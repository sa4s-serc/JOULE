from __future__ import annotations

import json
import os
from textwrap import dedent

from joule.models import TargetSpec, TransformationResult


class LLMUnavailableError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate_transformation(self, target: TargetSpec) -> TransformationResult:
        fake_response = os.getenv("JOULE_FAKE_LLM_RESPONSE")
        if fake_response:
            payload = json.loads(fake_response)
            return TransformationResult(
                operator_name="llm_generative",
                candidate_source=payload["candidate_source"],
                reasoning=payload.get("reasoning", "LLM-generated optimization"),
                dependencies=payload.get("dependencies", []),
                metadata={"source": "fake-env"},
            )
        if not self.model:
            raise LLMUnavailableError("No LLM model configured. Set [tool.joule].llm_model or JOULE_LLM_MODEL.")
        try:
            from litellm import completion
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMUnavailableError("litellm is not installed; set JOULE_FAKE_LLM_RESPONSE for tests.") from exc

        prompt = dedent(
            f"""
            Optimize the following Python function for energy, latency, and memory.
            Return strict JSON with keys: candidate_source, reasoning, dependencies.

            {target.source}
            """
        ).strip()
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        payload = json.loads(content)
        return TransformationResult(
            operator_name="llm_generative",
            candidate_source=payload["candidate_source"],
            reasoning=payload.get("reasoning", "LLM-generated optimization"),
            dependencies=payload.get("dependencies", []),
            metadata={"model": self.model},
        )
