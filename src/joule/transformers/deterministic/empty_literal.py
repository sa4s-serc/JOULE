from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _builtin_shadowed(tree: ast.AST, *, names: set[str]) -> bool:
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
            bound.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bound.add(alias.asname)
                else:
                    bound.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound.add(alias.asname or alias.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
    return any(name in bound for name in names)


class EmptyLiteralOperator(BaseOperator):
    name = "empty_literal"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.Call,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        if _builtin_shadowed(tree, names={"list", "dict"}):
            return []
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and not node.args and not node.keywords:
                    if node.func.id == "list":
                        changed = True
                        return ast.List(elts=[], ctx=ast.Load())
                    if node.func.id == "dict":
                        changed = True
                        return ast.Dict(keys=[], values=[])
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced zero-argument constructor calls with literal forms.",
            )
        ]
