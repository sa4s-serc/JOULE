from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _flatten_add_chain(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [*_flatten_add_chain(node.left), *_flatten_add_chain(node.right)]
    return [node]


def _is_string_fragment(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "str"
        and len(node.args) == 1
        and not node.keywords
    )


class StringConcatToJoin(BaseOperator):
    name = "StringConcatToJoin"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C10"])
    precheck_node_types = (ast.BinOp,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.BinOp):
            return False
        parts = _flatten_add_chain(node)
        return len(parts) >= 3 and all(_is_string_fragment(item) for item in parts)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_BinOp(self, node: ast.BinOp):
                nonlocal changed
                self.generic_visit(node)
                parts = _flatten_add_chain(node)
                if len(parts) < 3 or not all(_is_string_fragment(item) for item in parts):
                    return node
                changed = True
                return ast.copy_location(
                    ast.Call(
                        func=ast.Attribute(value=ast.Constant(value=""), attr="join", ctx=ast.Load()),
                        args=[ast.Tuple(elts=parts, ctx=ast.Load())],
                        keywords=[],
                    ),
                    node,
                )

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced chained string concatenation with ''.join(...).",
            )
        ]
