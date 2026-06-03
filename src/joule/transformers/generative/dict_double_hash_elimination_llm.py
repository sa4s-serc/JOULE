from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _if_has_dict_double_hash_pattern


class DictDoubleHashEliminationLLM(LLMTransformationOperator):
    name = "DictDoubleHashEliminationLLM"
    tier = Tier.M
    targets_smells = frozenset(["C5", "C8"])
    objective = "Eliminate repeated dictionary hash lookups by restructuring access patterns."
    precheck_node_types = (ast.If,)
    precheck_predicate = _if_has_dict_double_hash_pattern
