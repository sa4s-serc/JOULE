from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_has_early_exit


class EarlyExitOptimization(LLMTransformationOperator):
    name = "EarlyExitOptimization"
    tier = Tier.M
    targets_smells = frozenset(["C3", "C4"])
    objective = "Introduce semantically-safe early exits to avoid unnecessary work."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_has_early_exit
