from __future__ import annotations

import ast

from joule.models import Tier

from .llm_base import LLMTransformationOperator, _class_without_slots


class SlotsDelegateLLM(LLMTransformationOperator):
    name = "SlotsDelegateLLM"
    tier = Tier.M
    targets_smells = frozenset(["C5", "C6"])
    objective = "Introduce __slots__ in suitable classes to reduce attribute overhead and memory footprint."
    precheck_node_types = (ast.ClassDef,)
    precheck_predicate = _class_without_slots
