from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _call_has_generator_chain


class GeneratorChainFusion(LLMTransformationOperator):
    name = "GeneratorChainFusion"
    tier = Tier.M
    targets_smells = frozenset(["C6", "C10"])
    objective = "Fuse adjacent generator/list processing stages into a single lazy pipeline."
    precheck_node_types = (ast.Call, ast.ListComp, ast.GeneratorExp)
    precheck_predicate = _call_has_generator_chain
