from __future__ import annotations

from importlib import import_module
import json
import os
from textwrap import dedent
from typing import Any, cast

from joule.models import SearchContext, TargetSpec, Tier, TransformationResult, normalize_tier, tier_descriptor


class LLMUnavailableError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def generate_transformation(
        self,
        target: TargetSpec,
        context: SearchContext | None = None,
        *,
        operator_name: str = "llm_generative",
        objective: str = "Generate an optimization candidate.",
        operator_tier: Tier | str = Tier.M,
    ) -> TransformationResult:
        tier_value = normalize_tier(operator_tier)
        fake_response = os.getenv("JOULE_FAKE_LLM_RESPONSE")
        if fake_response:
            payload = json.loads(fake_response)
            if isinstance(payload, dict) and operator_name in payload and isinstance(payload[operator_name], dict):
                payload = payload[operator_name]
            return TransformationResult(
                operator_name=operator_name,
                candidate_source=payload.get("candidate_source", target.source),
                reasoning=payload.get("reasoning", "LLM-generated optimization"),
                dependencies=payload.get("dependencies", []),
                operator_family="llm",
                operator_tier=tier_value,
                proposal_rank=int(payload.get("proposal_rank", 0)),
                feature_hints=payload.get("feature_hints", {}),
                metadata={
                    "source": "fake-env",
                    "operator_tier": tier_value.value,
                    "operator_tier_descriptor": tier_descriptor(tier_value),
                    "objective": objective,
                    "context": context.to_record() if context else {},
                },
            )
        if not self.model:
            raise LLMUnavailableError("No LLM model configured. Set [tool.joule].llm_model or JOULE_LLM_MODEL.")
        try:
            completion = cast(Any, import_module("litellm")).completion
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMUnavailableError("litellm is not installed; set JOULE_FAKE_LLM_RESPONSE for tests.") from exc

        context_block = ""
        if context is not None:
            context_block = dedent(
                f"""
                Parent id: {context.parent_id}
                Parent operator: {context.parent_operator_name}
                Generation depth: {context.generation_depth}
                Search phase: {context.phase.value}
                Recent rejection reasons: {', '.join(context.rejection_history) or 'none'}
                Parent source:
                {context.parent_source}
                """
            ).strip()
        prompt = dedent(
            f"""
            Optimize the following Python function for energy, latency, and memory.
            Transformation operator: {operator_name}
            Tier: {tier_value.value} ({tier_descriptor(tier_value)})
            Objective: {objective}
            Return strict JSON with keys: candidate_source, reasoning, dependencies, proposal_rank, feature_hints.

            {context_block}

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
            operator_name=operator_name,
            candidate_source=payload["candidate_source"],
            reasoning=payload.get("reasoning", "LLM-generated optimization"),
            dependencies=payload.get("dependencies", []),
            operator_family="llm",
            operator_tier=tier_value,
            proposal_rank=int(payload.get("proposal_rank", 0)),
            feature_hints=payload.get("feature_hints", {}),
            metadata={
                "model": self.model,
                "objective": objective,
                "operator_tier": tier_value.value,
                "operator_tier_descriptor": tier_descriptor(tier_value),
                "context": context.to_record() if context else {},
            },
        )
