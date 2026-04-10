from __future__ import annotations

from joule.integrations.llm import LLMClient, LLMUnavailableError
from joule.models import SearchContext, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class GenerativeLLMOperator(BaseOperator):
    name = "llm_generative"
    family = "llm"

    def __init__(self, model: str) -> None:
        self.client = LLMClient(model=model)

    def generate(self, target: TargetSpec, context: SearchContext | None = None) -> list[TransformationResult]:
        try:
            generated = self.client.generate_transformation(target, context)
            generated.operator_name = self.name
            generated.operator_family = self.family
            return [generated]
        except LLMUnavailableError as exc:
            return [
                TransformationResult(
                    operator_name=self.name,
                    candidate_source=target.source,
                    reasoning=str(exc),
                    operator_family=self.family,
                    metadata={"skipped": True},
                )
            ]
