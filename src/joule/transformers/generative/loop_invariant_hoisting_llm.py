from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class LoopInvariantHoistingLLM(LLMTransformationOperator):
    name = "LoopInvariantHoistingLLM"
    tier = Tier.M
    objective = "Hoist loop-invariant computations out of hot loops."
