from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_has_augassign_reduction


class ManualReductionToBuiltinsLLM(LLMTransformationOperator):
    name = "ManualReductionToBuiltinsLLM"
    tier = Tier.M
    targets_smells = frozenset(["C3", "C10"])
    objective = "Replace manual reduction loops with optimized Python builtins."
    precheck_node_types = (ast.For, ast.While)
    precheck_predicate = _loop_has_augassign_reduction
