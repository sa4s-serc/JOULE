from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _always_true


class GenerativeLLMOperator(LLMTransformationOperator):
    name = "llm_generative"
    tier = Tier.M
    objective = "Produce a high-quality optimization candidate with clear rationale."
    precheck_node_types = (ast.For, ast.While, ast.Call, ast.BinOp, ast.If)
    precheck_predicate = _always_true
