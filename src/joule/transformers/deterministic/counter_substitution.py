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


def _counter_branch_key(stmt: ast.stmt, counter_name: str) -> ast.expr | None:
    if not isinstance(stmt, ast.If) or len(stmt.body) != 1 or len(stmt.orelse) != 1:
        return None

    cond = stmt.test
    if not (
        isinstance(cond, ast.Compare)
        and len(cond.ops) == 1
        and isinstance(cond.ops[0], ast.In)
        and len(cond.comparators) == 1
        and isinstance(cond.comparators[0], ast.Name)
        and cond.comparators[0].id == counter_name
    ):
        return None
    key_expr = cond.left

    increment = stmt.body[0]
    initialize = stmt.orelse[0]
    if not (
        isinstance(increment, ast.AugAssign)
        and isinstance(increment.op, ast.Add)
        and isinstance(increment.target, ast.Subscript)
        and isinstance(increment.target.value, ast.Name)
        and increment.target.value.id == counter_name
        and isinstance(increment.value, ast.Constant)
        and increment.value.value == 1
    ):
        return None
    if not structural_eq(increment.target.slice, key_expr):
        return None

    if not (
        isinstance(initialize, ast.Assign)
        and len(initialize.targets) == 1
        and isinstance(initialize.targets[0], ast.Subscript)
        and isinstance(initialize.targets[0].value, ast.Name)
        and initialize.targets[0].value.id == counter_name
        and isinstance(initialize.value, ast.Constant)
        and initialize.value.value == 1
        and structural_eq(initialize.targets[0].slice, key_expr)
    ):
        return None

    return key_expr


class CounterSubstitution(BaseOperator):
    name = "CounterSubstitution"
    family = "deterministic"
    tier = Tier.H
    targets_smells = frozenset(["C1", "C5"])
    precheck_node_types = (ast.If,)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, ast.If):
            return False
        for candidate in ast.walk(node):
            if isinstance(candidate, ast.Name) and _counter_branch_key(node, candidate.id) is not None:
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
        needs_counter_import = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed, needs_counter_import
            rewritten: list[ast.stmt] = []
            index = 0
            while index < len(statements):
                first = statements[index]
                second = statements[index + 1] if index + 1 < len(statements) else None
                counter_name = _empty_dict_assign(first)
                if counter_name and isinstance(second, ast.For) and second.body:
                    key_expr = _counter_branch_key(second.body[0], counter_name)
                    if key_expr is not None:
                        assign = first if isinstance(first, ast.Assign) else None
                        if assign is None:
                            rewritten.append(first)
                            index += 1
                            continue
                        changed = True
                        needs_counter_import = True
                        assign.value = ast.Call(func=ast.Name(id="Counter", ctx=ast.Load()), args=[], keywords=[])
                        second.body[0] = ast.AugAssign(
                            target=ast.Subscript(
                                value=ast.Name(id=counter_name, ctx=ast.Load()),
                                slice=key_expr,
                                ctx=ast.Store(),
                            ),
                            op=ast.Add(),
                            value=ast.Constant(value=1),
                        )
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
        if changed and needs_counter_import:
            ensure_import_from(new_tree, "collections", "Counter")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Converted manual frequency map increments to collections.Counter updates.",
                dependencies=["collections"],
            )
        ]
