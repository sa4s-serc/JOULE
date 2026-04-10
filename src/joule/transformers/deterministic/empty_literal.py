from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class EmptyLiteralOperator(BaseOperator):
    name = "empty_literal"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Call,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and not node.args and not node.keywords:
                    if node.func.id == "list":
                        changed = True
                        return ast.List(elts=[], ctx=ast.Load())
                    if node.func.id == "dict":
                        changed = True
                        return ast.Dict(keys=[], values=[])
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced zero-argument constructor calls with literal forms.",
            )
        ]
