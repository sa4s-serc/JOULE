from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator


def _itertools_delegate_precheck(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"zip", "map", "filter"}


class ItertoolsDelegateLLM(LLMTransformationOperator):
    name = "ItertoolsDelegateLLM"
    tier = Tier.M
    objective = "Delegate iterative composition to itertools primitives where beneficial."
    precheck_node_types = (ast.For, ast.Call)
    precheck_predicate = _itertools_delegate_precheck
