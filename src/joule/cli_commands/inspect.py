from __future__ import annotations

from pathlib import Path

from joule.cli_helpers.output import resolve_output_mode
from joule.utils.analysis import (
    candidate_detail_payload,
    human_candidate_detail_summary,
    human_inspect_summary,
    json_pretty,
    summarize_inspect_payload,
)
from joule.utils.reporting import workload_provenance_records


def run_inspect(path: Path, run_id: str, candidate_id: str | None, output: str, verbose: bool, quiet: bool, *, bootstrap_fn) -> None:
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
    payload["summary"] = summarize_inspect_payload(
        candidates=candidates,
        measurements=measurements,
        search_events=search_events,
        hotspots=hotspot_profiles,
        artifacts=payload["artifacts"],
        apply_audits=payload["apply_audits"],
    )
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
