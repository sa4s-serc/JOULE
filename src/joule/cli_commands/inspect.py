from __future__ import annotations

from pathlib import Path

from joule.cli_helpers.output import resolve_output_mode
from joule.utils.analysis import (
    candidate_source_hash,
    candidate_detail_payload,
    human_candidate_detail_summary,
    human_inspect_summary,
    json_pretty,
    summarize_inspect_payload,
)
from joule.utils.reporting import workload_provenance_records


def run_inspect(
    path: Path,
    run_id: str,
    candidate_id: str | None,
    output: str,
    verbose: bool,
    quiet: bool,
    surrogate_limit: int,
    *,
    bootstrap_fn,
) -> None:
    from typer import BadParameter, echo

    output_mode = resolve_output_mode(output)
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    settings, db, reporter = bootstrap_fn(path, verbose=verbose, quiet=effective_quiet)
    reporter.info("inspect", f"Loading run {run_id}")
    record = db.get_run(run_id)
    measurements = db.get_measurements(run_id)
    candidates = db.get_candidates(run_id)
    hotspot_profiles = db.get_hotspot_profiles(run_id)
    search_events = db.get_search_events(run_id)
    payload = {
        "run": {
            "run_id": record.run_id,
            "run_type": record.run_type.value,
            "status": record.status,
            "created_at": record.created_at,
            "target": record.target.to_record(),
            "bundle": record.bundle.to_record(),
            "metadata": record.metadata,
        },
        "workload_provenance": workload_provenance_records(record.bundle),
        "measurements": measurements,
        "candidates": candidates,
        "search_events": search_events,
        "hotspots": hotspot_profiles,
        "artifacts": db.get_artifacts(run_id),
        "apply_audits": db.get_apply_audits(run_id),
    }
    target_key = f"{record.target.module}:{record.target.qualname}"
    surrogate_history = db.get_surrogate_observations(limit=max(0, surrogate_limit), target_key=target_key)
    surrogate_preview = [
        {
            "source_hash": candidate_source_hash(str(item.get("source", ""))),
            "source_length": len(str(item.get("source", ""))),
            "score": float(item.get("score", 0.0)),
            "feature_hints": dict(item.get("feature_hints", {})),
        }
        for item in surrogate_history
    ]
    payload["surrogate_learning"] = {
        "target_key": target_key,
        "reuse_enabled": settings.surrogate_reuse_observations,
        "warm_start_limit": settings.surrogate_warm_start_limit,
        "stored_observations": db.count_surrogate_observations(target_key=target_key),
        "history_preview": surrogate_preview,
    }
    payload["summary"] = summarize_inspect_payload(
        candidates=candidates,
        measurements=measurements,
        search_events=search_events,
        hotspots=hotspot_profiles,
        artifacts=payload["artifacts"],
        apply_audits=payload["apply_audits"],
    )
    payload["summary"]["surrogate_learning"] = {
        "stored_observations": payload["surrogate_learning"]["stored_observations"],
        "preview_count": len(surrogate_preview),
        "reuse_enabled": settings.surrogate_reuse_observations,
        "warm_start_limit": settings.surrogate_warm_start_limit,
    }
    if candidate_id:
        selected = next((item for item in candidates if item["candidate_id"] == candidate_id), None)
        if selected is None:
            raise BadParameter(f"Unknown candidate_id {candidate_id!r} for run {run_id}")
        candidate_payload = candidate_detail_payload(selected, measurements)
        if output_mode == "json":
            echo(json_pretty(candidate_payload))
        else:
            reporter.console.print(human_candidate_detail_summary(candidate_payload))
        return
    if output_mode == "json":
        echo(json_pretty(payload))
    else:
        reporter.console.print(human_inspect_summary(payload))
