from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ReductionListCompToGenerator(BaseOperator):
    name = "ReductionListCompToGenerator"
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
                if isinstance(node.func, ast.Name) and node.args and node.func.id in {"sum", "all", "any", "min", "max"}:
                    first = node.args[0]
                    if isinstance(first, ast.ListComp):
                        changed = True
                        node.args[0] = ast.GeneratorExp(elt=first.elt, generators=first.generators)
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced reduction over list comprehension with generator expression.",
            )
        ]
