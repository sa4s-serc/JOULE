from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class AlgorithmComplexityReduction(LLMTransformationOperator):
    name = "AlgorithmicComplexityReduction"
    tier = Tier.H
    objective = "Refactor algorithmic approach to reduce asymptotic complexity."
