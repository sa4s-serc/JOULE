"""Checkpoint serialization and restoration helper functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from joule.models import AggregateMetrics, CandidateEvaluation, Fidelity, MeasurementReport, TargetSpec
from joule.orchestrator.pareto import ParetoFront, ParetoPoint
from joule.orchestrator.internal.mfbo_flow import OptimizationState


def save_checkpoint(
    *,
    db: Any,
    run_id: str,
    candidate_id: str,
    baseline: MeasurementReport,
    pareto: ParetoFront,
    parent_snapshots: dict[str, Any],
    seen_sources: dict[str, str],
    state: OptimizationState,
    escape_used: bool,
    accepted_candidate_ids: set[str],
    checkpoint_path: Path | None,
) -> None:
    pareto_payload = [
        {
            "candidate_id": point.candidate_id,
            "metrics": point.metrics.to_record(),
            "parent_id": point.parent_id,
            "generation_depth": point.generation_depth,
            "operator_name": point.operator_name,
            "active": point.active,
        }
        for point in pareto.points()
    ]
    metadata = {
        "schema_version": 2,
        "baseline_report": baseline.to_record(),
        "state": {
            "measured": state.measured,
            "total_budget": state.total_budget,
            "no_frontier_gain": state.no_frontier_gain,
            "max_parent_expansions": state.max_parent_expansions,
        },
        "seen_sources": seen_sources,
        "parent_snapshots": {
            key: {
                "candidate_id": item.candidate_id,
                "source": item.source,
                "operator_name": item.operator_name,
                "generation_depth": item.generation_depth,
                "rejection_history": item.rejection_history,
            }
            for key, item in parent_snapshots.items()
        },
        "accepted_candidate_ids": sorted(accepted_candidate_ids),
        "escape_used": escape_used,
        "expansion_counts": pareto.expansion_counts(),
    }
    db.save_checkpoint(
        run_id=run_id,
        generation=state.measured,
        candidate_id=candidate_id,
        pareto_front_json=json.dumps(pareto_payload),
        metadata_json=json.dumps(metadata),
    )
    if checkpoint_path is None:
        return
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "generation": state.measured,
                "candidate_id": candidate_id,
                "pareto": pareto_payload,
                "metadata": metadata,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def restore_checkpoint(
    *,
    db: Any,
    settings: Any,
    run_id: str,
    target: TargetSpec | None = None,
) -> dict[str, Any] | None:
    from joule.orchestrator.mfbo import _ParentSnapshot

    checkpoint = db.get_latest_checkpoint(run_id)
    if checkpoint is None:
        return None
    metadata = checkpoint.get("metadata", {}) if isinstance(checkpoint, dict) else {}
    if not isinstance(metadata, dict) or int(metadata.get("schema_version", 0)) < 2:
        raise ValueError(
            "Detected incompatible checkpoint schema. Remove .joule/ and rerun to initialize the clean multi-surrogate state."
        )
    baseline_payload = metadata.get("baseline_report") if isinstance(metadata, dict) else None
    if not isinstance(baseline_payload, dict):
        return None
    baseline = MeasurementReport.from_record(baseline_payload)

    pareto = ParetoFront(
        weights=(
            settings.pareto_weights.energy,
            settings.pareto_weights.latency,
            settings.pareto_weights.memory,
        )
    )
    try:
        pareto_payload = json.loads(str(checkpoint.get("pareto_front_json", "[]")))
    except json.JSONDecodeError:
        pareto_payload = []
    for point in pareto_payload:
        if not isinstance(point, dict):
            continue
        metrics_payload = point.get("metrics")
        if not isinstance(metrics_payload, dict):
            continue
        pareto.add(
            ParetoPoint(
                candidate_id=str(point.get("candidate_id", "")),
                metrics=AggregateMetrics.from_record(metrics_payload),
                parent_id=point.get("parent_id"),
                generation_depth=int(point.get("generation_depth", 0)),
                operator_name=str(point.get("operator_name", "baseline")),
                active=bool(point.get("active", True)),
            )
        )
    if not pareto.points():
        pareto.add(
            ParetoPoint(
                candidate_id="baseline",
                metrics=baseline.aggregate,
                parent_id=None,
                generation_depth=0,
                operator_name="baseline",
                active=True,
            )
        )

    pareto.load_expansion_counts(metadata.get("expansion_counts", {}))

    state_payload = metadata.get("state", {})
    state = OptimizationState(
        total_budget=int(state_payload.get("total_budget", settings.optimization_budget)),
        max_parent_expansions=int(state_payload.get("max_parent_expansions", 1)),
        measured=int(state_payload.get("measured", 0)),
        no_frontier_gain=int(state_payload.get("no_frontier_gain", 0)),
    )

    parent_snapshots: dict[str, _ParentSnapshot] = {}
    snap_payload = metadata.get("parent_snapshots", {})
    for key, val in snap_payload.items():
        snap = _ParentSnapshot(
            candidate_id=str(val.get("candidate_id", "")),
            source=str(val.get("source", "")),
            operator_name=str(val.get("operator_name", "")),
            generation_depth=int(val.get("generation_depth", 0)),
        )
        snap.rejection_history = list(val.get("rejection_history", []))
        parent_snapshots[key] = snap

    # Ensure target source matches baseline if provided
    if target and target.source.strip() != parent_snapshots["baseline"].source.strip():
        parent_snapshots["baseline"].source = target.source

    seen_sources = dict(metadata.get("seen_sources", {}))
    escape_used = bool(metadata.get("escape_used", False))
    accepted_candidate_ids = set(metadata.get("accepted_candidate_ids", []))

    return {
        "baseline": baseline,
        "pareto": pareto,
        "parent_snapshots": parent_snapshots,
        "seen_sources": seen_sources,
        "state": state,
        "escape_used": escape_used,
        "accepted_candidate_ids": accepted_candidate_ids,
    }


def load_accepted_evaluations(db: Any, run_id: str) -> dict[str, CandidateEvaluation]:
    from joule.metadata import parse_candidate_metadata
    from joule.models import FrontierState

    candidates = [item for item in db.get_candidates(run_id) if item["status"] == "accepted"]
    if not candidates:
        return {}

    measurements = db.get_measurements(run_id)
    reports_by_candidate: dict[str, MeasurementReport] = {}
    fidelity_rank = {Fidelity.F1: 1, Fidelity.F2: 2, Fidelity.F3: 3}
    for payload in measurements:
        candidate_id = payload.get("candidate_id")
        if not candidate_id:
            continue
        report = MeasurementReport.from_record(payload)
        existing = reports_by_candidate.get(candidate_id)
        if existing is None or fidelity_rank[report.fidelity] >= fidelity_rank[existing.fidelity]:
            reports_by_candidate[candidate_id] = report

    evaluations: dict[str, CandidateEvaluation] = {}
    for item in candidates:
        metadata = dict(item.get("metadata", {}))
        parsed_metadata = parse_candidate_metadata(metadata)
        frontier_raw = parsed_metadata.frontier_state or FrontierState.FRONTIER_ACTIVE.value
        try:
            frontier_state = FrontierState(frontier_raw)
        except ValueError:
            frontier_state = FrontierState.FRONTIER_ACTIVE
        acquisition_score = float(parsed_metadata.surrogate.acquisition_score)

        evaluations[item["candidate_id"]] = CandidateEvaluation(
            candidate_id=item["candidate_id"],
            operator_name=item["operator_name"],
            reasoning=item["reasoning"],
            source=item["source_code"],
            dependencies=item["dependencies"],
            parent_id=item["parent_id"] or "baseline",
            generation_depth=int(parsed_metadata.generation_depth),
            frontier_state=frontier_state,
            accepted=True,
            score=float(item["score"]),
            acquisition_score=acquisition_score,
            dominance_summary=dict(parsed_metadata.extra.get("dominance_summary", {})),
            report=reports_by_candidate.get(item["candidate_id"]),
            metadata=metadata,
        )
    return evaluations

