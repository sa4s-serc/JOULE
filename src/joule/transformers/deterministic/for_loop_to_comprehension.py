from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


def _references_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id == name for item in ast.walk(node))


class ForLoopToComprehension(BaseOperator):
    name = "ForLoopToComprehension"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.For,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        def append_arg(stmt: ast.stmt, list_name: str, depth: int = 0) -> tuple[ast.expr, list[ast.expr]] | None:
            if depth > 10:
                return None
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == list_name
                    and call.func.attr == "append"
                    and len(call.args) == 1
                    and not call.keywords
                ):
                    if _references_name(call.args[0], list_name):
                        return None
                    return call.args[0], []
            if isinstance(stmt, ast.If) and stmt.orelse == [] and len(stmt.body) == 1:
                nested = append_arg(stmt.body[0], list_name, depth + 1)
                if nested:
                    if _references_name(stmt.test, list_name):
                        return None
                    return nested[0], [stmt.test, *nested[1]]
            return None

        def rewrite_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
            nonlocal changed
            rewritten: list[ast.stmt] = []
            index = 0
            while index < len(statements):
                first = statements[index]
                second = statements[index + 1] if index + 1 < len(statements) else None
                if (
                    isinstance(first, ast.Assign)
                    and len(first.targets) == 1
                    and isinstance(first.targets[0], ast.Name)
                    and isinstance(first.value, ast.List)
                    and first.value.elts == []
                    and isinstance(second, ast.For)
                    and second.orelse == []
                    and len(second.body) == 1
                ):
                    list_name = first.targets[0].id
                    append = append_arg(second.body[0], list_name)
                    if append:
                        changed = True
                        comp = ast.ListComp(
                            elt=append[0],
                            generators=[
                                ast.comprehension(
                                    target=second.target,
                                    iter=second.iter,
                                    ifs=append[1],
                                    is_async=0,
                                )
                            ],
                        )
                        rewritten.append(ast.Assign(targets=first.targets, value=comp))
                        index += 2
                        continue
                rewritten.append(first)
                index += 1
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

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Collapsed append-based loops into list comprehensions.",
            )
        ]
