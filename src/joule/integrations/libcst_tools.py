from __future__ import annotations

from collections.abc import Sequence

import libcst as cst

from joule.models import TargetSpec


def _render_statement(node: cst.SimpleStatementLine | cst.BaseCompoundStatement) -> str:
    return cst.Module(body=[node]).code.strip()


def _is_docstring_statement(stmt: cst.SimpleStatementLine | cst.BaseCompoundStatement) -> bool:
    if not isinstance(stmt, cst.SimpleStatementLine) or len(stmt.body) != 1:
        return False
    expr = stmt.body[0]
    return isinstance(expr, cst.Expr) and isinstance(expr.value, cst.SimpleString)


def _is_future_import(stmt: cst.SimpleStatementLine | cst.BaseCompoundStatement) -> bool:
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    if len(stmt.body) != 1 or not isinstance(stmt.body[0], cst.ImportFrom):
        return False
    import_from = stmt.body[0]
    return (
        import_from.module is not None
        and isinstance(import_from.module, cst.Name)
        and import_from.module.value == "__future__"
    )


def _insertion_index(body: Sequence[cst.SimpleStatementLine | cst.BaseCompoundStatement]) -> int:
    index = 0
    if body and _is_docstring_statement(body[0]):
        index = 1
    while index < len(body) and _is_future_import(body[index]):
        index += 1
    return index


class FunctionReplacer(cst.CSTTransformer):
    def __init__(self, target: TargetSpec, replacement: cst.FunctionDef) -> None:
        self.target = target
        self.replacement = replacement
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._class_stack.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        self._class_stack.pop()
        return updated_node

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        if self._class_stack == self.target.owner_path and original_node.name.value == self.target.function_name:
            return self.replacement.with_changes(leading_lines=updated_node.leading_lines)
        return updated_node


def replace_function_in_module(module_source: str, target: TargetSpec, candidate_function_source: str) -> str:
    module = cst.parse_module(module_source)
    candidate_module = cst.parse_module(candidate_function_source)
    replacement = next(statement for statement in candidate_module.body if isinstance(statement, cst.FunctionDef))
    updated = module.visit(FunctionReplacer(target, replacement))
    candidate_imports = [
        statement
        for statement in candidate_module.body
        if _is_future_import(statement)
        or (
            isinstance(statement, cst.SimpleStatementLine)
            and len(statement.body) == 1
            and isinstance(statement.body[0], (cst.Import, cst.ImportFrom))
        )
    ]
    if candidate_imports:
        existing = {_render_statement(statement) for statement in updated.body}
        additions = [statement for statement in candidate_imports if _render_statement(statement) not in existing]
        if additions:
            body = list(updated.body)
            insert_at = _insertion_index(body)
            body[insert_at:insert_at] = additions
            updated = updated.with_changes(body=body)
    return updated.code
