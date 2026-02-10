from src.application.agents import AgentRuntime, create_default_registry
from src.application.agents.base import Agent
from src.application.agents.policies import StagePolicy
from src.application.agents.protocol import AgentContext, AgentError, AgentResult, AgentRole
from src.application.agents.registry import AgentRegistry


class BrokenStrategist(Agent):
    @property
    def name(self) -> str:
        return "broken_strategist"

    @property
    def role(self) -> AgentRole:
        return AgentRole.STRATEGIST

    @property
    def input_schema(self):
        return {"semantic_contract": dict}

    @property
    def output_schema(self):
        return {"strategy_plan": list}

    def run(self, context: AgentContext) -> AgentResult:
        # Wrong payload type on purpose
        return AgentResult(success=True, payload={"strategy_plan": "not-a-list"})


class MinimalArchitect(Agent):
    @property
    def name(self) -> str:
        return "minimal_architect"

    @property
    def role(self) -> AgentRole:
        return AgentRole.ARCHITECT

    @property
    def input_schema(self):
        return {"initial_code": str, "test_code": str}

    @property
    def output_schema(self):
        return {"semantic_contract": dict}

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, payload={"semantic_contract": {"k": "v"}})


class MinimalEngineer(Agent):
    @property
    def name(self) -> str:
        return "minimal_engineer"

    @property
    def role(self) -> AgentRole:
        return AgentRole.ENGINEER

    @property
    def input_schema(self):
        return {"initial_code": str, "strategy_plan": list}

    @property
    def output_schema(self):
        return {"candidate_code": str}

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, payload={"candidate_code": context.inputs["initial_code"]})


class MinimalSentinel(Agent):
    @property
    def name(self) -> str:
        return "minimal_sentinel"

    @property
    def role(self) -> AgentRole:
        return AgentRole.SENTINEL

    @property
    def input_schema(self):
        return {"candidate_code": str, "semantic_contract": dict}

    @property
    def output_schema(self):
        return {"approved": bool}

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, payload={"approved": True})


def test_agent_runtime_emits_structured_stage_events():
    emitted = []
    runtime = AgentRuntime(
        registry=create_default_registry(),
        event_emitter=lambda event_type, payload: emitted.append((event_type, payload)),
    )

    result = runtime.execute("def f(x):\n    return x\n", "def test_f():\n    assert f(1) == 1\n")

    assert result["approved"] is True
    assert any(event_type == "stage_event" for event_type, _ in emitted)
    assert any(payload.get("action") == "stage_started" for _, payload in emitted)
    assert any(payload.get("stage") == "strategy_generation" for _, payload in emitted)


def test_agent_runtime_rejects_output_schema_mismatch():
    registry = AgentRegistry()
    registry.register(MinimalArchitect())
    registry.register(BrokenStrategist())
    registry.register(MinimalEngineer())
    registry.register(MinimalSentinel())

    runtime = AgentRuntime(registry=registry)

    try:
        runtime.execute("def f(x):\n    return x\n", "def test_f():\n    assert f(1) == 1\n")
        assert False, "Expected AgentError for schema mismatch"
    except AgentError as err:
        assert err.role == AgentRole.STRATEGIST
        assert "invalid output type" in err.detail


def test_stage_policy_requires_semantic_contract_before_strategy_generation():
    policy = StagePolicy()

    try:
        policy.validate_invariants(memory={}, stage="strategy_generation")
        assert False, "Expected AgentError for missing semantic_contract"
    except AgentError as err:
        assert err.role == AgentRole.STRATEGIST
        assert "semantic contract" in err.detail
