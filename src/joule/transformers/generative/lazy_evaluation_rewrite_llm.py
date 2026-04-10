from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class LazyEvaluationRewriteLLM(LLMTransformationOperator):
    name = "LazyEvaluationRewriteLLM"
    tier = Tier.M
    objective = "Rewrite eager processing into lazy evaluation pipeline to reduce memory pressure."
