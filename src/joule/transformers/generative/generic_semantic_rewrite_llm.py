from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class GenericSemanticRewriteLLM(LLMTransformationOperator):
    name = "GenericSemanticRewriteLLM"
    tier = Tier.H
    escape_only = True
    objective = "Perform a broad semantic rewrite to escape local search minima while preserving correctness."
