from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _always_true


class GenericSemanticRewriteLLM(LLMTransformationOperator):
    name = "GenericSemanticRewriteLLM"
    tier = Tier.H
    escape_only = True
    objective = "Perform a broad semantic rewrite to escape local search minima while preserving correctness."
    precheck_node_types = (ast.For, ast.While, ast.Call, ast.BinOp, ast.If)
    precheck_predicate = _always_true
