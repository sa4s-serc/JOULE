from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class NaiveSearchToIndexed(LLMTransformationOperator):
    name = "NaiveSearchToIndexed"
    tier = Tier.H
    objective = "Replace repeated naive searches with indexed lookup structures."
