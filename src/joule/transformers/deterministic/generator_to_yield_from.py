from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _can_rewrite_for(stmt: ast.stmt) -> tuple[bool, str | None]:
    if not isinstance(stmt, ast.For) or stmt.orelse or len(stmt.body) != 1:
        return False, None
    body_stmt = stmt.body[0]
    if not (isinstance(body_stmt, ast.Expr) and isinstance(body_stmt.value, ast.Yield)):
        return False, None
    yielded = body_stmt.value.value
    if not (isinstance(stmt.target, ast.Name) and isinstance(yielded, ast.Name) and yielded.id == stmt.target.id):
        return False, None
    return True, stmt.target.id


def _loads_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id == name for item in ast.walk(node))


class GeneratorToYieldFrom(BaseOperator):
    name = "GeneratorToYieldFrom"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.For,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return []
        changed = False

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed
            rewritten: list[ast.stmt] = []
            for index, stmt in enumerate(statements):
                ok, target_name = _can_rewrite_for(stmt)
                if ok and target_name is not None:
                    later_uses_target = any(_loads_name(follow, target_name) for follow in statements[index + 1 :])
                    if not later_uses_target:
                        changed = True
                        for_stmt = stmt if isinstance(stmt, ast.For) else None
                        if for_stmt is not None:
                            rewritten.append(ast.copy_location(ast.Expr(value=ast.YieldFrom(value=for_stmt.iter)), for_stmt))
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
                reasoning="Replaced pass-through generator loop with yield from.",
            )
        ]
