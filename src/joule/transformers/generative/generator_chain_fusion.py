from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _call_has_generator_chain


class GeneratorChainFusion(LLMTransformationOperator):
    name = "GeneratorChainFusion"
    tier = Tier.M
    objective = "Fuse adjacent generator/list processing stages into a single lazy pipeline."
    precheck_node_types = (ast.Call, ast.ListComp, ast.GeneratorExp)
    precheck_predicate = _call_has_generator_chain
