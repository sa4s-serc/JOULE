from __future__ import annotations

import ast
from collections.abc import Iterable

from joule.models import TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class NoopDeterministicOperator(BaseOperator):
    family = "deterministic"

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del target, context
        return []


class AstTransformOperator(BaseOperator):
    family = "deterministic"

    def transform(self, tree: ast.AST) -> tuple[ast.AST, bool]:
        raise NotImplementedError

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        new_tree, changed = self.transform(tree)
        ast.fix_missing_locations(new_tree)
        try:
            rewritten = ast.unparse(new_tree)
        except Exception:
            return []
        if not changed or rewritten.strip() == target.source.strip():
            return []
        return [
            self.build_result(
                candidate_source=rewritten,
                reasoning=self.reasoning(),
            )
        ]

    def reasoning(self) -> str:
        return "Applied deterministic AST rewrite."


def structural_eq(left: ast.AST, right: ast.AST) -> bool:
    return ast.dump(left, annotate_fields=False, include_attributes=False) == ast.dump(
        right,
        annotate_fields=False,
        include_attributes=False,
    )


def loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def assigned_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}


def insertion_index(module: ast.Module) -> int:
    index = 0
    if (
        module.body
        and isinstance(module.body[0], ast.Expr)
        and isinstance(module.body[0].value, ast.Constant)
        and isinstance(module.body[0].value.value, str)
    ):
        index = 1
    while (
        index < len(module.body)
        and isinstance(module.body[index], ast.ImportFrom)
        and module.body[index].module == "__future__"
    ):
        index += 1
    return index


def _import_aliases(names: Iterable[ast.alias]) -> set[tuple[str, str | None]]:
    return {(alias.name, alias.asname) for alias in names}


def ensure_import(module: ast.Module, module_name: str) -> bool:
    for stmt in module.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.name == module_name and alias.asname is None:
                    return False
    module.body.insert(insertion_index(module), ast.Import(names=[ast.alias(name=module_name)]))
    return True


def ensure_import_from(module: ast.Module, package: str, symbol: str) -> bool:
    for stmt in module.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.level == 0 and stmt.module == package:
            existing = _import_aliases(stmt.names)
            if (symbol, None) in existing:
                return False
            stmt.names.append(ast.alias(name=symbol))
            return True
    module.body.insert(
        insertion_index(module),
        ast.ImportFrom(module=package, names=[ast.alias(name=symbol)], level=0),
    )
    return True
