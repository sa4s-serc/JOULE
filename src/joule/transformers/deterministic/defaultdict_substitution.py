from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import ensure_import_from, structural_eq


def _empty_dict_assign(stmt: ast.stmt) -> str | None:
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    if not isinstance(stmt.targets[0], ast.Name):
        return None
    if not (isinstance(stmt.value, ast.Dict) and stmt.value.keys == [] and stmt.value.values == []):
        return None
    return stmt.targets[0].id


def _defaultdict_guard_key(stmt: ast.stmt, mapping_name: str) -> ast.expr | None:
    if not isinstance(stmt, ast.If) or stmt.orelse:
        return None
    if not (
        isinstance(stmt.test, ast.Compare)
        and len(stmt.test.ops) == 1
        and isinstance(stmt.test.ops[0], ast.NotIn)
        and len(stmt.test.comparators) == 1
        and isinstance(stmt.test.comparators[0], ast.Name)
        and stmt.test.comparators[0].id == mapping_name
    ):
        return None
    if len(stmt.body) != 1 or not isinstance(stmt.body[0], ast.Assign):
        return None
    assign = stmt.body[0]
    if not (
        len(assign.targets) == 1
        and isinstance(assign.targets[0], ast.Subscript)
        and isinstance(assign.targets[0].value, ast.Name)
        and assign.targets[0].value.id == mapping_name
        and isinstance(assign.value, ast.List)
        and assign.value.elts == []
    ):
        return None
    if not structural_eq(assign.targets[0].slice, stmt.test.left):
        return None
    return stmt.test.left


def _append_call(stmt: ast.stmt, mapping_name: str, key_expr: ast.expr) -> bool:
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return False
    call = stmt.value
    if not (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "append"
        and isinstance(call.func.value, ast.Subscript)
        and isinstance(call.func.value.value, ast.Name)
        and call.func.value.value.id == mapping_name
        and structural_eq(call.func.value.slice, key_expr)
        and len(call.args) == 1
        and not call.keywords
    ):
        return False
    return True


class DefaultDictSubstitution(BaseOperator):
    name = "DefaultDictSubstitution"
    family = "deterministic"
    tier = Tier.H
    targets_smells = frozenset(["C1", "C5"])
    precheck_node_types = (ast.If,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.If):
            return False
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Name) and _defaultdict_guard_key(node, candidate.id) is not None:
                return True
        return False

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        if not isinstance(tree, ast.Module):
            return []
        changed = False
        needs_import = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed, needs_import
            rewritten: list[ast.stmt] = []
            index = 0
            while index < len(statements):
                first = statements[index]
                second = statements[index + 1] if index + 1 < len(statements) else None
                mapping_name = _empty_dict_assign(first)
                if mapping_name and isinstance(second, ast.For) and len(second.body) >= 2:
                    key_expr = _defaultdict_guard_key(second.body[0], mapping_name)
                    if key_expr is not None and _append_call(second.body[1], mapping_name, key_expr):
                        assign = first if isinstance(first, ast.Assign) else None
                        if assign is None:
                            rewritten.append(first)
                            index += 1
                            continue
                        changed = True
                        needs_import = True
                        assign.value = ast.Call(
                            func=ast.Name(id="defaultdict", ctx=ast.Load()),
                            args=[ast.Lambda(args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]), body=ast.List(elts=[], ctx=ast.Load()))],
                            keywords=[],
                        )
                        second.body = [second.body[1], *second.body[2:]]
                        rewritten.append(assign)
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
        if changed and needs_import:
            ensure_import_from(new_tree, "collections", "defaultdict")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced guard-based dict list initialization with defaultdict(list-like factory).",
                dependencies=["collections"],
            )
        ]
