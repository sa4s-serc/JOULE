from __future__ import annotations

from joule.models import Tier

from .llm_base import LLMTransformationOperator


class RegexPrecompilationLLM(LLMTransformationOperator):
    name = "RegexPrecompilationLLM"
    tier = Tier.M
    objective = "Precompile regex usage to avoid repeated pattern compilation overhead."
