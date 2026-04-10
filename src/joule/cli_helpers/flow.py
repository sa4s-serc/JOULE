from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from joule.config import JouleSettings
from joule.discovery.resolver import resolve_target, resolve_workload_bundle
from joule.integrations.git import file_sha256, source_sha256
from joule.models import RunRecord, RunType
from joule.utils.artifacts import run_directory, write_lockfile
from joule.utils.db import JouleDB
from joule.utils.reporting import workload_provenance_records
from joule.utils.terminal import TerminalReporter


@dataclass(slots=True)
class ExecutionContext:
    settings: JouleSettings
    db: JouleDB
    reporter: TerminalReporter
    target: Any
    bundle: Any
    chosen_backend: str
    run_id: str
    run_dir: Path
    record: RunRecord
    oracle: Any
    orchestrator: Any


def run_metadata(target, settings: JouleSettings, bundle, backend_name: str) -> dict:
    return {
        "target_qualname": target.qualname,
        "target_file_hash": file_sha256(target.file_path),
        "baseline_source_hash": source_sha256(target.source),
        "default_backend": settings.default_backend,
        "selected_backend": backend_name,
        "config_snapshot": settings.to_record(),
        "workload_provenance": workload_provenance_records(bundle),
    }


def resolve_target_and_bundle(
    *,
    path: Path,
    function: str,
    settings: JouleSettings,
    reporter: TerminalReporter,
    tests: list[str] | None,
    properties: list[str] | None,
    harness: str | None,
):
    reporter.info("setup", f"Project root: {settings.project_root}")
    target = resolve_target(path, function, project_root=settings.project_root)
    reporter.info("target", f"Resolved {target.qualname} at {target.file_path}")
    bundle = resolve_workload_bundle(settings, target, tests=tests, properties=properties, harness=harness)
    reporter.info("workloads", f"Using {len(bundle.workloads)} workload(s)")
    return target, bundle


def create_run_record(
    *,
    settings: JouleSettings,
    db: JouleDB,
    run_type: RunType,
    target,
    bundle,
    chosen_backend: str,
) -> tuple[RunRecord, str, Path]:
    run_id = settings.new_run_id()
    run_dir = run_directory(settings, run_id)
    record = RunRecord(
        run_id=run_id,
        run_type=run_type,
        target=target,
        bundle=bundle,
        status="running",
        created_at=datetime.now(UTC).isoformat(),
        metadata=run_metadata(target, settings, bundle, chosen_backend),
    )
    lock_path = write_lockfile(
        settings,
        run_id=run_id,
        target=target,
        backend=chosen_backend,
        target_file_hash=record.metadata["target_file_hash"],
        baseline_source_hash=record.metadata["baseline_source_hash"],
    )
    record.metadata["lock_path"] = str(lock_path)
    db.create_run(record)
    return record, run_id, run_dir
