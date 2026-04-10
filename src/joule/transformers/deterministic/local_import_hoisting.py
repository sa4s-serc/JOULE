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

        class Rewriter(ast.NodeTransformer):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                nonlocal changed
                self.generic_visit(node)
                index = 0
                while index < len(node.body) and isinstance(node.body[index], (ast.Import, ast.ImportFrom)):
                    if _safe_import_statement(node.body[index]):
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
        additions: list[ast.stmt] = []
        for stmt in hoisted:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    signature = ("import", alias.name, "", alias.asname, 0)
                    if signature in existing:
                        continue
                    additions.append(ast.Import(names=[ast.alias(name=alias.name, asname=alias.asname)]))
                    existing.add(signature)
            elif isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
                for alias in stmt.names:
                    signature = ("from", stmt.module, alias.name, alias.asname, stmt.level)
                    if signature in existing:
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
