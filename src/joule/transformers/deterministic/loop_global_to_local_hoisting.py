from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import assigned_names


FAST_BUILTINS = {"abs", "all", "any", "len", "max", "min", "sum"}


def _called_builtin_names(node: ast.AST) -> set[str]:
    return {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in FAST_BUILTINS
    }


def _scope_names(statements: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


def _rewrite_loop_calls(loop: ast.stmt, alias_map: dict[str, str]) -> ast.stmt:
    class LoopRewriter(ast.NodeTransformer):
        def visit_Call(self, node: ast.Call):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in alias_map:
                node.func = ast.Name(id=alias_map[node.func.id], ctx=ast.Load())
            return node

    return LoopRewriter().visit(loop)


class LoopGlobalToLocalHoisting(BaseOperator):
    name = "LoopGlobalToLocalHoisting"
    family = "deterministic"
    tier = Tier.H
    targets_smells = frozenset(["C8", "C10"])
    precheck_node_types = (ast.For, ast.While)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, (ast.For, ast.While)):
            return False
        return bool(_called_builtin_names(node))

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
            for stmt in statements:
                if isinstance(stmt, (ast.For, ast.While)):
                    builtin_names = sorted(name for name in _called_builtin_names(stmt) if name not in assigned_names(stmt))
                    if builtin_names:
                        alias_map: dict[str, str] = {}
                        for name in builtin_names:
                            alias = f"_{name}_local"
                            while alias in known_names:
                                alias += "_"
                            known_names.add(alias)
                            alias_map[name] = alias

                        rewritten.extend(
                            ast.Assign(
                                targets=[ast.Name(id=alias, ctx=ast.Store())],
                                value=ast.Name(id=name, ctx=ast.Load()),
                            )
                            for name, alias in alias_map.items()
                        )
                        rewritten.append(_rewrite_loop_calls(stmt, alias_map))
                        changed = True
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
                reasoning="Hoisted repeated builtin lookups to local aliases before loops.",
            )
        ]
