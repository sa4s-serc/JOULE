from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import ensure_import_from


DISALLOWED_NODES = (
    ast.Assign,
    ast.AnnAssign,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.AugAssign,
    ast.Await,
    ast.Delete,
    ast.For,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


def _decorator_name(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    if isinstance(expr, ast.Call):
        return _decorator_name(expr.func)
    return None


def _has_cache_decorator(node: ast.FunctionDef) -> bool:
    return any(_decorator_name(item) in {"cache", "lru_cache"} for item in node.decorator_list)


def _has_recursive_call(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == node.name
        for call in ast.walk(node)
    )


def _memoization_safe(node: ast.FunctionDef) -> bool:
    if _has_cache_decorator(node) or not _has_recursive_call(node):
        return False
    if any(isinstance(item, DISALLOWED_NODES) for item in ast.walk(node)):
        return False
    return any(isinstance(item, ast.Return) for item in ast.walk(node))


class MemoizationAddition(BaseOperator):
    name = "MemoizationAddition"
    family = "deterministic"
    tier = Tier.H
    precheck_node_types = (ast.FunctionDef,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.FunctionDef) and _memoization_safe(node)

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

        class Rewriter(ast.NodeTransformer):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                nonlocal changed, needs_import
                self.generic_visit(node)
                if not _memoization_safe(node):
                    return node
                changed = True
                needs_import = True
                node.decorator_list.insert(
                    0,
                    ast.Call(
                        func=ast.Name(id="lru_cache", ctx=ast.Load()),
                        args=[],
                        keywords=[ast.keyword(arg="maxsize", value=ast.Constant(value=None))],
                    ),
                )
                return node

        new_tree = Rewriter().visit(tree)
        if changed and needs_import:
            ensure_import_from(new_tree, "functools", "lru_cache")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Added functools.lru_cache to eligible recursive functions.",
                dependencies=["functools"],
            )
        ]
