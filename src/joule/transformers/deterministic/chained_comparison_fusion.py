from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ChainedComparisonFusion(BaseOperator):
    name = "ChainedComparisonFusion"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.BoolOp,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_BoolOp(self, node: ast.BoolOp):
                nonlocal changed
                self.generic_visit(node)
                if not isinstance(node.op, ast.And) or len(node.values) != 2:
                    return node
                left, right = node.values
                if not (isinstance(left, ast.Compare) and isinstance(right, ast.Compare)):
                    return node
                if len(left.ops) != 1 or len(left.comparators) != 1 or len(right.ops) != 1 or len(right.comparators) != 1:
                    return node
                pivot = left.comparators[0]
                if ast.dump(pivot) != ast.dump(right.left):
                    return node
                changed = True
                return ast.Compare(
                    left=left.left,
                    ops=[left.ops[0], right.ops[0]],
                    comparators=[left.comparators[0], right.comparators[0]],
                )

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Fused adjacent AND-ed comparisons into chained comparison syntax.",
            )
        ]
