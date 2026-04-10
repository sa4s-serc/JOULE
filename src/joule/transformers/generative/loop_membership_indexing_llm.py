from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class LoopMembershipIndexingLLM(LLMTransformationOperator):
    name = "LoopMembershipIndexingLLM"
    tier = Tier.H
    objective = "Replace repeated loop-time membership checks with indexed structures."
