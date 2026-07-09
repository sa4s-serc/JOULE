from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _always_true


class GenerativeLLMOperator(LLMTransformationOperator):
    name = "llm_generative"
    tier = Tier.M
    targets_smells = frozenset(["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12"])
    objective = "Produce a high-quality optimization candidate with clear rationale."
    precheck_node_types = (ast.For, ast.While, ast.Call, ast.BinOp, ast.If)
    precheck_predicate = _always_true
