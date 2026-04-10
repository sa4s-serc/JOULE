from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class TryExceptFastPathLLM(LLMTransformationOperator):
    name = "TryExceptFastPathLLM"
    tier = Tier.M
    objective = "Restructure exception-heavy paths to keep common-case execution fast."
