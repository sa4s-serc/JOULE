from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class ItertoolsDelegateLLM(LLMTransformationOperator):
    name = "ItertoolsDelegateLLM"
    tier = Tier.M
    objective = "Delegate iterative composition to itertools primitives where beneficial."
