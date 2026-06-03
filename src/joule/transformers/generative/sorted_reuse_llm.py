from __future__ import annotations

import ast
from collections import Counter

from joule.models import Tier

from .llm_base import LLMTransformationOperator


def _sorted_reuse_precheck(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    call_signatures = [
        ast.dump(call.args[0], annotate_fields=False, include_attributes=False)
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "sorted"
        and len(call.args) == 1
        and not call.keywords
    ]
    if not call_signatures:
        return False
    return any(count > 1 for count in Counter(call_signatures).values())


class SortedReuseLLM(LLMTransformationOperator):
    name = "SortedReuseLLM"
    tier = Tier.M
    targets_smells = frozenset(["C1", "C8"])
    objective = "Hoist repeated sorted(...) computations so sorted inputs are materialized once and reused."
    precheck_node_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Call)
    precheck_predicate = _sorted_reuse_precheck
