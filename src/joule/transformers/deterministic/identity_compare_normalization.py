from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class IdentityCompareNormalization(BaseOperator):
    name = "IdentityCompareNormalization"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C4"])
    precheck_node_types = (ast.Compare,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Compare(self, node: ast.Compare):
                nonlocal changed
                self.generic_visit(node)
                if len(node.ops) != 1 or len(node.comparators) != 1:
                    return node
                comparator = node.comparators[0]
                if not (isinstance(comparator, ast.Constant) and comparator.value is None):
                    return node
                if isinstance(node.ops[0], ast.Eq):
                    changed = True
                    node.ops[0] = ast.Is()
                elif isinstance(node.ops[0], ast.NotEq):
                    changed = True
                    node.ops[0] = ast.IsNot()
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Normalized None comparisons to identity operators.",
            )
        ]
