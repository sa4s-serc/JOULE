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
