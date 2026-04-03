from __future__ import annotations

import libcst as cst

from joule.models import TargetSpec


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
            return self.replacement.with_changes(
                leading_lines=updated_node.leading_lines,
                decorators=updated_node.decorators,
            )
        return updated_node


def replace_function_in_module(module_source: str, target: TargetSpec, candidate_function_source: str) -> str:
    module = cst.parse_module(module_source)
    candidate_module = cst.parse_module(candidate_function_source)
    replacement = next(statement for statement in candidate_module.body if isinstance(statement, cst.FunctionDef))
    updated = module.visit(FunctionReplacer(target, replacement))
    return updated.code
