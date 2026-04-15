from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _function_has_recursive_call


def _recursion_to_dp_precheck(node: ast.AST) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _function_has_recursive_call(node)
    return isinstance(node, ast.Call)


class RecursionToDynamicProgramming(LLMTransformationOperator):
    name = "RecursionToDynamicProgramming"
    tier = Tier.H
    objective = "Convert expensive recursive algorithms to dynamic-programming formulations."
    precheck_node_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Call)
    precheck_predicate = _recursion_to_dp_precheck
