from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import structural_eq


def _list_initializer(stmt: ast.stmt) -> str | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    if not isinstance(stmt.targets[0], ast.Name):
        return None
    if not (isinstance(stmt.value, ast.List) and stmt.value.elts == []):
        return None
    return stmt.targets[0].id


def _dedup_if_key(stmt: ast.stmt, output_name: str) -> ast.expr | None:
    if not isinstance(stmt, ast.If):
        return None
    if not (
        isinstance(stmt.test, ast.Compare)
        and len(stmt.test.ops) == 1
        and isinstance(stmt.test.ops[0], ast.NotIn)
        and len(stmt.test.comparators) == 1
        and isinstance(stmt.test.comparators[0], ast.Name)
        and stmt.test.comparators[0].id == output_name
    ):
        return None
    if not stmt.body:
        return None
    first = stmt.body[0]
    if not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Attribute)
        and isinstance(first.value.func.value, ast.Name)
        and first.value.func.value.id == output_name
        and first.value.func.attr == "append"
        and len(first.value.args) == 1
        and not first.value.keywords
        and structural_eq(first.value.args[0], stmt.test.left)
    ):
        return None
    return stmt.test.left


def _scope_names(statements: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


class SeenSetForAppendDedup(BaseOperator):
    name = "SeenSetForAppendDedup"
    family = "deterministic"
    tier = Tier.H
    targets_smells = frozenset(["C3", "C5"])
    precheck_node_types = (ast.If,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.If):
            return False
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Name) and _dedup_if_key(node, candidate.id) is not None:
                return True
        return False

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed
            known_names = _scope_names(statements)
            rewritten: list[ast.stmt] = []
            index = 0
            while index < len(statements):
                first = statements[index]
                second = statements[index + 1] if index + 1 < len(statements) else None
                output_name = _list_initializer(first)
                if output_name and isinstance(second, ast.For) and second.body and isinstance(second.body[0], ast.If):
                    key_expr = _dedup_if_key(second.body[0], output_name)
                    if key_expr is not None:
                        seen_name = f"_{output_name}_seen"
                        while seen_name in known_names:
                            seen_name += "_"
                        known_names.add(seen_name)

                        dedup_if = second.body[0]
                        test = dedup_if.test
                        assert isinstance(test, ast.Compare)
                        test.comparators[0] = ast.Name(id=seen_name, ctx=ast.Load())
                        dedup_if.body.insert(
                            0,
                            ast.Expr(
                                value=ast.Call(
                                    func=ast.Attribute(
                                        value=ast.Name(id=seen_name, ctx=ast.Load()),
                                        attr="add",
                                        ctx=ast.Load(),
                                    ),
                                    args=[key_expr],
                                    keywords=[],
                                )
                            ),
                        )

                        changed = True
                        rewritten.append(first)
                        rewritten.append(
                            ast.Assign(
                                targets=[ast.Name(id=seen_name, ctx=ast.Store())],
                                value=ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[]),
                            )
                        )
                        rewritten.append(second)
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
                reasoning="Introduced a seen-set side cache for append-based deduplication loops.",
            )
        ]
