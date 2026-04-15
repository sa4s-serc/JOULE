from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from joule.cli import app
from joule.config import load_settings
from joule.models import CandidateEvaluation, FrontierState
from joule.orchestrator.mfbo import OptimizationOrchestrator
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


def test_run_command_supports_new_medium_target(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "algos.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "string_concat_report",
            "--tests",
            "tests/test_algos.py::test_string_concat_report",
            "--budget",
            "3",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Run:" in result.output


def test_run_command_supports_complex_harness_target(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "complex_cases.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "warehouse_balancing_pipeline",
            "--harness",
            "sample_pkg.harnesses:warehouse_pipeline_harness",
            "--budget",
            "2",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Run:" in result.output


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


def test_apply_allows_stdlib_dependency_bearing_candidate(sample_project):
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
            ('["collections"]', candidate["candidate_id"]),
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
    assert apply_result.exit_code == 0, apply_result.output


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


def test_run_analysis_best_candidate_id_matches_summary_when_scalar_regresses(sample_project, monkeypatch):
    _loosen_thresholds(sample_project)
    from joule.cli_commands import run as run_command

    original_optimize = OptimizationOrchestrator.optimize

    def _optimize_with_forced_best(self, run_id, target, bundle, **kwargs):
        baseline, pareto, best = original_optimize(self, run_id, target, bundle, **kwargs)
        if best is not None:
            return baseline, pareto, best
        candidate_id = "forcedbest"
        self.db.record_candidate(
            candidate_id=candidate_id,
            run_id=run_id,
            parent_id="baseline",
            operator_name="forced",
            reasoning="forced best candidate for regression guard coverage",
            dependencies=[],
            source_code=target.source,
            status="accepted",
            score=0.0,
            metadata={"stage": "F3", "phase": "confirmation", "rejected": None},
        )
        return (
            baseline,
            pareto,
            CandidateEvaluation(
                candidate_id=candidate_id,
                operator_name="forced",
                reasoning="forced best candidate for regression guard coverage",
                source=target.source,
                dependencies=[],
                parent_id="baseline",
                generation_depth=1,
                frontier_state=FrontierState.FRONTIER_ACTIVE,
                accepted=True,
                score=0.0,
                acquisition_score=0.0,
                dominance_summary={},
                report=baseline,
                metadata={},
            ),
        )

    monkeypatch.setattr(OptimizationOrchestrator, "optimize", _optimize_with_forced_best)

    calls = {"count": 0}

    def _forced_scalar_score(_aggregate):
        calls["count"] += 1
        return 1.0 if calls["count"] == 1 else 2.0

    monkeypatch.setattr(run_command, "scalar_score", _forced_scalar_score)

    target_file = sample_project / "sample_pkg" / "algos.py"
    result = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "unreferenced_total",
            "--budget",
            "6",
            "--analysis",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    analysis = payload["analysis"]
    run_dir = sample_project / ".joule" / "runs" / payload["run_id"]

    assert calls["count"] >= 2
    assert analysis["accepted_candidate_ids"]
    assert payload["best_candidate"] is None
    assert analysis["best_candidate_id"] is None
    assert not (run_dir / "best.patch").exists()


def test_run_rejects_non_positive_budget(sample_project):
    result = runner.invoke(
        app,
        [
            "run",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "unreferenced_total",
            "--budget",
            "0",
            "--no-dashboard",
        ],
    )
    assert result.exit_code != 0
    assert "--budget must be >= 1" in result.output


def test_run_writes_structured_events_and_summary_path(sample_project):
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
            "3",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    run_id = payload["run_id"]
    run_dir = sample_project / ".joule" / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    assert events_path.exists()
    assert events_path.read_text(encoding="utf-8").strip()
    assert payload["artifact_paths"].get("events.jsonl") == str(events_path)
    assert payload["artifact_paths"].get("run_summary.json") == str(run_dir / "run_summary.json")
    assert payload["artifact_paths"].get("dashboard.html") == str(run_dir / "dashboard.html")


def test_apply_commit_requires_branch(sample_project):
    result = runner.invoke(
        app,
        [
            "apply",
            str(sample_project),
            "--run-id",
            "deadbeef0000",
            "--commit",
        ],
    )
    assert result.exit_code != 0
    assert "--commit requires --branch" in result.output


def test_resume_command_continues_existing_run(sample_project):
    _loosen_thresholds(sample_project)
    target_file = sample_project / "sample_pkg" / "algos.py"

    first = runner.invoke(
        app,
        [
            "run",
            str(target_file),
            "--function",
            "unreferenced_total",
            "--budget",
            "2",
            "--analysis",
            "--no-dashboard",
        ],
    )
    assert first.exit_code == 0, first.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", first.output).group(1)

    settings = load_settings(sample_project)
    db = JouleDB(settings.db_path)
    before = len(db.get_candidates(run_id))
    checkpoint_path = sample_project / ".joule" / "runs" / run_id / "checkpoint.json"
    assert checkpoint_path.exists()

    resumed = runner.invoke(
        app,
        [
            "resume",
            str(sample_project),
            "--run-id",
            run_id,
            "--budget",
            "4",
            "--analysis",
            "--no-dashboard",
        ],
    )
    assert resumed.exit_code == 0, resumed.output

    after = len(db.get_candidates(run_id))
    assert after >= before


def test_run_ci_mode_threshold_failure_returns_exit_1(sample_project):
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
            "--ci",
            "--improvement-threshold",
            "1.0",
        ],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["ci_result"]["enabled"] is True
    assert payload["ci_result"]["exit_code"] == 1


def test_run_ci_mode_baseline_failure_returns_exit_2(sample_project):
    failing_test = sample_project / "tests" / "test_forced_failure.py"
    failing_test.write_text(
        "def test_forced_failure():\n"
        "    assert False\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "run",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_forced_failure.py::test_forced_failure",
            "--ci",
        ],
    )
    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["ci_result"]["enabled"] is True
    assert payload["ci_result"]["exit_code"] == 2
