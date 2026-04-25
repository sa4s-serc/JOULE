from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from joule.evaluators.oracle import PerformanceOracle
from joule.utils.db import CandidateRecord
from joule.utils.artifacts import write_artifact
from joule.utils.db import JouleDB
from joule.utils.terminal import Reporter


def write_dashboard_snapshot(db: JouleDB, run_dir: Path) -> Path:
    from joule.dashboard.app import render_dashboard_html

    return write_artifact(run_dir, "dashboard.html", render_dashboard_html(db))


def write_run_summary(
    db: JouleDB,
    run_dir: Path,
    name: str,
    payload: dict,
) -> Path:
    output = write_artifact(run_dir, name, json.dumps(payload, indent=2))
    write_dashboard_snapshot(db, run_dir)
    return output


def collect_hotspot_analysis(
    *,
    oracle: PerformanceOracle,
    db: JouleDB,
    run_id: str,
    target: Any,
    bundle: Any,
    run_dir: Path,
    reporter: Reporter,
    enabled: bool,
    limit: int,
    granular: bool = False,
) -> dict | None:
    if not enabled:
        return None
    if granular:
        reporter.info("hotspots", "Profiling workloads for granular hotspot analysis (line-level)")
    else:
        reporter.info("hotspots", "Profiling workloads for hotspot analysis")
    records = oracle.profile_bundle_hotspots(target=target, bundle=bundle, granular=granular)
    created_at = datetime.now(UTC).isoformat()
    for item in records:
        db.record_hotspot_profile(
            run_id=run_id,
            workload_id=item["workload_id"],
            kind="workload",
            payload=item,
            created_at=created_at,
        )
    from joule.utils.analysis import summarize_hotspots, json_pretty

    summary = summarize_hotspots(records, limit=limit, target_file=target.file_path, granular=granular)
    db.record_hotspot_profile(
        run_id=run_id,
        workload_id="all",
        kind="summary",
        payload=summary,
        created_at=created_at,
    )
    write_artifact(run_dir, "hotspots.json", json_pretty(summary))
    return summary


def write_candidate_artifacts(
    run_dir: Path,
    candidates: list[CandidateRecord],
    *,
    db: JouleDB | None = None,
    run_id: str | None = None,
) -> None:
    from joule.utils.analysis import json_pretty

    if db is not None and not run_id:
        raise ValueError("run_id is required when db is provided")

    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for item in candidates:
        candidate_json = json_pretty(item)
        candidate_dir = candidates_dir / item["candidate_id"]
        candidate_dir.mkdir(parents=True, exist_ok=True)
        write_artifact(candidate_dir, "candidate.json", candidate_json)
        write_artifact(candidate_dir, "candidate.py", item["source_code"])
        if db is not None and run_id:
            db.record_artifact(run_id, f"candidates/{item['candidate_id']}/candidate.json", "json", candidate_json)
            db.record_artifact(run_id, f"candidates/{item['candidate_id']}/candidate.py", "code", item["source_code"])


def artifact_paths_payload(run_dir: Path, names: list[str]) -> dict[str, str]:
    return {name: str(run_dir / name) for name in names if (run_dir / name).exists()}
