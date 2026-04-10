from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class SeenSetDeduplicationLLM(LLMTransformationOperator):
    name = "SeenSetDeduplicationLLM"
    tier = Tier.H
    objective = "Introduce seen-set based deduplication for repeated append patterns."
