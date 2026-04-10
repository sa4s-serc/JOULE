from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class GeneratorToYieldFrom(BaseOperator):
    name = "GeneratorToYieldFrom"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.For,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_For(self, node: ast.For):
                nonlocal changed
                self.generic_visit(node)
                if node.orelse:
                    return node
                if len(node.body) != 1:
                    return node
                stmt = node.body[0]
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Yield):
                    yielded = stmt.value.value
                    if isinstance(node.target, ast.Name) and isinstance(yielded, ast.Name) and yielded.id == node.target.id:
                        changed = True
                        return ast.copy_location(ast.Expr(value=ast.YieldFrom(value=node.iter)), node)
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced pass-through generator loop with yield from.",
            )
        ]
