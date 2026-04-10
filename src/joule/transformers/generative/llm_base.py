from __future__ import annotations

import ast

from joule.integrations.llm import LLMClient, LLMUnavailableError
from joule.models import SearchContext, TargetSpec, Tier, TransformationResult
from joule.transformers.base import BaseOperator


class LLMTransformationOperator(BaseOperator):
    family = "llm"
    tier = Tier.M
    objective = "Generate a semantics-preserving optimization candidate."
    precheck_node_types = (ast.FunctionDef, ast.AsyncFunctionDef)

    def __init__(self, model: str) -> None:
        self.client = LLMClient(model=model)

    def generate(self, target: TargetSpec, context: SearchContext | None = None) -> list[TransformationResult]:
        try:
            generated = self.client.generate_transformation(
                target,
                context,
                operator_name=self.name,
                objective=self.objective,
                operator_tier=self.tier,
            )
        except LLMUnavailableError as exc:
            return [
                self.build_result(
                    candidate_source=target.source,
                    reasoning=str(exc),
                    proposal_rank=100,
                    metadata={"skipped": True, "llm_unavailable": True},
                )
            ]
        except Exception as exc:
            return [
                self.build_result(
                    candidate_source=target.source,
                    reasoning=f"LLM generation failed: {exc}",
                    proposal_rank=100,
                    metadata={"skipped": True, "llm_error": True},
                )
            ]

        candidate = generated.candidate_source.strip()
        if not candidate:
            return [
                self.build_result(
                    candidate_source=target.source,
                    reasoning="LLM returned an empty candidate.",
                    proposal_rank=100,
                    metadata={"skipped": True, "llm_invalid_output": True},
                )
            ]
        try:
            ast.parse(generated.candidate_source)
        except SyntaxError as exc:
            return [
                self.build_result(
                    candidate_source=target.source,
                    reasoning=f"LLM candidate failed syntax validation: {exc.msg}",
                    proposal_rank=100,
                    metadata={"skipped": True, "llm_invalid_syntax": True},
                )
            ]

        generated.operator_name = self.name
        generated.operator_family = self.family
        generated.operator_tier = self.tier
        generated.metadata.setdefault("operator_tier", self.tier.value)
        generated.metadata.setdefault("operator_tier_descriptor", self.tier_description())
        return [generated]
