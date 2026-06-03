from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class DictGetWithDefault(BaseOperator):
    name = "DictGetWithDefault"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C4", "C5"])
    precheck_node_types = (ast.If,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_If(self, node: ast.If):
                nonlocal changed
                self.generic_visit(node)
                if len(node.body) != 1 or len(node.orelse) != 1:
                    return node
                test = node.test
                body_stmt = node.body[0]
                else_stmt = node.orelse[0]
                if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.In)):
                    return node
                if len(test.comparators) != 1:
                    return node
                mapping = test.comparators[0]
                key = test.left
                if not (
                    isinstance(body_stmt, ast.Assign)
                    and len(body_stmt.targets) == 1
                    and isinstance(else_stmt, ast.Assign)
                    and len(else_stmt.targets) == 1
                ):
                    return node
                if ast.dump(body_stmt.targets[0]) != ast.dump(else_stmt.targets[0]):
                    return node
                body_value = body_stmt.value
                if not (
                    isinstance(body_value, ast.Subscript)
                    and ast.dump(body_value.value) == ast.dump(mapping)
                    and ast.dump(body_value.slice) == ast.dump(key)
                ):
                    return node
                changed = True
                return ast.Assign(
                    targets=body_stmt.targets,
                    value=ast.Call(
                        func=ast.Attribute(value=mapping, attr="get", ctx=ast.Load()),
                        args=[key, else_stmt.value],
                        keywords=[],
                    ),
                )

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced explicit dict membership branch with dict.get default access.",
            )
        ]
