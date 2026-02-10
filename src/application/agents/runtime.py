"""Agentic runtime for staged optimization execution."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from src.application.agents.base import Agent
from src.application.agents.policies import StagePolicy
from src.application.agents.protocol import AgentContext, AgentError, AgentMessage, AgentResult, AgentRole
from src.application.agents.registry import AgentRegistry


class _ArchitectAgent(Agent):
    @property
    def name(self) -> str:
        return "default_architect"

    @property
    def role(self) -> AgentRole:
        return AgentRole.ARCHITECT

    @property
    def input_schema(self) -> Dict[str, type]:
        return {"initial_code": str, "test_code": str}

    @property
    def output_schema(self) -> Dict[str, type]:
        return {"semantic_contract": dict}

    def run(self, context: AgentContext) -> AgentResult:
        contract = {
            "must_preserve_behavior": True,
            "target": "energy_joules,duration_seconds",
        }
        return AgentResult(success=True, payload={"semantic_contract": contract})


class _StrategistAgent(Agent):
    @property
    def name(self) -> str:
        return "default_strategist"

    @property
    def role(self) -> AgentRole:
        return AgentRole.STRATEGIST

    @property
    def input_schema(self) -> Dict[str, type]:
        return {"semantic_contract": dict}

    @property
    def output_schema(self) -> Dict[str, type]:
        return {"strategy_plan": list}

    def run(self, context: AgentContext) -> AgentResult:
        plan = ["prefer low-risk mutators first", "expand to semantic mutators if stagnant"]
        return AgentResult(success=True, payload={"strategy_plan": plan})


class _EngineerAgent(Agent):
    @property
    def name(self) -> str:
        return "default_engineer"

    @property
    def role(self) -> AgentRole:
        return AgentRole.ENGINEER

    @property
    def input_schema(self) -> Dict[str, type]:
        return {"initial_code": str, "strategy_plan": list}

    @property
    def output_schema(self) -> Dict[str, type]:
        return {"candidate_code": str}

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, payload={"candidate_code": context.inputs["initial_code"]})


class _SentinelAgent(Agent):
    @property
    def name(self) -> str:
        return "default_sentinel"

    @property
    def role(self) -> AgentRole:
        return AgentRole.SENTINEL

    @property
    def input_schema(self) -> Dict[str, type]:
        return {"candidate_code": str, "semantic_contract": dict}

    @property
    def output_schema(self) -> Dict[str, type]:
        return {"approved": bool}

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, payload={"approved": True})


class AgentRuntime:
    """Coordinator that runs role-ordered agent graph with schema checks."""

    STAGES = [
        ("architecture", AgentRole.ARCHITECT),
        ("semantic_contract", AgentRole.ARCHITECT),
        ("strategy_generation", AgentRole.STRATEGIST),
        ("implementation", AgentRole.ENGINEER),
        ("safety_review", AgentRole.SENTINEL),
    ]

    def __init__(
        self,
        registry: AgentRegistry,
        event_emitter: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        policy: Optional[StagePolicy] = None,
    ):
        self.registry = registry
        self.event_emitter = event_emitter
        self.policy = policy or StagePolicy()

    def execute(self, initial_code: str, test_code: str) -> Dict[str, Any]:
        context = AgentContext(inputs={"initial_code": initial_code, "test_code": test_code})
        stage_history: List[str] = []

        for stage_name, role in self.STAGES:
            self.policy.validate_invariants(context.memory, stage_name)
            self._emit_stage_event("stage_started", stage_name, role, {"memory_keys": list(context.memory.keys())})

            agents = self.registry.get_by_role(role)
            if not agents:
                raise AgentError(stage=stage_name, role=role, detail="no registered agent for role")

            result = self._run_agent(agents[0], stage_name, context)
            context.memory.update(result.payload)
            stage_history.append(stage_name)
            self.policy.validate_order(stage_history)
            self._emit_stage_event("stage_completed", stage_name, role, result.payload)

        return context.memory

    def _run_agent(self, agent: Agent, stage_name: str, context: AgentContext) -> AgentResult:
        self._validate_schema(agent.input_schema, {**context.inputs, **context.memory}, stage_name, agent.role, "input")
        result = agent.run(context)
        if not result.success:
            raise AgentError(stage=stage_name, role=agent.role, detail="agent returned unsuccessful result")
        self._validate_schema(agent.output_schema, result.payload, stage_name, agent.role, "output")

        result.message = AgentMessage(
            role=agent.role,
            stage=stage_name,
            payload=result.payload,
            correlation_id=str(uuid.uuid4()),
        )
        return result

    def _validate_schema(
        self,
        schema: Dict[str, type],
        payload: Dict[str, Any],
        stage_name: str,
        role: AgentRole,
        schema_name: str,
    ) -> None:
        for key, expected_type in schema.items():
            if key not in payload:
                raise AgentError(stage=stage_name, role=role, detail=f"missing {schema_name} key '{key}'")
            if not isinstance(payload[key], expected_type):
                raise AgentError(
                    stage=stage_name,
                    role=role,
                    detail=(
                        f"invalid {schema_name} type for '{key}': "
                        f"expected {expected_type.__name__}, got {type(payload[key]).__name__}"
                    ),
                )

    def _emit_stage_event(self, action: str, stage: str, role: AgentRole, payload: Dict[str, Any]) -> None:
        if not self.event_emitter:
            return
        self.event_emitter(
            "stage_event",
            {
                "action": action,
                "stage": stage,
                "role": role.value,
                "payload": payload,
                "timestamp": time.time(),
            },
        )


def create_default_registry() -> AgentRegistry:
    """Create a registry with default canonical role agents."""
    registry = AgentRegistry()
    registry.register(_ArchitectAgent())
    registry.register(_StrategistAgent())
    registry.register(_EngineerAgent())
    registry.register(_SentinelAgent())
    return registry
