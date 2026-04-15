from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _seen_set_dedup_pattern


class SeenSetDeduplicationLLM(LLMTransformationOperator):
    name = "SeenSetDeduplicationLLM"
    tier = Tier.H
    objective = "Introduce seen-set based deduplication for repeated append patterns."
    precheck_node_types = (ast.If,)
    precheck_predicate = _seen_set_dedup_pattern
