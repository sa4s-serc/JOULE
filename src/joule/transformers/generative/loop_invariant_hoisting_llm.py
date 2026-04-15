from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator


def _loop_invariant_precheck(node: ast.AST) -> bool:
    return isinstance(node, (ast.For, ast.While)) and any(isinstance(child, ast.Call) for child in ast.walk(node))


class LoopInvariantHoistingLLM(LLMTransformationOperator):
    name = "LoopInvariantHoistingLLM"
    tier = Tier.M
    objective = "Hoist loop-invariant computations out of hot loops."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_invariant_precheck
