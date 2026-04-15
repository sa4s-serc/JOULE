from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _regex_runtime_call


class RegexPrecompilationLLM(LLMTransformationOperator):
    name = "RegexPrecompilationLLM"
    tier = Tier.M
    objective = "Precompile regex usage to avoid repeated pattern compilation overhead."
    precheck_node_types = (ast.Call,)
    precheck_predicate = _regex_runtime_call
