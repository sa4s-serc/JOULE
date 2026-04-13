from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _is_list_initializer(stmt: ast.stmt, name: str) -> bool:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    if not isinstance(stmt.targets[0], ast.Name) or stmt.targets[0].id != name:
        return False
    value = stmt.value
    if isinstance(value, ast.List):
        return True
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "list"
        and len(value.args) <= 1
        and not value.keywords
    )


def _sorted_assignment(stmt: ast.AST) -> tuple[str, list[ast.keyword]] | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    if not isinstance(stmt.targets[0], ast.Name):
        return None
    target_name = stmt.targets[0].id
    value = stmt.value
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "sorted"
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Name)
        and value.args[0].id == target_name
    ):
        return None
    for keyword in value.keywords:
        if keyword.arg not in {"key", "reverse"}:
            return None
    return target_name, value.keywords


class SortedToInPlaceSort(BaseOperator):
    name = "SortedToInPlaceSort"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Assign,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return _sorted_assignment(node) is not None

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
            for stmt in statements:
                sorted_data = _sorted_assignment(stmt)
                if rewritten and sorted_data is not None:
                    name, keywords = sorted_data
                    if _is_list_initializer(rewritten[-1], name):
                        changed = True
                        rewritten.append(
                            ast.copy_location(
                                ast.Expr(
                                    value=ast.Call(
                                        func=ast.Attribute(
                                            value=ast.Name(id=name, ctx=ast.Load()),
                                            attr="sort",
                                            ctx=ast.Load(),
                                        ),
                                        args=[],
                                        keywords=keywords,
                                    )
                                ),
                                stmt,
                            )
                        )
                        continue
                rewritten.append(stmt)
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
                reasoning="Replaced sorted(list)-reassignment with in-place list.sort().",
            )
        ]
