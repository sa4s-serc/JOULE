from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_contains_nested_loop


class AlgorithmComplexityReduction(LLMTransformationOperator):
    name = "AlgorithmicComplexityReduction"
    tier = Tier.H
    targets_smells = frozenset(["C7"])
    objective = "Refactor algorithmic approach to reduce asymptotic complexity."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_contains_nested_loop
