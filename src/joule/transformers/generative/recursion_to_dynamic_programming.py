from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class RecursionToDynamicProgramming(LLMTransformationOperator):
    name = "RecursionToDynamicProgramming"
    tier = Tier.H
    objective = "Convert expensive recursive algorithms to dynamic-programming formulations."
