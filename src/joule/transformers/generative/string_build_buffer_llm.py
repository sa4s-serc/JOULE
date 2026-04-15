from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator


def _string_buffer_precheck(node: ast.AST) -> bool:
    return isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)


class StringBuildBufferLLM(LLMTransformationOperator):
    name = "StringBuildBufferLLM"
    tier = Tier.M
    objective = "Rewrite repeated string concatenation to buffered construction patterns."
    precheck_node_types = (ast.For, ast.While, ast.AugAssign)
    precheck_predicate = _string_buffer_precheck
