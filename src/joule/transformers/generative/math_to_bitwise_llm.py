from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _math_to_bitwise_candidate


class MathToBitwiseLLM(LLMTransformationOperator):
    name = "MathToBitwiseLLM"
    tier = Tier.M
    objective = "Convert safe arithmetic operations into equivalent bitwise operations where beneficial."
    precheck_node_types = (ast.BinOp,)
    precheck_predicate = _math_to_bitwise_candidate
