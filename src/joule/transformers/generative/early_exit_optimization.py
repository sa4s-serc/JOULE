from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class EarlyExitOptimization(LLMTransformationOperator):
    name = "EarlyExitOptimization"
    tier = Tier.M
    objective = "Introduce semantically-safe early exits to avoid unnecessary work."
