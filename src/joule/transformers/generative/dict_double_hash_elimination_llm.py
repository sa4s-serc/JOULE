from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class DictDoubleHashEliminationLLM(LLMTransformationOperator):
    name = "DictDoubleHashEliminationLLM"
    tier = Tier.M
    objective = "Eliminate repeated dictionary hash lookups by restructuring access patterns."
