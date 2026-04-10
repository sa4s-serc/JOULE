from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class ConcurrentMapDelegateLLM(LLMTransformationOperator):
    name = "ConcurrentMapDelegateLLM"
    tier = Tier.M
    objective = "Parallelize independent map-style workloads where concurrency is beneficial and safe."
