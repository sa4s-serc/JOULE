from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import ensure_import_from


def _is_list_init(expr: ast.expr) -> bool:
    if isinstance(expr, ast.List):
        return True
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "list"
        and len(expr.args) <= 1
        and not expr.keywords
    )


def _is_pop_zero_call(expr: ast.expr, queue_name: str) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and isinstance(expr.func.value, ast.Name)
        and expr.func.value.id == queue_name
        and expr.func.attr == "pop"
        and len(expr.args) == 1
        and isinstance(expr.args[0], ast.Constant)
        and expr.args[0].value == 0
        and not expr.keywords
    )


def _rewrite_pop_zero(stmt: ast.stmt, queue_name: str) -> bool:
    changed = False

    class PopRewrite(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call):
            nonlocal changed
            self.generic_visit(node)
            if _is_pop_zero_call(node, queue_name):
                changed = True
                node.func.attr = "popleft"
                node.args = []
            return node

    PopRewrite().visit(stmt)
    return changed


def _contains_pop_zero(node: ast.AST, queue_name: str) -> bool:
    return any(
        isinstance(item, ast.Call) and _is_pop_zero_call(item, queue_name)
        for item in ast.walk(node)
    )


def _reassigns_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store) and item.id == name
        for item in ast.walk(node)
    )


class ListPopZeroToDeque(BaseOperator):
    name = "ListPopZeroToDeque"
    family = "deterministic"
    tier = Tier.H
    precheck_node_types = (ast.While,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.While):
            return False
        if not isinstance(node.test, ast.Name):
            return False
        return _contains_pop_zero(node, node.test.id)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False
        needs_deque_import = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed, needs_deque_import
            for index, stmt in enumerate(statements):
                if not (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and _is_list_init(stmt.value)
                ):
                    continue
                queue_name = stmt.targets[0].id
                while_index: int | None = None
                for follow_index in range(index + 1, len(statements)):
                    follow_stmt = statements[follow_index]
                    if _reassigns_name(follow_stmt, queue_name):
                        break
                    if (
                        isinstance(follow_stmt, ast.While)
                        and isinstance(follow_stmt.test, ast.Name)
                        and follow_stmt.test.id == queue_name
                        and _contains_pop_zero(follow_stmt, queue_name)
                    ):
                        while_index = follow_index
                        break
                if while_index is None:
                    continue
                if _rewrite_pop_zero(statements[while_index], queue_name):
                    changed = True
                    needs_deque_import = True
                    stmt.value = ast.Call(
                        func=ast.Name(id="deque", ctx=ast.Load()),
                        args=[stmt.value],
                        keywords=[],
                    )
            return statements

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
        if changed and isinstance(new_tree, ast.Module) and needs_deque_import:
            ensure_import_from(new_tree, "collections", "deque")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Converted queue-style list.pop(0) usage to deque.popleft().",
                dependencies=["collections"],
            )
        ]
