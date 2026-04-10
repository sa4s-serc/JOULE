from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class FStringConversion(BaseOperator):
    name = "FStringConversion"
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
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and not node.keywords
                ):
                    template = node.func.value.value
                    slots = template.count("{}")
                    if slots == len(node.args) and slots > 0:
                        parts = template.split("{}")
                        values: list[ast.expr] = []
                        for index, text in enumerate(parts):
                            if text:
                                values.append(ast.Constant(value=text))
                            if index < len(node.args):
                                values.append(ast.FormattedValue(value=node.args[index], conversion=-1))
                        changed = True
                        return ast.JoinedStr(values=values)
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Converted simple str.format usage to f-string form.",
            )
        ]
