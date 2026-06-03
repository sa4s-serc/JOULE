from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ReturnBoolSimplification(BaseOperator):
    name = "ReturnBoolSimplification"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C4"])
    precheck_node_types = (ast.If,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_If(self, node: ast.If):
                nonlocal changed
                self.generic_visit(node)
                if len(node.body) == 1 and len(node.orelse) == 1:
                    if_body = node.body[0]
                    if_else = node.orelse[0]
                    if (
                        isinstance(if_body, ast.Return)
                        and isinstance(if_else, ast.Return)
                        and isinstance(if_body.value, ast.Constant)
                        and isinstance(if_else.value, ast.Constant)
                        and isinstance(if_body.value.value, bool)
                        and isinstance(if_else.value.value, bool)
                    ):
                        if if_body.value.value is True and if_else.value.value is False:
                            changed = True
                            return ast.Return(value=node.test)
                        if if_body.value.value is False and if_else.value.value is True:
                            changed = True
                            return ast.Return(value=ast.UnaryOp(op=ast.Not(), operand=node.test))
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Simplified boolean if/else return pattern into a direct boolean return.",
            )
        ]
