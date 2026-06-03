from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_has_membership_check


class LoopMembershipIndexingLLM(LLMTransformationOperator):
    name = "LoopMembershipIndexingLLM"
    tier = Tier.H
    targets_smells = frozenset(["C3", "C5", "C8"])
    objective = "Replace repeated loop-time membership checks with indexed structures."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_has_membership_check
