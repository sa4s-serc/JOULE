from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class GeneratorChainFusion(LLMTransformationOperator):
    name = "GeneratorChainFusion"
    tier = Tier.M
    objective = "Fuse adjacent generator/list processing stages into a single lazy pipeline."
