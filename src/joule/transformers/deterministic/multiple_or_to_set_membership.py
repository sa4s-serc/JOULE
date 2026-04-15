from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _is_hashable_constant(node: ast.expr) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    try:
        hash(node.value)
    except TypeError:
        return False
    return True


class MultipleOrToSetMembership(BaseOperator):
    name = "MultipleOrToSetMembership"
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
                if not isinstance(node.op, ast.Or) or len(node.values) < 2:
                    return node
                comparisons = []
                for part in node.values:
                    if not isinstance(part, ast.Compare) or len(part.ops) != 1 or len(part.comparators) != 1:
                        return node
                    if not isinstance(part.ops[0], ast.Eq):
                        return node
                    if not _is_hashable_constant(part.comparators[0]):
                        return node
                    comparisons.append(part)
                anchor = comparisons[0].left
                if not all(ast.dump(comp.left) == ast.dump(anchor) for comp in comparisons[1:]):
                    return node
                changed = True
                return ast.Compare(
                    left=anchor,
                    ops=[ast.In()],
                    comparators=[ast.Set(elts=[comp.comparators[0] for comp in comparisons])],
                )

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Collapsed repeated equality OR checks into set membership.",
            )
        ]
