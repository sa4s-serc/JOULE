from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from typer.testing import CliRunner

from joule.cli import app
from joule.discovery.resolver import resolve_target
from joule.evaluators.backends.mock import MockEnergyBackend
from joule.models import WorkloadKind, WorkloadSpec


runner = CliRunner()


def test_doctor_command_reports_backend(sample_project):
    result = runner.invoke(app, ["doctor", str(sample_project)])
    assert result.exit_code == 0, result.output
    assert "Backend mock" in result.output


def test_dashboard_once_returns_html(sample_project):
    result = runner.invoke(app, ["dashboard", str(sample_project), "--once"])
    assert result.exit_code == 0, result.output
    assert "<title>JOULE Dashboard</title>" in result.output


def test_adaptive_measurement_uses_inner_repetitions(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8") + "\n[tool.joule]\nadaptive_min_window_s = 0.5\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "unreferenced_total",
            "--json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    match = re.search(r'(\{\s*"run_id".*\})', result.output, flags=re.DOTALL)
    assert match, result.output
    payload = json.loads(match.group(1))
    assert payload["samples"][0]["metadata"]["inner_repetitions"] > 1


def test_mock_backend_reports_full_metrics(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "unreferenced_total", project_root=sample_project)
    workload = WorkloadSpec(
        kind=WorkloadKind.GOLDEN_TRACE,
        identifier="golden::unreferenced_total",
        label="golden trace",
        selector=f"{target.file_path}::{target.function_name}",
    )
    measurement = MockEnergyBackend().measure(target, workload, inner_repetitions=2)
    assert measurement.wall_time_s > 0
    assert measurement.cpu_time_s >= 0
    assert measurement.peak_memory_bytes >= 0
    assert measurement.energy_j >= 0


def test_repo_launcher_dispatches_to_cli(sample_project):
    launcher = Path(__file__).resolve().parents[1] / "joule"
    process = subprocess.run(
        [str(launcher), "dashboard", str(sample_project), "--once"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "<title>JOULE Dashboard</title>" in process.stdout
