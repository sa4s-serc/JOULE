from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class VectorizationDelegate(LLMTransformationOperator):
    name = "VectorizationDelegate[loop->numpy]"
    tier = Tier.H
    objective = "Vectorize numeric loops through NumPy-style operations when semantically safe."
