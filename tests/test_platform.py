from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import pytest
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


def test_dashboard_once_includes_guided_sections(sample_project):
    baseline = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--no-dashboard",
        ],
    )
    assert baseline.exit_code == 0, baseline.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", baseline.output).group(1)

    result = runner.invoke(app, ["dashboard", str(sample_project), "--run-id", run_id, "--once"])
    assert result.exit_code == 0, result.output
    assert "Recommended Next Steps" in result.output
    assert "run-selector" in result.output
    assert "candidate-search-filter" in result.output
    assert "candidate-status-filter" in result.output
    assert "candidate-stage-filter" in result.output
    assert "candidate-visible-count" in result.output


def test_dashboard_surfaces_hotspot_insights(sample_project):
    baseline = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--hotspots",
            "--no-dashboard",
        ],
    )
    assert baseline.exit_code == 0, baseline.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", baseline.output).group(1)

    result = runner.invoke(app, ["dashboard", str(sample_project), "--run-id", run_id, "--once"])
    assert result.exit_code == 0, result.output
    normalized = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    normalized = re.sub(r"\s+", " ", normalized)
    assert "Hotspot Signal Quality" in normalized
    assert "Hotspot Insights" in normalized
    assert "schema_version=" in normalized
    assert "<th>Target Share</th>" in result.output
    assert "recommendations</strong>" in result.output.lower()


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
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    match = re.search(r'(\{\s*"run_id".*\})', result.output, flags=re.DOTALL)
    assert match, result.output
    payload = json.loads(match.group(1))
    assert payload["baseline"]["samples"][0]["metadata"]["inner_repetitions"] > 1


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


def test_doctor_command_separates_required_and_optional_checks(sample_project):
    result = runner.invoke(app, ["doctor", str(sample_project)])
    assert result.exit_code == 0, result.output
    assert "Required runtime checks" in result.output
    assert "Optional capabilities" in result.output


def test_discover_and_inspect_expose_workload_provenance(sample_project):
    baseline = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--no-dashboard",
        ],
    )
    assert baseline.exit_code == 0, baseline.output

    discover_result = runner.invoke(app, ["discover", str(sample_project)])
    assert discover_result.exit_code == 0, discover_result.output
    assert "workload_provenance" in discover_result.output

    run_id = re.search(r"Run:\s*([a-f0-9]+)", baseline.output).group(1)
    inspect_result = runner.invoke(app, ["inspect", str(sample_project), "--run-id", run_id])
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "workload_provenance" in inspect_result.output
    assert '"summary"' in inspect_result.output
    payload = json.loads(inspect_result.output)
    assert "surrogate_learning" in payload
    assert payload["summary"]["surrogate_learning"]["stored_observations"] >= 0


def test_inspect_human_output_is_readable(sample_project):
    baseline = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--no-dashboard",
        ],
    )
    assert baseline.exit_code == 0, baseline.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", baseline.output).group(1)

    inspect_result = runner.invoke(
        app,
        ["inspect", str(sample_project), "--run-id", run_id, "--output", "human"],
    )
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Run:" in inspect_result.output
    assert "Candidates:" in inspect_result.output
    assert "Diagnostics:" in inspect_result.output
    assert "Surrogate learning:" in inspect_result.output


def test_discover_human_output_is_human_readable(sample_project):
    result = runner.invoke(app, ["discover", str(sample_project), "--output", "human"])
    assert result.exit_code == 0, result.output
    assert "Discover:" in result.output
    assert "target(s)" in result.output


def test_parse_json_helper_summarizes_run_output(sample_project):
    run_result = runner.invoke(
        app,
        [
            "run",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "unreferenced_total",
            "--budget",
            "2",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert run_result.exit_code == 0, run_result.output

    parsed = runner.invoke(app, ["parse-json"], input=run_result.output)
    assert parsed.exit_code == 0, parsed.output
    assert "Run:" in parsed.output
    assert "Baseline:" in parsed.output


def test_parse_json_helper_rejects_invalid_payload(sample_project):
    del sample_project
    parsed = runner.invoke(app, ["parse-json"], input="not-json")
    assert parsed.exit_code != 0
    assert "Invalid JSON payload" in parsed.output


def test_inspect_unknown_candidate_returns_actionable_error(sample_project):
    baseline = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--no-dashboard",
        ],
    )
    assert baseline.exit_code == 0, baseline.output
    run_id = re.search(r"Run:\s*([a-f0-9]+)", baseline.output).group(1)

    inspect_result = runner.invoke(
        app,
        ["inspect", str(sample_project), "--run-id", run_id, "--candidate-id", "missing-id"],
    )
    assert inspect_result.exit_code != 0
    assert "Unknown candidate_id" in inspect_result.output


def test_inspect_summary_includes_search_and_artifact_reconciliation(sample_project):
    run_result = runner.invoke(
        app,
        [
            "run",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "unreferenced_total",
            "--budget",
            "3",
            "--analysis",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert run_result.exit_code == 0, run_result.output
    run_payload = json.loads(run_result.output)
    run_id = run_payload["run_id"]

    inspect_result = runner.invoke(
        app,
        ["inspect", str(sample_project), "--run-id", run_id],
    )
    assert inspect_result.exit_code == 0, inspect_result.output
    payload = json.loads(inspect_result.output)
    summary = payload["summary"]

    search_consistency = summary["search_consistency"]
    assert search_consistency["generated_minus_candidates"] == 0
    assert search_consistency["terminal_minus_candidates"] == 0
    assert search_consistency["frontier_dominated_events"] >= 0

    artifact_counts = summary["artifact_counts"]
    assert artifact_counts["filesystem_files"] >= artifact_counts["db_recorded"]
    reconciliation = summary["artifact_reconciliation"]
    assert reconciliation["missing_db_records"] >= 0
    assert isinstance(reconciliation["missing_db_record_examples"], list)


def test_run_help_exposes_budget_and_path_guidance():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0, result.output
    assert "Path to a target .py file or project root" in result.output
    assert "--budget" in result.output
    assert "--fresh-surrogate" in result.output


def test_resume_help_exposes_fresh_surrogate_option():
    result = runner.invoke(app, ["resume", "--help"])
    assert result.exit_code == 0, result.output
    assert "--fresh-surrogate" in result.output


def test_transformations_command_lists_registered_operators(sample_project):
    result = runner.invoke(app, ["transformations", str(sample_project)])
    assert result.exit_code == 0, result.output
    assert "Registered Transformations" in result.output
    assert "ForLoopToComprehension" in result.output
    assert "GenericSemanticRewriteLLM" in result.output


def test_transformations_command_json_output(sample_project):
    result = runner.invoke(app, ["transformations", str(sample_project), "--output", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    names = {item["name"] for item in payload["transformations"]}
    assert "ForLoopToComprehension" in names
    assert "GenericSemanticRewriteLLM" in names


def test_config_show_resolves_profile_defaults_and_overrides(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + "\n[tool.joule]\nprofile = \"quick\"\noptimization_budget = 9\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["config", "show", str(sample_project), "--output", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    resolved = payload["resolved"]
    assert resolved["profile"] == "quick"
    assert resolved["baseline_repetitions"] == 3
    assert resolved["optimization_budget"] == 9


def test_config_show_human_output(sample_project):
    result = runner.invoke(app, ["config", "show", str(sample_project)])
    assert result.exit_code == 0, result.output
    assert "Resolved JOULE Configuration" in result.output
    assert "optimization_budget" in result.output


def test_config_show_includes_nested_surrogate_settings(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + "\n[tool.joule.surrogate]\nmodel = \"gp\"\nacquisition = \"ucb\"\n"
        + "\n[tool.joule.surrogates.gp]\nnoise = 1e-5\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["config", "show", str(sample_project), "--output", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    surrogate = payload["resolved"]["surrogate"]
    assert surrogate["model"] == "gp"
    assert surrogate["acquisition"] == "ucb"
    assert surrogate["gp"]["noise"] == pytest.approx(1e-5)


def test_config_show_rejects_unknown_profile(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8") + "\n[tool.joule]\nprofile = \"unknown\"\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["config", "show", str(sample_project), "--output", "json"])
    assert result.exit_code != 0
    assert "Unknown JOULE profile" in result.output


def test_config_show_rejects_legacy_surrogate_keys(sample_project):
    pyproject = sample_project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8") + "\n[tool.joule]\nsurrogate_acquisition = \"ucb\"\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["config", "show", str(sample_project), "--output", "json"])
    assert result.exit_code != 0
    assert "Unsupported legacy surrogate key" in result.output
