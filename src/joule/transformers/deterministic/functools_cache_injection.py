from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import ensure_import_from


_DISQUALIFYING_NODES = (
    ast.Global,
    ast.Nonlocal,
    ast.Yield,
    ast.YieldFrom,
    ast.AsyncFor,
    ast.AsyncWith,
)

_IO_CALL_NAMES = {"open", "print", "input", "write", "read"}


def _decorator_name(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    if isinstance(expr, ast.Call):
        return _decorator_name(expr.func)
    return None


def _already_cached(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_name(d) in {"cache", "lru_cache", "cached_property"} for d in node.decorator_list)


def _has_io_side_effect(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name) and child.func.id in _IO_CALL_NAMES:
                return True
    return False


def _uses_mutable_default(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for default in node.args.defaults + node.args.kw_defaults:
        if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
            return True
    return False


def _is_cache_eligible(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True when the function is safe to wrap with @functools.cache."""
    if _already_cached(node):
        return False
    if isinstance(node, ast.AsyncFunctionDef):
        return False
    all_args = node.args.args + node.args.posonlyargs + node.args.kwonlyargs
    if not all_args:
        return False
    # Reject *args / **kwargs (hard to guarantee hashability)
    if node.args.vararg or node.args.kwarg:
        return False
    if any(isinstance(s, _DISQUALIFYING_NODES) for s in ast.walk(node)):
        return False
    if _has_io_side_effect(node):
        return False
    if _uses_mutable_default(node):
        return False
    # Must have at least one return statement with a non-None value
    returns = [s for s in ast.walk(node) if isinstance(s, ast.Return) and s.value is not None]
    if not returns:
        return False
    return True


class FunctoolsCacheInjection(BaseOperator):
    """Inject @functools.cache on eligible pure module-level functions.

    Complements MemoizationAddition (recursive only). This operator targets
    any pure function that would benefit from result caching.
    """

    name = "FunctoolsCacheInjection"
    family = "deterministic"
    tier = Tier.M
    targets_smells = frozenset(["C1", "C8"])
    precheck_node_types = (ast.FunctionDef,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.FunctionDef) and _is_cache_eligible(node)

    def _precheck_tree(self, tree: ast.AST, target: TargetSpec, context=None) -> bool:
        del context
        if not isinstance(tree, ast.Module):
            return False
        # Only top-level functions qualify (not class methods).
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and _is_cache_eligible(node):
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

        class Rewriter(ast.NodeTransformer):
            def visit_FunctionDef(self_inner, node: ast.FunctionDef):
                self_inner.generic_visit(node)
                if not _is_cache_eligible(node):
                    return node
                nonlocal changed
                changed = True
                node.decorator_list.insert(0, ast.Name(id="cache", ctx=ast.Load()))
                return node

        new_tree = Rewriter().visit(tree)
        if changed:
            ensure_import_from(new_tree, "functools", "cache")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Injected @functools.cache on eligible pure function(s) to avoid redundant recomputation.",
                dependencies=["functools"],
            )
        ]
