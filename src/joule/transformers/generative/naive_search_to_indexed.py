from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _naive_search_candidate


class NaiveSearchToIndexed(LLMTransformationOperator):
    name = "NaiveSearchToIndexed"
    tier = Tier.H
    targets_smells = frozenset(["C5", "C7"])
    objective = "Replace repeated naive searches with indexed lookup structures."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _naive_search_candidate
