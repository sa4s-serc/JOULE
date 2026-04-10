from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import assigned_names


MUTATING_METHODS = {
    "add",
    "append",
    "clear",
    "difference_update",
    "discard",
    "extend",
    "insert",
    "intersection_update",
    "pop",
    "remove",
    "reverse",
    "sort",
    "symmetric_difference_update",
    "update",
}


def _scope_names(statements: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for stmt in statements:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


def _membership_comparators(loop: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(loop):
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], (ast.In, ast.NotIn))
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], ast.Name)
        ):
            names.add(node.comparators[0].id)
    return names


def _mutated_containers(loop: ast.AST) -> set[str]:
    mutated = set(assigned_names(loop))
    for node in ast.walk(loop):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.attr in MUTATING_METHODS
        ):
            mutated.add(node.func.value.id)
    return mutated


def _rewrite_membership(loop: ast.stmt, alias_map: dict[str, str]) -> ast.stmt:
    class MembershipRewriter(ast.NodeTransformer):
        def visit_Compare(self, node: ast.Compare):
            self.generic_visit(node)
            if (
                len(node.ops) == 1
                and isinstance(node.ops[0], (ast.In, ast.NotIn))
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Name)
                and node.comparators[0].id in alias_map
            ):
                node.comparators[0] = ast.Name(id=alias_map[node.comparators[0].id], ctx=ast.Load())
            return node

    return MembershipRewriter().visit(loop)


class LoopMembershipSetCache(BaseOperator):
    name = "LoopMembershipSetCache"
    family = "deterministic"
    tier = Tier.H
    precheck_node_types = (ast.For, ast.While)

    def _precheck_node(self, node: ast.AST) -> bool:
        if not isinstance(node, (ast.For, ast.While)):
            return False
        candidates = _membership_comparators(node)
        if not candidates:
            return False
        return bool(candidates - _mutated_containers(node))

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
                    candidates = sorted(_membership_comparators(stmt) - _mutated_containers(stmt))
                    if candidates:
                        alias_map: dict[str, str] = {}
                        for name in candidates:
                            alias = f"_{name}_set"
                            while alias in known_names:
                                alias += "_"
                            known_names.add(alias)
                            alias_map[name] = alias

                        rewritten.extend(
                            ast.Assign(
                                targets=[ast.Name(id=alias, ctx=ast.Store())],
                                value=ast.Call(
                                    func=ast.Name(id="set", ctx=ast.Load()),
                                    args=[ast.Name(id=name, ctx=ast.Load())],
                                    keywords=[],
                                ),
                            )
                            for name, alias in alias_map.items()
                        )
                        rewritten.append(_rewrite_membership(stmt, alias_map))
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
                reasoning="Cached loop membership containers as sets outside loop bodies.",
            )
        ]
