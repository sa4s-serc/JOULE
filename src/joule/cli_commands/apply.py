from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from joule.config import JouleSettings
from joule.integrations.git import (
    apply_patch_to_target,
    commit,
    create_branch,
    file_sha256,
    stage_files,
)
from joule.utils.db import JouleDB
from joule.utils.terminal import TerminalReporter


def run_apply(
    settings: JouleSettings,
    db: JouleDB,
    reporter: TerminalReporter,
    run_id: str,
    candidate_id: str | None,
    branch: bool,
    commit_changes: bool,
) -> None:
    from typer import BadParameter

    if commit_changes and not branch:
        raise BadParameter("--commit requires --branch")
    run = db.get_run(run_id)
    candidates = db.get_candidates(run_id)
    if candidate_id:
        selected = next((item for item in candidates if item["candidate_id"] == candidate_id), None)
    else:
        selected = next((item for item in candidates if item["status"] == "accepted"), None)
    if selected is None:
        raise BadParameter(
            f"No accepted candidate available for run {run_id}; use 'joule inspect {settings.project_root} --run-id {run_id}' to review candidates"
        )
    if selected["dependencies"]:
        dependencies = ", ".join(str(dep) for dep in selected["dependencies"])
        raise BadParameter(
            f"Candidate {selected['candidate_id']} requires new dependencies ({dependencies}) and remains review-only in JOULE v0"
        )
    expected_hash = run.metadata.get("target_file_hash")
    current_hash = file_sha256(run.target.file_path)
    if expected_hash and current_hash != expected_hash:
        raise BadParameter(
            f"Target file changed since measurement (expected {expected_hash[:8]}, current {current_hash[:8]}); refusing to apply"
        )
    if branch:
        branch_name = create_branch(run.target.project_root, run_id)
        reporter.info("git", f"Created branch {branch_name}")
    apply_patch_to_target(run.target, selected["source_code"])
    artifact_paths = [
        run.target.file_path,
        settings.artifact_path / "runs" / run_id / "best.patch",
        settings.artifact_path / "runs" / run_id / "run_summary.json",
        settings.artifact_path / "runs" / run_id / "dashboard.html",
    ]
    existing_paths = [path for path in artifact_paths if path.exists()]
    if branch:
        stage_files(run.target.project_root, existing_paths)
    if commit_changes:
        commit(run.target.project_root, f"Apply JOULE candidate {selected['candidate_id']} for {run.target.qualname}")
        reporter.info("git", f"Committed candidate {selected['candidate_id']}")
    applied_at = datetime.now(UTC).isoformat()
    db.record_apply_audit(
        run_id=run_id,
        candidate_id=selected["candidate_id"],
        applied_at=applied_at,
        metadata={"branch": branch, "commit": commit_changes},
    )
    reporter.info("apply", f"Applied candidate {selected['candidate_id']} to {run.target.file_path}")
