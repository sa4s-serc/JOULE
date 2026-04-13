from __future__ import annotations

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
    assert '"hotspots"' in result.output


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
