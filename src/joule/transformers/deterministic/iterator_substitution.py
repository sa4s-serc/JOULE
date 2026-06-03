from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _iter_call(expr: ast.expr) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "iter"
        and len(expr.args) == 1
        and not expr.keywords
    )


class IteratorSubstitution(BaseOperator):
    name = "IteratorSubstitution"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C3", "C10"])
    precheck_node_types = (ast.For,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.For) and _iter_call(node.iter)

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
                iter_call = node.iter
                if _iter_call(iter_call):
                    assert isinstance(iter_call, ast.Call)
                    changed = True
                    node.iter = iter_call.args[0]
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Removed redundant iter() wrappers in for loops.",
            )
        ]
