from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _eager_materialisation_precheck


class LazyEvaluationRewriteLLM(LLMTransformationOperator):
    name = "LazyEvaluationRewriteLLM"
    tier = Tier.M
    targets_smells = frozenset(["C6", "C10"])
    objective = "Rewrite eager processing into lazy evaluation pipeline to reduce memory pressure."
    precheck_node_types = (ast.Call, ast.ListComp)
    precheck_predicate = _eager_materialisation_precheck
