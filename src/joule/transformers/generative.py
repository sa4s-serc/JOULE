from __future__ import annotations

from joule.integrations.llm import LLMClient, LLMUnavailableError
from joule.models import TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class GenerativeLLMOperator(BaseOperator):
    name = "llm_generative"

    def __init__(self, model: str) -> None:
        self.client = LLMClient(model=model)

    def generate(self, target: TargetSpec) -> list[TransformationResult]:
        try:
            return [self.client.generate_transformation(target)]
        except LLMUnavailableError as exc:
            return [
                TransformationResult(
                    operator_name=self.name,
                    candidate_source=target.source,
                    reasoning=str(exc),
                    metadata={"skipped": True},
                )
            ]
