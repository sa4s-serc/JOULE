from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_arithmetic_candidate


class VectorizationDelegate(LLMTransformationOperator):
    name = "VectorizationDelegate[loop->numpy]"
    tier = Tier.H
    objective = "Vectorize numeric loops through NumPy-style operations when semantically safe."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_arithmetic_candidate
