from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class StringBuildBufferLLM(LLMTransformationOperator):
    name = "StringBuildBufferLLM"
    tier = Tier.M
    objective = "Rewrite repeated string concatenation to buffered construction patterns."
