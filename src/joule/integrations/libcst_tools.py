from __future__ import annotations

import libcst as cst


class FunctionReplacer(cst.CSTTransformer):
    def __init__(self, function_name: str, replacement: cst.FunctionDef) -> None:
        self.function_name = function_name
        self.replacement = replacement

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        if original_node.name.value == self.function_name:
            return self.replacement.with_changes(leading_lines=updated_node.leading_lines)
        return updated_node


def replace_function_in_module(module_source: str, function_name: str, candidate_function_source: str) -> str:
    module = cst.parse_module(module_source)
    candidate_module = cst.parse_module(candidate_function_source)
    replacement = next(statement for statement in candidate_module.body if isinstance(statement, cst.FunctionDef))
    updated = module.visit(FunctionReplacer(function_name, replacement))
    return updated.code
