from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import insertion_index


SAFE_MODULES = {
    "bisect",
    "collections",
    "functools",
    "heapq",
    "itertools",
    "json",
    "math",
    "operator",
    "re",
    "statistics",
    "string",
}


def _root_module(name: str) -> str:
    return name.split(".", 1)[0]


def _safe_import_statement(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Import):
        return all(_root_module(alias.name) in SAFE_MODULES for alias in stmt.names)
    if isinstance(stmt, ast.ImportFrom):
        return stmt.level == 0 and stmt.module is not None and _root_module(stmt.module) in SAFE_MODULES
    return False


def _import_signatures(module: ast.Module) -> set[tuple[str, str, str, str | None, int]]:
    signatures: set[tuple[str, str, str, str | None, int]] = set()
    for stmt in module.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                signatures.add(("import", alias.name, "", alias.asname, 0))
        elif isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
            for alias in stmt.names:
                signatures.add(("from", stmt.module, alias.name, alias.asname, stmt.level))
    return signatures


def _import_alias_names(stmt: ast.stmt) -> set[str]:
    names: set[str] = set()
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            names.add(alias.asname or _root_module(alias.name))
    elif isinstance(stmt, ast.ImportFrom):
        for alias in stmt.names:
            if alias.name == "*":
                continue
            names.add(alias.asname or alias.name)
    return names


def _bound_name_targets(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Param))
    }


def _module_level_bound_names(module: ast.Module) -> set[str]:
    bound: set[str] = set()
    for stmt in module.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(stmt.name)
            continue
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                bound.add(alias.asname or _root_module(alias.name))
            continue
        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                if alias.name == "*":
                    continue
                bound.add(alias.asname or alias.name)
            continue
        bound.update(_bound_name_targets(stmt))
    return bound


class LocalImportHoisting(BaseOperator):
    name = "LocalImportHoisting"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Import, ast.ImportFrom)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, (ast.Import, ast.ImportFrom)) and _safe_import_statement(node)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        if not isinstance(tree, ast.Module):
            return []

        changed = False
        hoisted: list[ast.stmt] = []
        blocked_aliases = _module_level_bound_names(tree)

        class Rewriter(ast.NodeTransformer):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                nonlocal changed
                self.generic_visit(node)
                index = 0
                while index < len(node.body) and isinstance(node.body[index], (ast.Import, ast.ImportFrom)):
                    if _safe_import_statement(node.body[index]):
                        if _import_alias_names(node.body[index]) & blocked_aliases:
                            break
                        hoisted.append(node.body[index])
                        changed = True
                        index += 1
                        continue
                    break
                if index:
                    node.body = node.body[index:] or [ast.Pass()]
                return node

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                nonlocal changed
                self.generic_visit(node)
                index = 0
                while index < len(node.body) and isinstance(node.body[index], (ast.Import, ast.ImportFrom)):
                    if _safe_import_statement(node.body[index]):
                        if _import_alias_names(node.body[index]) & blocked_aliases:
                            break
                        hoisted.append(node.body[index])
                        changed = True
                        index += 1
                        continue
                    break
                if index:
                    node.body = node.body[index:] or [ast.Pass()]
                return node

        new_tree = Rewriter().visit(tree)
        if not changed or not isinstance(new_tree, ast.Module):
            return []

        existing = _import_signatures(new_tree)
        module_bound_names = _module_level_bound_names(new_tree)
        additions: list[ast.stmt] = []
        for stmt in hoisted:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    alias_name = alias.asname or _root_module(alias.name)
                    signature = ("import", alias.name, "", alias.asname, 0)
                    if signature in existing:
                        continue
                    if alias_name in module_bound_names:
                        continue
                    additions.append(ast.Import(names=[ast.alias(name=alias.name, asname=alias.asname)]))
                    existing.add(signature)
            elif isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
                for alias in stmt.names:
                    alias_name = alias.asname or alias.name
                    signature = ("from", stmt.module, alias.name, alias.asname, stmt.level)
                    if signature in existing:
                        continue
                    if alias_name in module_bound_names:
                        continue
                    additions.append(
                        ast.ImportFrom(
                            module=stmt.module,
                            names=[ast.alias(name=alias.name, asname=alias.asname)],
                            level=stmt.level,
                        )
                    )
                    existing.add(signature)

        insert_at = insertion_index(new_tree)
        for offset, stmt in enumerate(additions):
            new_tree.body.insert(insert_at + offset, stmt)

        ast.fix_missing_locations(new_tree)
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Hoisted safe stdlib imports from function scope to module scope.",
            )
        ]
