from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class SlotsDelegateLLM(LLMTransformationOperator):
    name = "SlotsDelegateLLM"
    tier = Tier.M
    objective = "Introduce __slots__ in suitable classes to reduce attribute overhead and memory footprint."
