from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ListToSetMembership(BaseOperator):
    name = "DataStructureSubstitution[list->set]"
    family = "deterministic"
    tier = Tier.H
    precheck_node_types = (ast.Compare,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Compare(self, node: ast.Compare):
                nonlocal changed
                self.generic_visit(node)
                if len(node.ops) != 1 or not isinstance(node.ops[0], ast.In):
                    return node
                comparator = node.comparators[0]
                if isinstance(comparator, (ast.List, ast.Tuple)) and len(comparator.elts) > 3:
                    if all(isinstance(item, ast.Constant) for item in comparator.elts):
                        changed = True
                        return ast.copy_location(
                            ast.Compare(
                                left=node.left,
                                ops=node.ops,
                                comparators=[ast.Set(elts=comparator.elts)],
                            ),
                            node,
                        )
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Substituted linear list membership with set-based lookup.",
            )
        ]
