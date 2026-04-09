from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from joule.cli import app
from joule.config import load_settings
from joule.utils.db import JouleDB


runner = CliRunner()


def _loosen_thresholds(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + "\n[tool.joule]\npromotion_scalar_min = 0.0\nfinal_improvement_min = 0.0\n",
        encoding="utf-8",
    )


def test_run_command_measures_candidates(sample_project):
    _loosen_thresholds(sample_project)
    source_path = sample_project / "sample_pkg" / "algos.py"
    original = source_path.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "run",
            str(source_path),
            "--function",
            "unreferenced_total",
            "--budget",
            "4",
            "--verbose",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Run:" in result.output
    assert "Funnel:" in result.output
    assert "setup" in result.output
    assert source_path.read_text(encoding="utf-8") == original
    run_id = re.search(r"Run:\s*([a-f0-9]+)", result.output).group(1)
    run_dir = sample_project / ".joule" / "runs" / run_id
    lock_payload = json.loads((sample_project / ".joule.lock").read_text(encoding="utf-8"))
    assert lock_payload["run_id"] == run_id
    assert lock_payload["target"]["qualname"] == "unreferenced_total"
    assert lock_payload["target_file_hash"]
    assert lock_payload["baseline_source_hash"]
    assert lock_payload["config"]["default_backend"] == "mock"
    assert (run_dir / "run_summary.json").exists()
    if "Best: none accepted" not in result.output:
        assert (run_dir / "best.patch").exists()


def test_apply_command_applies_best_candidate(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "algos.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "unreferenced_total",
            "--budget",
            "4",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", result.output).group(1)
    settings = load_settings(sample_project)
    candidates = JouleDB(settings.db_path).get_candidates(run_id)
    assert candidates
    apply_result = runner.invoke(
        app,
        [
            "apply",
            str(sample_project),
            "--run-id",
            run_id,
            "--candidate-id",
            candidates[0]["candidate_id"],
        ],
    )
    assert apply_result.exit_code == 0, apply_result.output
    assert "sum((value for value in range(limit) if value % 3 == 0))" in target_file.read_text(encoding="utf-8")


def test_apply_rejects_dependency_bearing_candidate(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "algos.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "unreferenced_total",
            "--budget",
            "4",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", result.output).group(1)
    settings = load_settings(sample_project)
    db = JouleDB(settings.db_path)
    candidate = db.get_candidates(run_id)[0]
    with db.connect() as conn:
        conn.execute(
            "UPDATE candidates SET dependencies_json = ? WHERE candidate_id = ?",
            ('["numpy"]', candidate["candidate_id"]),
        )
    apply_result = runner.invoke(
        app,
        [
            "apply",
            str(sample_project),
            "--run-id",
            run_id,
            "--candidate-id",
            candidate["candidate_id"],
        ],
    )
    assert apply_result.exit_code != 0
    assert "review-only" in apply_result.output


def test_run_analysis_writes_candidate_and_analysis_artifacts(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "algos.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "unreferenced_total",
            "--budget",
            "4",
            "--analysis",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    run_id = re.search(r'"run_id":\s*"([^"]+)"', result.output).group(1)
    run_dir = sample_project / ".joule" / "runs" / run_id
    assert (run_dir / "optimization_analysis.json").exists()
    assert (run_dir / "candidates").exists()
