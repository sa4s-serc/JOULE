from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class GenerativeLLMOperator(LLMTransformationOperator):
    name = "llm_generative"
    tier = Tier.M
    objective = "Produce a high-quality optimization candidate with clear rationale."
