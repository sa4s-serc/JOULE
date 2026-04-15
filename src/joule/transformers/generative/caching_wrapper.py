from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _function_has_repeated_calls


def _caching_wrapper_precheck(node: ast.AST) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _function_has_repeated_calls(node)
    return isinstance(node, ast.Call)


class CachingWrapper(LLMTransformationOperator):
    name = "CachingWrapper"
    tier = Tier.M
    objective = "Wrap repeated deterministic computations in bounded caching strategy."
    precheck_node_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Call)
    precheck_predicate = _caching_wrapper_precheck
