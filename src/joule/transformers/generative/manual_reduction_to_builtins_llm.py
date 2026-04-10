from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class ManualReductionToBuiltinsLLM(LLMTransformationOperator):
    name = "ManualReductionToBuiltinsLLM"
    tier = Tier.M
    objective = "Replace manual reduction loops with optimized Python builtins."
