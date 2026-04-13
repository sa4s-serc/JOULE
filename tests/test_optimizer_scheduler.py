from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from joule.config import JouleSettings
from joule.models import (
    AggregateMetrics,
    Fidelity,
    MeasurementReport,
    SearchPhase,
    TargetSpec,
    TransformationResult,
    WorkloadBundle,
    WorkloadKind,
    WorkloadSpec,
)
from joule.evaluators.correctness import CorrectnessEngine
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.orchestrator.pareto import ParetoFront, ParetoPoint
from joule.surrogate.gp import GaussianProcessSurrogate
from joule.utils.db import JouleDB


class _AlwaysCorrect:
    def verify(self, *_args, **_kwargs):
        return True, []


class _ChainOperator:
    name = "chain"
    family = "deterministic"

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del target
        if context is None:
            return []
        if context.generation_depth == 0:
            return [
                TransformationResult(
                    operator_name=self.name,
                    operator_family=self.family,
                    proposal_rank=0,
                    candidate_source="def target(limit):\n    return sum(value for value in range(limit))\n",
                    reasoning="depth-1 candidate",
                )
            ]
        if context.generation_depth == 1:
            return [
                TransformationResult(
                    operator_name=self.name,
                    operator_family=self.family,
                    proposal_rank=0,
                    candidate_source=(
                        "def target(limit):\n"
                        "    total = 0\n"
                        "    for value in range(limit):\n"
                        "        total += value\n"
                        "    return total\n"
                    ),
                    reasoning="depth-2 candidate",
                )
            ]
        return []


class _SingleRegistry:
    def __init__(self, operator) -> None:
        self.operator = operator
        self.operators = [operator]

    def select_operator(self, *, phase: SearchPhase, parent_generation: int):
        del phase, parent_generation
        return self.operator

    def update(self, *_args, **_kwargs) -> None:
        return None

    def record_empty_attempt(self, *_args, **_kwargs) -> None:
        return None


class _FakeOracle:
    def __init__(self, source_metrics: dict[str, tuple[float, float, float]]) -> None:
        self.source_metrics = source_metrics

    def measure_bundle(
        self,
        *,
        run_id: str,
        target: TargetSpec,
        bundle: WorkloadBundle,
        fidelity: Fidelity,
        candidate_id: str | None = None,
        candidate_source: str | None = None,
        repetitions: int | None = None,
        use_cache: bool = True,
    ) -> MeasurementReport:
        del repetitions
        source = candidate_source or target.source
        latency, energy, memory = self.source_metrics[source]
        aggregate = AggregateMetrics(
            workload_id="all",
            repetitions=1,
            success_rate=1.0,
            mean_wall_time_s=latency,
            mean_cpu_time_s=latency,
            mean_peak_memory_bytes=memory,
            mean_energy_j=energy,
            wall_time_ci95=0.0,
            cpu_time_ci95=0.0,
            peak_memory_ci95=0.0,
            energy_ci95=0.0,
        )
        return MeasurementReport(
            run_id=run_id,
            candidate_id=candidate_id,
            fidelity=fidelity,
            aggregate=aggregate,
            per_workload=[
                AggregateMetrics(
                    workload_id=bundle.workloads[0].identifier,
                    repetitions=1,
                    success_rate=1.0,
                    mean_wall_time_s=latency,
                    mean_cpu_time_s=latency,
                    mean_peak_memory_bytes=memory,
                    mean_energy_j=energy,
                    wall_time_ci95=0.0,
                    cpu_time_ci95=0.0,
                    peak_memory_ci95=0.0,
                    energy_ci95=0.0,
                )
            ],
            samples=[],
            environment={"backend": "fake"},
        )


def _target_and_bundle(project_root: Path) -> tuple[TargetSpec, WorkloadBundle]:
    source = "def target(limit):\n    return sum([value for value in range(limit)])\n"
    module_path = project_root / "module.py"
    module_path.write_text(source, encoding="utf-8")
    target = TargetSpec(
        project_root=project_root,
        module="module",
        file_path=module_path,
        function_name="target",
        qualname="target",
        owner_path=[],
        line_start=1,
        line_end=2,
        source=source,
    )
    bundle = WorkloadBundle(
        target=target,
        workloads=[
            WorkloadSpec(
                kind=WorkloadKind.HARNESS,
                identifier="harness::target",
                label="target harness",
                selector="module:target",
            )
        ],
    )
    return target, bundle


def test_optimizer_expands_non_baseline_parent_and_persists_lineage(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        search_min_novelty=0.0,
        surrogate_min_training_points=1,
        search_branching_factor=2,
        search_max_generations=4,
        search_convergence_patience=8,
    )
    target, bundle = _target_and_bundle(tmp_path)
    source_metrics = {
        target.source: (10.0, 10.0, 1_000.0),
        "def target(limit):\n    return sum(value for value in range(limit))\n": (11.0, 9.0, 1_000.0),
        (
            "def target(limit):\n"
            "    total = 0\n"
            "    for value in range(limit):\n"
            "        total += value\n"
            "    return total\n"
        ): (11.0, 8.0, 1_000.0),
    }
    db = JouleDB(settings.db_path)
    orchestrator = OptimizationOrchestrator(
        settings=settings,
        db=db,
        oracle=cast(Any, _FakeOracle(source_metrics)),
        correctness=cast(Any, _AlwaysCorrect()),
        registry=cast(Any, _SingleRegistry(_ChainOperator())),
        surrogate=GaussianProcessSurrogate(),
    )

    _baseline, _pareto, best = orchestrator.optimize("run-chain", target, bundle, budget=2)

    assert best is not None
    candidates = db.get_candidates("run-chain")
    accepted = [item for item in candidates if item["status"] == "accepted"]
    assert any(item["parent_id"] != "baseline" for item in accepted)
    assert any(item["metadata"].get("generation_depth") == 2 for item in accepted)


def test_pareto_front_rejects_dominated_candidates_and_keeps_tradeoffs():
    front = ParetoFront(weights=(0.5, 0.3, 0.2))
    base = AggregateMetrics("all", 1, 1.0, 10.0, 10.0, 10.0, 10.0, 0.0, 0.0, 0.0, 0.0)
    a = AggregateMetrics("all", 1, 1.0, 12.0, 12.0, 10.0, 9.0, 0.0, 0.0, 0.0, 0.0)
    b = AggregateMetrics("all", 1, 1.0, 14.0, 14.0, 10.0, 8.0, 0.0, 0.0, 0.0, 0.0)
    dominated = AggregateMetrics("all", 1, 1.0, 13.0, 13.0, 10.0, 9.5, 0.0, 0.0, 0.0, 0.0)

    assert front.add(ParetoPoint(candidate_id="baseline", metrics=base))["accepted"]
    assert front.add(ParetoPoint(candidate_id="a", metrics=a))["accepted"]
    assert front.add(ParetoPoint(candidate_id="b", metrics=b))["accepted"]
    rejected = front.add(ParetoPoint(candidate_id="dominated", metrics=dominated))

    assert rejected["accepted"] is False
    assert "a" in rejected["dominated_by"]
    assert {item.candidate_id for item in front.points()} == {"baseline", "a", "b"}


def test_surrogate_novelty_rejection_and_warm_start(tmp_path: Path):
    surrogate = GaussianProcessSurrogate()
    source = "def f(x):\n    return x + 1\n"
    surrogate.record(source, 1.2)
    screened = surrogate.screen_candidate(
        source=source,
        best_score=1.0,
        phase=SearchPhase.EXPLORATION,
        min_novelty=0.2,
        min_training_points=1,
    )
    assert screened["decision"] == "reject"
    assert screened["reason"] == "low_novelty"

    settings = JouleSettings(project_root=tmp_path, surrogate_warm_start_limit=5)
    db = JouleDB(settings.db_path)
    db.record_candidate(
        candidate_id="hist-1",
        run_id="hist-run",
        parent_id="baseline",
        operator_name="hist-op",
        reasoning="history",
        dependencies=[],
        source_code=source,
        status="accepted",
        score=2.5,
        metadata={},
    )
    orchestrator = OptimizationOrchestrator(
        settings=settings,
        db=db,
        oracle=cast(Any, _FakeOracle({source: (1.0, 1.0, 1.0)})),
        correctness=cast(Any, CorrectnessEngine()),
        registry=cast(Any, _SingleRegistry(_ChainOperator())),
        surrogate=GaussianProcessSurrogate(),
    )
    mean, _uncertainty = orchestrator.surrogate.predict(source)
    assert mean == 2.5
