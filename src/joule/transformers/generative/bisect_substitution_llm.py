from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class BisectSubstitutionLLM(LLMTransformationOperator):
    name = "BisectSubstitutionLLM"
    tier = Tier.M
    objective = "Replace linear sorted-list searches with bisect-based indexing."
