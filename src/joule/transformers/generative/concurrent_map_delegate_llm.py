from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _loop_has_append_call


def _concurrent_map_precheck(node: ast.AST) -> bool:
    return _loop_has_append_call(node) if isinstance(node, ast.For) else False


class ConcurrentMapDelegateLLM(LLMTransformationOperator):
    name = "ConcurrentMapDelegateLLM"
    tier = Tier.M
    objective = "Parallelize independent map-style workloads where concurrency is beneficial and safe."
    precheck_node_types = (ast.For, ast.ListComp, ast.GeneratorExp)
    precheck_predicate = _concurrent_map_precheck
