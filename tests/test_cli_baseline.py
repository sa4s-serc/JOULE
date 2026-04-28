from __future__ import annotations

import json

from typer.testing import CliRunner

from joule.cli import app


runner = CliRunner()


def test_baseline_command_with_pytest_workload(sample_project):
    result = runner.invoke(
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
    assert result.exit_code == 0, result.output
    assert "Aggregate:" in result.output


def test_baseline_command_with_property_workload(sample_project):
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--properties",
            "sample_pkg.properties:property_membership_total",
            "--repetitions",
            "2",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "property::sample_pkg.properties:property_membership_total" in result.output


def test_baseline_hotspots_json_output_includes_hotspots(sample_project):
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--hotspots",
            "--output",
            "json",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    hotspots = payload["hotspots"]
    assert hotspots
    assert hotspots["schema_version"] >= 2
    assert "signal_quality" in hotspots
    assert "workload_kind_counts" in hotspots
    assert hotspots["workload_kind_counts"].get("pytest", 0) >= 1
    assert "target_top_functions" in hotspots
    assert "project_top_functions" in hotspots
    assert "non_project_top_functions" in hotspots
    assert "insights" in hotspots
    assert "recommendations" in hotspots
    assert hotspots["recommendations"]
    assert hotspots["by_workload"][0]["workload_kind"] == "pytest"
    # Support both schema v2 (flat: project_share at top level) and legacy (nested under "signal").
    workload_entry = hotspots["by_workload"][0]
    if "signal" in workload_entry:
        assert 0.0 <= workload_entry["signal"]["project_share"] <= 1.0
        assert 0.0 <= workload_entry["signal"]["target_share"] <= 1.0
    else:
        assert 0.0 <= workload_entry["project_share"] <= 1.0
        assert 0.0 <= workload_entry["target_share"] <= 1.0
    if hotspots["top_functions"]:
        assert 0.0 <= hotspots["top_functions"][0]["share"] <= 1.0
        assert hotspots["top_functions"][0]["avg_cost_us"] >= 0.0


def test_baseline_rejects_non_positive_repetitions(sample_project):
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--repetitions",
            "0",
            "--no-dashboard",
        ],
    )
    assert result.exit_code != 0
    assert "--repetitions must be >= 1" in result.output


def test_baseline_help_includes_path_and_function_guidance():
    result = runner.invoke(app, ["baseline", "--help"])
    assert result.exit_code == 0, result.output
    assert "Path to a target .py file or project root" in result.output
    assert "module.func" in result.output


def test_baseline_reuses_measurement_cache(sample_project):
    command = [
        "baseline",
        str(sample_project / "sample_pkg" / "algos.py"),
        "--function",
        "membership_total",
        "--tests",
        "tests/test_algos.py::test_membership_total",
        "--no-dashboard",
    ]
    first = runner.invoke(app, command)
    assert first.exit_code == 0, first.output

    second = runner.invoke(app, command)
    assert second.exit_code == 0, second.output
    assert "cache" in second.output.lower()


def test_baseline_command_with_new_property_workload(sample_project):
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "algos.py"),
            "--function",
            "counter_histogram",
            "--properties",
            "sample_pkg.properties:property_counter_histogram",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "property::sample_pkg.properties:property_counter_histogram" in result.output


def test_baseline_command_with_new_harness_workload(sample_project):
    result = runner.invoke(
        app,
        [
            "baseline",
            str(sample_project / "sample_pkg" / "complex_cases.py"),
            "--function",
            "warehouse_balancing_pipeline",
            "--harness",
            "sample_pkg.harnesses:warehouse_pipeline_harness",
            "--no-dashboard",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "harness::sample_pkg.harnesses:warehouse_pipeline_harness" in result.output
