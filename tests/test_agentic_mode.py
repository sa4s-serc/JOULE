from src.application.engine.evolution import EngineConfig, EvolutionaryEngine


class DummyRunner:
    def run(self, code: str, test_code: str, allowed_imports=None):
        return True, {"energy_joules": 1.0, "duration_seconds": 1.0}, "ok"


def test_engine_agentic_mode_emits_stage_events():
    events = []

    engine = EvolutionaryEngine(
        mutators=[],
        runner=DummyRunner(),
        config=EngineConfig(generations=1, population_size=2, enable_parallel_mutations=False, enable_intelligent_selection=False),
        event_callback=lambda evt: events.append(evt),
    )

    solutions = engine.optimize(
        "def f(x):\n    return x\n",
        "def test_f():\n    assert f(1) == 1\n",
        mode="agentic",
    )

    assert solutions
    stage_events = [event for event in events if event.type == "stage_event"]
    assert stage_events
    assert any(event.data.get("stage") == "strategy_generation" for event in stage_events)
