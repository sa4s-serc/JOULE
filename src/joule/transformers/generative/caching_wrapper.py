from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class CachingWrapper(LLMTransformationOperator):
    name = "CachingWrapper"
    tier = Tier.M
    objective = "Wrap repeated deterministic computations in bounded caching strategy."
