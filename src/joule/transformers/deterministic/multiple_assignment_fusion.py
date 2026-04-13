from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import loaded_names


def _single_name_assignment(stmt: ast.AST) -> tuple[str, ast.expr] | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return None
    return target.id, stmt.value


class MultipleAssignmentFusion(BaseOperator):
    name = "MultipleAssignmentFusion"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Assign,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return _single_name_assignment(node) is not None

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed
            rewritten: list[ast.stmt] = []
            index = 0
            while index < len(statements):
                first = statements[index]
                second = statements[index + 1] if index + 1 < len(statements) else None
                first_data = _single_name_assignment(first)
                second_data = _single_name_assignment(second) if second is not None else None
                if first_data and second_data:
                    first_name, first_value = first_data
                    second_name, second_value = second_data
                    if (
                        first_name != second_name
                        and second_name not in loaded_names(first_value)
                        and first_name not in loaded_names(second_value)
                    ):
                        changed = True
                        rewritten.append(
                            ast.copy_location(
                                ast.Assign(
                                    targets=[
                                        ast.Tuple(
                                            elts=[
                                                ast.Name(id=first_name, ctx=ast.Store()),
                                                ast.Name(id=second_name, ctx=ast.Store()),
                                            ],
                                            ctx=ast.Store(),
                                        )
                                    ],
                                    value=ast.Tuple(elts=[first_value, second_value], ctx=ast.Load()),
                                ),
                                first,
                            )
                        )
                        index += 2
                        continue
                rewritten.append(first)
                index += 1
            return rewritten

        class Rewriter(ast.NodeTransformer):
            def visit_Module(self, node: ast.Module):
                node.body = rewrite_statements(node.body)
                self.generic_visit(node)
                return node

            def visit_FunctionDef(self, node: ast.FunctionDef):
                node.body = rewrite_statements(node.body)
                self.generic_visit(node)
                return node

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                node.body = rewrite_statements(node.body)
                self.generic_visit(node)
                return node

            def visit_For(self, node: ast.For):
                node.body = rewrite_statements(node.body)
                node.orelse = rewrite_statements(node.orelse)
                self.generic_visit(node)
                return node

            def visit_While(self, node: ast.While):
                node.body = rewrite_statements(node.body)
                node.orelse = rewrite_statements(node.orelse)
                self.generic_visit(node)
                return node

            def visit_If(self, node: ast.If):
                node.body = rewrite_statements(node.body)
                node.orelse = rewrite_statements(node.orelse)
                self.generic_visit(node)
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Fused independent adjacent assignments into tuple assignment.",
            )
        ]
