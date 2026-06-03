from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import structural_eq


def _range_len_target(expr: ast.expr) -> ast.expr | None:
    if not (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "range"
        and len(expr.args) == 1
        and not expr.keywords
    ):
        return None
    inner = expr.args[0]
    if not (
        isinstance(inner, ast.Call)
        and isinstance(inner.func, ast.Name)
        and inner.func.id == "len"
        and len(inner.args) == 1
        and not inner.keywords
    ):
        return None
    return inner.args[0]


def _is_index_access(expr: ast.expr, *, sequence: ast.expr, index_name: str) -> bool:
    if not isinstance(expr, ast.Subscript):
        return False
    return structural_eq(expr.value, sequence) and isinstance(expr.slice, ast.Name) and expr.slice.id == index_name


class EnumerateSubstitution(BaseOperator):
    name = "EnumerateSubstitution"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C3", "C10"])
    precheck_node_types = (ast.For,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Name) or not node.body:
            return False
        sequence = _range_len_target(node.iter)
        if sequence is None:
            return False
        first = node.body[0]
        return (
            isinstance(first, ast.Assign)
            and len(first.targets) == 1
            and isinstance(first.targets[0], ast.Name)
            and _is_index_access(first.value, sequence=sequence, index_name=node.target.id)
        )

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_For(self, node: ast.For):
                nonlocal changed
                self.generic_visit(node)
                if not isinstance(node.target, ast.Name) or not node.body:
                    return node
                sequence = _range_len_target(node.iter)
                if sequence is None:
                    return node
                first = node.body[0]
                if not (
                    isinstance(first, ast.Assign)
                    and len(first.targets) == 1
                    and isinstance(first.targets[0], ast.Name)
                    and _is_index_access(first.value, sequence=sequence, index_name=node.target.id)
                ):
                    return node

                changed = True
                index_name = node.target.id
                value_name = first.targets[0].id
                node.target = ast.Tuple(
                    elts=[
                        ast.Name(id=index_name, ctx=ast.Store()),
                        ast.Name(id=value_name, ctx=ast.Store()),
                    ],
                    ctx=ast.Store(),
                )
                node.iter = ast.Call(
                    func=ast.Name(id="enumerate", ctx=ast.Load()),
                    args=[sequence],
                    keywords=[],
                )
                node.body = node.body[1:] or [ast.Pass()]
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Rewrote index-based loops into enumerate()-driven iteration.",
            )
        ]
