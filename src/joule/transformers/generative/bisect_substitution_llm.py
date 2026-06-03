from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator


def _bisect_substitution_precheck(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "index"


class BisectSubstitutionLLM(LLMTransformationOperator):
    name = "BisectSubstitutionLLM"
    tier = Tier.M
    targets_smells = frozenset(["C7", "C10"])
    objective = "Replace linear sorted-list searches with bisect-based indexing."
    precheck_node_types = (ast.Call, ast.For, ast.While)
    precheck_predicate = _bisect_substitution_precheck
