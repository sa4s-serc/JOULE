from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class MathToBitwiseLLM(LLMTransformationOperator):
    name = "MathToBitwiseLLM"
    tier = Tier.M
    objective = "Convert safe arithmetic operations into equivalent bitwise operations where beneficial."
