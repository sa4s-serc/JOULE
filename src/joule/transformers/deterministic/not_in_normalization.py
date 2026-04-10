from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class NotInNormalization(BaseOperator):
    name = "NotInNormalization"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.UnaryOp,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_UnaryOp(self, node: ast.UnaryOp):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.op, ast.Not) and isinstance(node.operand, ast.Compare):
                    compare = node.operand
                    if len(compare.ops) == 1 and isinstance(compare.ops[0], ast.In):
                        changed = True
                        compare.ops[0] = ast.NotIn()
                        return compare
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Normalized negated membership checks into direct not-in comparisons.",
            )
        ]
