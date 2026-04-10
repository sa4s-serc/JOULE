from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class DictKeysMembershipElision(BaseOperator):
    name = "DictKeysMembershipElision"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Compare,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.Compare):
            return False
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return False
        comparator = node.comparators[0]
        return (
            isinstance(node.ops[0], ast.In)
            and isinstance(comparator, ast.Call)
            and isinstance(comparator.func, ast.Attribute)
            and comparator.func.attr == "keys"
            and comparator.args == []
            and comparator.keywords == []
        )

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
                if (
                    isinstance(node.ops[0], ast.In)
                    and isinstance(comparator, ast.Call)
                    and isinstance(comparator.func, ast.Attribute)
                    and comparator.func.attr == "keys"
                    and comparator.args == []
                    and comparator.keywords == []
                ):
                    changed = True
                    node.comparators[0] = comparator.func.value
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Removed redundant dict.keys() wrapper in membership checks.",
            )
        ]
