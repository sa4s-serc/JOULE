from __future__ import annotations

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
    assert '"run_id"' in result.output
    assert '"pareto"' in result.output
    assert "setup" in result.output
    assert source_path.read_text(encoding="utf-8") == original
    run_id = re.search(r'"run_id":\s*"([^"]+)"', result.output).group(1)
    run_dir = sample_project / ".joule" / "runs" / run_id
    assert (run_dir / "run_summary.json").exists()
    if '"best_candidate": null' not in result.output:
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
    run_id = re.search(r'"run_id":\s*"([^"]+)"', result.output).group(1)
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
