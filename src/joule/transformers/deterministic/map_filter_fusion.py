from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _single_name(node: ast.expr) -> str | None:
    """Return the name id if node is a simple ast.Name, regardless of context."""
    if isinstance(node, ast.Name):
        return node.id
    return None


def _references_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id == name
        for item in ast.walk(node)
    )


def _simple_call_expr(node: ast.expr) -> bool:
    """True when node is a simple function call with a single name as the callable."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
        and len(node.args) == 1
        and not node.keywords
        and not node.starargs if hasattr(node, "starargs") else True
    )


def _try_map_fusion(
    init_stmt: ast.Assign,
    for_stmt: ast.For,
) -> ast.Assign | None:
    """
    Detect pattern:
        result = []
        for x in iterable:
            result.append(f(x))

    Rewrite to:
        result = list(map(f, iterable))

    Returns new assignment node or None if pattern doesn't match.
    """
    # Init must be `name = []`
    if (
        len(init_stmt.targets) != 1
        or not isinstance(init_stmt.targets[0], ast.Name)
        or not isinstance(init_stmt.value, ast.List)
        or init_stmt.value.elts
    ):
        return None

    list_name = init_stmt.targets[0].id

    # For body must be exactly one statement: result.append(expr)
    if len(for_stmt.body) != 1 or for_stmt.orelse:
        return None
    body_stmt = for_stmt.body[0]
    if not isinstance(body_stmt, ast.Expr):
        return None
    call = body_stmt.value
    if (
        not isinstance(call, ast.Call)
        or not isinstance(call.func, ast.Attribute)
        or not isinstance(call.func.value, ast.Name)
        or call.func.value.id != list_name
        or call.func.attr != "append"
        or len(call.args) != 1
        or call.keywords
    ):
        return None

    append_arg = call.args[0]

    # The appended expression must not reference the accumulator
    if _references_name(append_arg, list_name):
        return None

    # The loop target must be a simple name
    loop_var = _single_name(for_stmt.target)
    if loop_var is None:
        return None

    # append_arg must be a call of a simple function applied to the loop variable
    # e.g. f(x) where x is the loop variable — ensures map(f, iterable) is valid
    if not (
        isinstance(append_arg, ast.Call)
        and len(append_arg.args) == 1
        and not append_arg.keywords
        and isinstance(append_arg.args[0], ast.Name)
        and append_arg.args[0].id == loop_var
    ):
        return None

    func_node = append_arg.func

    # Build: result = list(map(f, iterable))
    map_call = ast.Call(
        func=ast.Name(id="map", ctx=ast.Load()),
        args=[func_node, for_stmt.iter],
        keywords=[],
    )
    list_call = ast.Call(
        func=ast.Name(id="list", ctx=ast.Load()),
        args=[map_call],
        keywords=[],
    )
    return ast.Assign(targets=init_stmt.targets, value=list_call)


def _try_filter_fusion(
    init_stmt: ast.Assign,
    for_stmt: ast.For,
) -> ast.Assign | None:
    """
    Detect pattern:
        result = []
        for x in iterable:
            if predicate(x):
                result.append(x)

    Rewrite to:
        result = list(filter(predicate, iterable))
    """
    if (
        len(init_stmt.targets) != 1
        or not isinstance(init_stmt.targets[0], ast.Name)
        or not isinstance(init_stmt.value, ast.List)
        or init_stmt.value.elts
    ):
        return None

    list_name = init_stmt.targets[0].id

    # For body must be exactly: if pred(x): result.append(x)
    if len(for_stmt.body) != 1 or for_stmt.orelse:
        return None

    if_stmt = for_stmt.body[0]
    if not isinstance(if_stmt, ast.If) or if_stmt.orelse:
        return None
    if len(if_stmt.body) != 1:
        return None

    append_stmt = if_stmt.body[0]
    if not isinstance(append_stmt, ast.Expr):
        return None
    append_call = append_stmt.value
    if (
        not isinstance(append_call, ast.Call)
        or not isinstance(append_call.func, ast.Attribute)
        or not isinstance(append_call.func.value, ast.Name)
        or append_call.func.value.id != list_name
        or append_call.func.attr != "append"
        or len(append_call.args) != 1
        or append_call.keywords
    ):
        return None

    loop_var = _single_name(for_stmt.target)
    if loop_var is None:
        return None

    # append argument must be exactly the loop variable
    if not (isinstance(append_call.args[0], ast.Name) and append_call.args[0].id == loop_var):
        return None

    # Predicate must be a simple call of the loop variable
    pred = if_stmt.test
    if not (
        isinstance(pred, ast.Call)
        and len(pred.args) == 1
        and not pred.keywords
        and isinstance(pred.args[0], ast.Name)
        and pred.args[0].id == loop_var
    ):
        return None

    func_node = pred.func

    # Build: result = list(filter(predicate, iterable))
    filter_call = ast.Call(
        func=ast.Name(id="filter", ctx=ast.Load()),
        args=[func_node, for_stmt.iter],
        keywords=[],
    )
    list_call = ast.Call(
        func=ast.Name(id="list", ctx=ast.Load()),
        args=[filter_call],
        keywords=[],
    )
    return ast.Assign(targets=init_stmt.targets, value=list_call)


def _rewrite_block(stmts: list[ast.stmt]) -> tuple[list[ast.stmt], bool]:
    result: list[ast.stmt] = []
    changed = False
    i = 0
    while i < len(stmts):
        stmt = stmts[i]
        nxt = stmts[i + 1] if i + 1 < len(stmts) else None
        if isinstance(stmt, ast.Assign) and isinstance(nxt, ast.For):
            fused = _try_map_fusion(stmt, nxt) or _try_filter_fusion(stmt, nxt)
            if fused is not None:
                result.append(fused)
                changed = True
                i += 2
                continue
        result.append(stmt)
        i += 1
    return result, changed


class MapFilterFusion(BaseOperator):
    """Replace trivial for-loop accumulations with map() or filter() calls.

    Targets patterns where a loop body is a single append of a transformed or
    filtered element into a list initialized just before the loop.

    Examples::

        # map fusion
        result = []
        for x in items:
            result.append(transform(x))
        # becomes:
        result = list(map(transform, items))

        # filter fusion
        result = []
        for x in items:
            if keep(x):
                result.append(x)
        # becomes:
        result = list(filter(keep, items))
    """

    name = "MapFilterFusion"
    family = "deterministic"
    tier = Tier.L
    targets_smells = frozenset(["C3", "C10"])
    precheck_node_types = (ast.For,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []

        overall_changed = False

        class Rewriter(ast.NodeTransformer):
            def _rewrite_body(self_inner, body: list[ast.stmt]) -> list[ast.stmt]:
                nonlocal overall_changed
                new_body, changed = _rewrite_block(body)
                if changed:
                    overall_changed = True
                # Recurse into each statement
                return [self_inner.visit(s) for s in new_body]

            def visit_Module(self_inner, node: ast.Module):
                node.body = self_inner._rewrite_body(node.body)
                return node

            def visit_FunctionDef(self_inner, node: ast.FunctionDef):
                node.body = self_inner._rewrite_body(node.body)
                return node

            def visit_AsyncFunctionDef(self_inner, node: ast.AsyncFunctionDef):
                node.body = self_inner._rewrite_body(node.body)
                return node

            def visit_For(self_inner, node: ast.For):
                node.body = self_inner._rewrite_body(node.body)
                return node

            def visit_While(self_inner, node: ast.While):
                node.body = self_inner._rewrite_body(node.body)
                return node

            def visit_If(self_inner, node: ast.If):
                node.body = self_inner._rewrite_body(node.body)
                node.orelse = self_inner._rewrite_body(node.orelse)
                return node

            def visit_With(self_inner, node: ast.With):
                node.body = self_inner._rewrite_body(node.body)
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not overall_changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced trivial for-loop accumulations with map() or filter() calls.",
            )
        ]
