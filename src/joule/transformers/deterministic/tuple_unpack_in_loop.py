from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _unpack_prefix(node: ast.For) -> tuple[list[str], int] | None:
    if not isinstance(node.target, ast.Name):
        return None
    loop_name = node.target.id
    pairs: list[tuple[int, str]] = []
    for stmt in node.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            break
        if not (
            isinstance(stmt.value, ast.Subscript)
            and isinstance(stmt.value.value, ast.Name)
            and stmt.value.value.id == loop_name
            and isinstance(stmt.value.slice, ast.Constant)
            and isinstance(stmt.value.slice.value, int)
            and stmt.value.slice.value >= 0
        ):
            break
        pairs.append((stmt.value.slice.value, stmt.targets[0].id))
    if len(pairs) < 2:
        return None
    indexes = [idx for idx, _ in pairs]
    if len(set(indexes)) != len(indexes) or sorted(indexes) != list(range(len(indexes))):
        return None
    ordered_targets = [name for _, name in sorted(pairs)]
    if len(set(ordered_targets)) != len(ordered_targets):
        return None

    remaining = node.body[len(pairs) :]
    for stmt in remaining:
        for nested in ast.walk(stmt):
            if isinstance(nested, ast.Name) and isinstance(nested.ctx, ast.Load) and nested.id == loop_name:
                return None

    return ordered_targets, len(pairs)


class TupleUnpackInLoop(BaseOperator):
    name = "TupleUnpackInLoop"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.For,)

    def _precheck_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.For) and _unpack_prefix(node) is not None

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_For(self, node: ast.For):
                nonlocal changed
                self.generic_visit(node)
                prefix = _unpack_prefix(node)
                if prefix is None:
                    return node
                names, consumed = prefix
                changed = True
                node.target = ast.Tuple(
                    elts=[ast.Name(id=name, ctx=ast.Store()) for name in names],
                    ctx=ast.Store(),
                )
                node.body = node.body[consumed:] or [ast.Pass()]
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Converted tuple indexing inside loops into direct tuple unpacking.",
            )
        ]
