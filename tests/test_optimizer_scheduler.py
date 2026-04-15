from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

import pytest

from joule.config import JouleSettings
from joule.metadata import parse_candidate_metadata
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
from joule.evaluators.backends.base import BackendMeasurement, EnergyBackend
from joule.evaluators.correctness import CorrectnessEngine
from joule.evaluators.oracle import PerformanceOracle
from joule.orchestrator.mfbo import OptimizationOrchestrator, _ParentSnapshot
from joule.orchestrator.internal.mfbo_flow import OptimizationState
from joule.orchestrator.pareto import ParetoFront, ParetoPoint
from joule.surrogate.gp import GaussianProcessSurrogate
from joule.utils.analysis import candidate_source_hash
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


class _CountingBackend:
    supports_parallel_measurement = True

    def __init__(self, name: str, *, energy_j: float, peak_memory_bytes: int = 4096) -> None:
        self.name = name
        self.energy_j = energy_j
        self.peak_memory_bytes = peak_memory_bytes
        self.calls = 0

    def measure(
        self,
        target: TargetSpec,
        workload: WorkloadSpec,
        *,
        overlay_root: Path | None = None,
        inner_repetitions: int = 1,
        timeout_s: float = 30.0,
    ) -> BackendMeasurement:
        del target, workload, overlay_root, timeout_s
        self.calls += 1
        logical_invocations = max(1, int(inner_repetitions))
        return BackendMeasurement(
            wall_time_s=0.20 * logical_invocations,
            cpu_time_s=0.10 * logical_invocations,
            peak_memory_bytes=self.peak_memory_bytes,
            energy_j=self.energy_j * logical_invocations,
            return_code=0,
            success=True,
            metadata={"logical_invocations": logical_invocations},
        )


class _NonParallelBackend(_CountingBackend):
    supports_parallel_measurement = False

    def __init__(self, name: str, *, energy_j: float, peak_memory_bytes: int = 4096) -> None:
        super().__init__(name, energy_j=energy_j, peak_memory_bytes=peak_memory_bytes)
        self._non_picklable = lambda value: value


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


def test_pareto_weighted_score_normalizes_memory_bytes():
    front = ParetoFront(weights=(0.0, 0.0, 1.0))
    metrics = AggregateMetrics("all", 1, 1.0, 0.0, 0.0, 1024 * 1024, 0.0, 0.0, 0.0, 0.0, 0.0)

    assert front.weighted_score(metrics) == pytest.approx(1.0)


def test_checkpoint_restore_recovers_pareto_expansion_counts(tmp_path: Path):
    settings = JouleSettings(project_root=tmp_path)
    target, _bundle = _target_and_bundle(tmp_path)
    db = JouleDB(settings.db_path)
    orchestrator = OptimizationOrchestrator(
        settings=settings,
        db=db,
        oracle=cast(Any, _FakeOracle({target.source: (1.0, 1.0, 1.0)})),
        correctness=cast(Any, _AlwaysCorrect()),
        registry=cast(Any, _SingleRegistry(_ChainOperator())),
        surrogate=GaussianProcessSurrogate(),
    )

    baseline = AggregateMetrics("all", 1, 1.0, 10.0, 10.0, 1_000.0, 10.0, 0.0, 0.0, 0.0, 0.0)
    report = MeasurementReport(
        run_id="run-checkpoint",
        candidate_id=None,
        fidelity=Fidelity.F3,
        aggregate=baseline,
        per_workload=[],
        samples=[],
        environment={"backend": "fake"},
    )
    pareto = ParetoFront(weights=(0.5, 0.3, 0.2))
    pareto.add(ParetoPoint(candidate_id="baseline", metrics=baseline))
    assert pareto.sample_active_parent(max_generation=4) == "baseline"
    assert pareto.expansion_count("baseline") == 1

    state = OptimizationState(total_budget=1, max_parent_expansions=2, measured=1, no_frontier_gain=0)
    parent_snapshots = {
        "baseline": _ParentSnapshot(
            candidate_id="baseline",
            source=target.source,
            operator_name="baseline",
            generation_depth=0,
        )
    }
    orchestrator._save_checkpoint(
        run_id="run-checkpoint",
        candidate_id="baseline",
        baseline=report,
        pareto=pareto,
        parent_snapshots=parent_snapshots,
        seen_sources={candidate_source_hash(target.source): "baseline"},
        state=state,
        escape_used=False,
        accepted_candidate_ids={"baseline"},
        checkpoint_path=tmp_path / "checkpoint.json",
    )

    restored = orchestrator._restore_checkpoint(run_id="run-checkpoint")
    assert restored is not None
    assert restored["pareto"].expansion_count("baseline") == 1


def test_pareto_parent_sampling_can_prefer_deeper_points():
    baseline_metrics = AggregateMetrics("all", 1, 1.0, 10.0, 10.0, 10.0, 10.0, 0.0, 0.0, 0.0, 0.0)
    deeper_metrics = AggregateMetrics("all", 1, 1.0, 11.0, 11.0, 10.0, 9.0, 0.0, 0.0, 0.0, 0.0)

    shallow_first = ParetoFront(weights=(0.5, 0.3, 0.2))
    shallow_first.add(ParetoPoint(candidate_id="baseline", metrics=baseline_metrics, generation_depth=0))
    shallow_first.add(ParetoPoint(candidate_id="deep", metrics=deeper_metrics, generation_depth=2))
    assert shallow_first.sample_active_parent(max_generation=4, prefer_deeper=False) == "baseline"

    deep_first = ParetoFront(weights=(0.5, 0.3, 0.2))
    deep_first.add(ParetoPoint(candidate_id="baseline", metrics=baseline_metrics, generation_depth=0))
    deep_first.add(ParetoPoint(candidate_id="deep", metrics=deeper_metrics, generation_depth=2))
    assert deep_first.sample_active_parent(max_generation=4, prefer_deeper=True) == "deep"


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
    target, _bundle = _target_and_bundle(tmp_path)
    target_key = f"{target.module}:{target.qualname}"
    db = JouleDB(settings.db_path)
    db.save_surrogate_observation(
        run_id="hist-run",
        target_key=target_key,
        source_code=source,
        score=2.5,
    )
    orchestrator = OptimizationOrchestrator(
        settings=settings,
        db=db,
        oracle=cast(Any, _FakeOracle({source: (1.0, 1.0, 1.0)})),
        correctness=cast(Any, CorrectnessEngine()),
        registry=cast(Any, _SingleRegistry(_ChainOperator())),
        surrogate=GaussianProcessSurrogate(),
    )
    orchestrator._warm_start_surrogate(target_key=target_key, fresh_start=False)
    mean, _uncertainty = orchestrator.surrogate.predict(source)
    assert mean == 2.5

    fresh_orchestrator = OptimizationOrchestrator(
        settings=settings,
        db=db,
        oracle=cast(Any, _FakeOracle({source: (1.0, 1.0, 1.0)})),
        correctness=cast(Any, CorrectnessEngine()),
        registry=cast(Any, _SingleRegistry(_ChainOperator())),
        surrogate=GaussianProcessSurrogate(),
    )
    fresh_orchestrator._warm_start_surrogate(target_key=target_key, fresh_start=True)
    fresh_mean, _fresh_uncertainty = fresh_orchestrator.surrogate.predict(source)
    assert fresh_mean == 0.0


def test_surrogate_predicts_and_exposes_acquisition_metadata():
    surrogate = GaussianProcessSurrogate(acquisition="ei")
    training = [
        ("def f(x):\n    return x + 1\n", 1.2),
        ("def f(x):\n    return x + 2\n", 1.1),
        ("def f(x):\n    return (x + 3)\n", 1.0),
    ]
    for source, score in training:
        surrogate.record(source, score)

    query = "def f(x):\n    y = x + 1\n    return y\n"
    mean, uncertainty = surrogate.predict(query)
    assert math.isfinite(mean)
    assert math.isfinite(uncertainty)
    assert uncertainty >= 0.0

    screened = surrogate.screen_candidate(
        source=query,
        best_score=0.9,
        phase=SearchPhase.EXPLOITATION,
        min_novelty=0.0,
        min_training_points=3,
    )
    assert screened["model_mode"] == "gp"
    assert screened["acquisition"] == "ei"
    assert math.isfinite(float(screened["acquisition_score"]))


def test_orchestrator_create_uses_configured_surrogate_settings(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        surrogate_acquisition="ucb",
        surrogate_gp_noise=1e-5,
        surrogate_gp_length_scale=2.0,
        surrogate_gp_nu=2.5,
        surrogate_gp_ucb_beta=1.8,
    )
    target, _bundle = _target_and_bundle(tmp_path)
    db = JouleDB(settings.db_path)
    oracle = cast(Any, _FakeOracle({target.source: (1.0, 1.0, 1.0)}))

    orchestrator = OptimizationOrchestrator.create(settings, db, oracle)

    assert orchestrator.surrogate.mode == "gp"
    assert orchestrator.surrogate.acquisition == "ucb"


def test_operator_composition_generates_chained_metadata(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        search_min_novelty=0.0,
        surrogate_min_training_points=1,
        search_branching_factor=2,
        search_composition_enabled=True,
        search_composition_width=1,
        search_max_generations=4,
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
        ): (12.0, 8.0, 1_000.0),
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

    orchestrator.optimize("run-compose", target, bundle, budget=2)

    candidates = db.get_candidates("run-compose")
    composed = [item for item in candidates if int(item["metadata"].get("composition_hops", 0)) > 0]
    assert composed
    assert any(item["metadata"].get("generation_depth") == 2 for item in composed)
    assert any(len(item["metadata"].get("composed_operator_chain", [])) == 2 for item in composed)


def test_oracle_cache_isolated_by_backend(tmp_path: Path):
    settings = JouleSettings(project_root=tmp_path, inner_repetitions_mode="fixed")
    target, bundle = _target_and_bundle(tmp_path)
    db = JouleDB(settings.db_path)

    mock_backend = _CountingBackend("mock", energy_j=1.0)
    mock_oracle = PerformanceOracle(settings=settings, backend=cast(Any, mock_backend), db=db)
    first = mock_oracle.measure_bundle(
        run_id="run-mock",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=True,
    )

    rapl_backend = _CountingBackend("rapl", energy_j=2.5)
    rapl_oracle = PerformanceOracle(settings=settings, backend=cast(Any, rapl_backend), db=db)
    second = rapl_oracle.measure_bundle(
        run_id="run-rapl",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=True,
    )

    assert first.environment["backend"] == "mock"
    assert second.environment["backend"] == "rapl"
    assert rapl_backend.calls == 1
    assert second.aggregate.mean_energy_j == pytest.approx(2.5)


def test_oracle_cached_report_uses_current_run_id(tmp_path: Path):
    settings = JouleSettings(project_root=tmp_path, inner_repetitions_mode="fixed")
    target, bundle = _target_and_bundle(tmp_path)
    db = JouleDB(settings.db_path)
    backend = _CountingBackend("mock", energy_j=1.0)
    oracle = PerformanceOracle(settings=settings, backend=cast(Any, backend), db=db)

    first = oracle.measure_bundle(
        run_id="run-1",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=True,
    )
    second = oracle.measure_bundle(
        run_id="run-2",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=True,
    )

    assert first.run_id == "run-1"
    assert second.run_id == "run-2"
    assert backend.calls == 1
    assert second.metadata.get("cache_hit") is True


def test_oracle_peak_memory_not_divided_by_inner_repetitions(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        inner_repetitions_mode="fixed",
        inner_repetitions_fixed=4,
    )
    target, bundle = _target_and_bundle(tmp_path)
    backend = _CountingBackend("mock", energy_j=1.5, peak_memory_bytes=32_768)
    oracle = PerformanceOracle(settings=settings, backend=cast(Any, backend), db=JouleDB(settings.db_path))

    report = oracle.measure_bundle(
        run_id="run-memory",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=False,
    )

    sample = report.samples[0]
    assert sample.metadata["inner_repetitions"] == 4
    assert sample.peak_memory_bytes == 32_768


def test_oracle_disables_parallel_for_non_parallel_backends(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        inner_repetitions_mode="fixed",
        max_parallel_workers=2,
    )
    target, bundle = _target_and_bundle(tmp_path)
    bundle = WorkloadBundle(
        target=target,
        workloads=[
            *bundle.workloads,
            WorkloadSpec(
                kind=WorkloadKind.HARNESS,
                identifier="harness::target-secondary",
                label="target harness secondary",
                selector="module:target",
            ),
        ],
    )
    backend = _NonParallelBackend("rapl", energy_j=1.0)
    oracle = PerformanceOracle(settings=settings, backend=cast(Any, backend), db=JouleDB(settings.db_path))

    report = oracle.measure_bundle(
        run_id="run-sequential",
        target=target,
        bundle=bundle,
        fidelity=Fidelity.F1,
        repetitions=1,
        use_cache=False,
    )

    assert backend.calls == 2
    assert report.aggregate.repetitions == 2


def test_measurement_report_round_trips_from_record():
    report = MeasurementReport(
        run_id="run-roundtrip",
        candidate_id="cand-1",
        fidelity=Fidelity.F2,
        aggregate=AggregateMetrics(
            workload_id="all",
            repetitions=2,
            success_rate=1.0,
            mean_wall_time_s=0.12,
            mean_cpu_time_s=0.10,
            mean_peak_memory_bytes=1024.0,
            mean_energy_j=0.9,
            wall_time_ci95=0.01,
            cpu_time_ci95=0.01,
            peak_memory_ci95=4.0,
            energy_ci95=0.02,
        ),
        per_workload=[],
        samples=[],
        environment={"backend": "mock"},
        metadata={"cache_hit": False},
    )

    restored = MeasurementReport.from_record(report.to_record())
    assert restored.run_id == report.run_id
    assert restored.candidate_id == report.candidate_id
    assert restored.fidelity is report.fidelity
    assert restored.environment == report.environment


def test_candidate_metadata_is_versioned_and_typed(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        search_min_novelty=0.0,
        surrogate_min_training_points=1,
        search_branching_factor=1,
        search_max_generations=2,
    )
    target, bundle = _target_and_bundle(tmp_path)
    source_metrics = {
        target.source: (10.0, 10.0, 1_000.0),
        "def target(limit):\n    return sum(value for value in range(limit))\n": (9.0, 9.0, 1_000.0),
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

    orchestrator.optimize("run-metadata", target, bundle, budget=1)

    candidates = db.get_candidates("run-metadata")
    assert candidates
    parsed = parse_candidate_metadata(candidates[0].get("metadata", {}))
    assert parsed.schema_version >= 1
    assert parsed.surrogate.schema_version >= 1

    events = db.get_search_events("run-metadata")
    assert events
    assert all(int(event["detail"].get("schema_version", 0)) >= 1 for event in events)


def test_partial_fidelity_rejections_record_explicit_reason(tmp_path: Path):
    settings = JouleSettings(
        project_root=tmp_path,
        search_min_novelty=0.0,
        surrogate_min_training_points=1,
        search_branching_factor=1,
        search_max_generations=2,
        search_exploration_fraction=1.0,
        search_exploitation_fraction=0.0,
        search_confirmation_fraction=0.0,
    )
    target, bundle = _target_and_bundle(tmp_path)
    source_metrics = {
        target.source: (10.0, 10.0, 1_000.0),
        "def target(limit):\n    return sum(value for value in range(limit))\n": (10.0, 10.0, 1_000.0),
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

    orchestrator.surrogate.screen_candidate = lambda **_kwargs: {
        "decision": "measure_partial",
        "reason": "",
        "predicted_score": 1.0,
        "uncertainty": 0.0,
        "novelty": 1.0,
        "acquisition_score": 0.0,
        "expected_improvement": 0.0,
        "model_mode": "forced",
        "acquisition": "ei",
        "schema_version": 1,
    }

    orchestrator.optimize("run-partial-fidelity", target, bundle, budget=1)

    candidates = db.get_candidates("run-partial-fidelity")
    assert len(candidates) == 1
    metadata = parse_candidate_metadata(candidates[0].get("metadata", {}))
    assert metadata.rejected == "partial_fidelity_f1"

    events = db.get_search_events("run-partial-fidelity")
    rejected_f1 = [
        event
        for event in events
        if event["candidate_id"] == candidates[0]["candidate_id"] and event["event_type"] == "rejected_f1"
    ]
    assert rejected_f1
    assert rejected_f1[-1]["detail"].get("reason") == "partial_fidelity_f1"


def test_energy_backend_protocol_requires_parallel_capability_flag():
    class MissingCapabilityBackend:
        name = "missing"

        def measure(self, *args, **kwargs):
            del args, kwargs
            return BackendMeasurement(
                wall_time_s=0.0,
                cpu_time_s=0.0,
                peak_memory_bytes=0,
                energy_j=0.0,
                return_code=0,
                success=True,
            )

    assert not isinstance(MissingCapabilityBackend(), EnergyBackend)
