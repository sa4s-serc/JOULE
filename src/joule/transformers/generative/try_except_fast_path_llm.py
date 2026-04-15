from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _try_except_fast_path_candidate


class TryExceptFastPathLLM(LLMTransformationOperator):
    name = "TryExceptFastPathLLM"
    tier = Tier.M
    objective = "Restructure exception-heavy paths to keep common-case execution fast."
    precheck_node_types = (ast.Try,)
    precheck_predicate = _try_except_fast_path_candidate
