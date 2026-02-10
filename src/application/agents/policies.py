"""Stage policies and invariants for agentic flow."""

from __future__ import annotations

from typing import Dict, Any

from src.application.agents.protocol import AgentError, AgentRole


class StagePolicy:
    """Enforces cross-stage invariants."""

    REQUIRED_STAGE_ORDER = [
        "architecture",
        "semantic_contract",
        "strategy_generation",
        "implementation",
        "safety_review",
    ]

    def validate_order(self, stage_history: list[str]) -> None:
        for idx, stage in enumerate(stage_history):
            if idx >= len(self.REQUIRED_STAGE_ORDER):
                break
            expected = self.REQUIRED_STAGE_ORDER[idx]
            if stage != expected:
                raise AgentError(
                    stage=stage,
                    role=AgentRole.SENTINEL,
                    detail=f"Invalid stage order: expected '{expected}' before '{stage}'",
                )

    def validate_invariants(self, memory: Dict[str, Any], stage: str) -> None:
        if stage == "strategy_generation" and "semantic_contract" not in memory:
            raise AgentError(
                stage=stage,
                role=AgentRole.STRATEGIST,
                detail="semantic contract must exist before strategy generation",
            )

        if stage == "implementation" and "strategy_plan" not in memory:
            raise AgentError(
                stage=stage,
                role=AgentRole.ENGINEER,
                detail="strategy plan must exist before implementation",
            )
