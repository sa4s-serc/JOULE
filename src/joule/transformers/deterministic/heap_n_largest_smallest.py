from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator

from ._shared import ensure_import


def _sorted_slice_pattern(node: ast.Subscript) -> tuple[str, ast.expr, ast.expr, ast.expr | None] | None:
    if not isinstance(node.slice, ast.Slice) or node.slice.lower is not None or node.slice.step is not None:
        return None
    k_value = node.slice.upper
    if k_value is None:
        return None

    call = node.value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "sorted"
        and len(call.args) == 1
    ):
        return None

    reverse = False
    key_value: ast.expr | None = None
    for keyword in call.keywords:
        if keyword.arg == "reverse":
            if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, bool):
                return None
            reverse = bool(keyword.value.value)
        elif keyword.arg == "key":
            key_value = keyword.value
        else:
            return None

    method = "nlargest" if reverse else "nsmallest"
    return method, k_value, call.args[0], key_value


class HeapNLargestSmallest(BaseOperator):
    name = "HeapNLargestSmallest"
    family = "deterministic"
    tier = Tier.H
    precheck_node_types = (ast.Subscript,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Subscript) and _sorted_slice_pattern(node) is not None

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Subscript(self, node: ast.Subscript):
                nonlocal changed
                self.generic_visit(node)
                pattern = _sorted_slice_pattern(node)
                if pattern is None:
                    return node
                changed = True
                method, k_value, iterable, key_value = pattern
                keywords = [ast.keyword(arg="key", value=key_value)] if key_value is not None else []
                return ast.copy_location(
                    ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="heapq", ctx=ast.Load()),
                            attr=method,
                            ctx=ast.Load(),
                        ),
                        args=[k_value, iterable],
                        keywords=keywords,
                    ),
                    node,
                )

        new_tree = Rewriter().visit(tree)
        if changed and isinstance(new_tree, ast.Module):
            ensure_import(new_tree, "heapq")
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced sorted(... )[:k] with heapq.nsmallest/nlargest for top-k selection.",
                dependencies=["heapq"],
            )
        ]
