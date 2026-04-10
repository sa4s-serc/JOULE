from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ConstantConditionElision(BaseOperator):
    name = "ConstantConditionElision"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.If,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_If(self, node: ast.If):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool):
                    changed = True
                    selected = node.body if node.test.value else node.orelse
                    return selected
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Elided statically-known boolean branches.",
            )
        ]
