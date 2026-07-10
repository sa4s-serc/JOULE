"""Tests for JOULE batch optimization command."""

from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from joule.cli import app


def test_batch_command_discovers_and_optimizes(tmp_path: Path):
    # Setup a dummy project structure with pyproject.toml and a python file containing pure function
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.joule]
default_backend = "mock"
optimization_budget = 2
""", encoding="utf-8")

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target_module = src_dir / "target_module.py"
    target_module.write_text("""
def fast_sum(items):
    # Simple target with a loop for discovery
    s = 0
    for x in items:
        s += x
    return s
""", encoding="utf-8")

    # Add a mock pytest file to allow executing workloads
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    pytest_file = tests_dir / "test_target.py"
    pytest_file.write_text("""
from target_module import fast_sum
def test_fast_sum():
    assert fast_sum([1, 2, 3]) == 6
""", encoding="utf-8")

    runner = CliRunner()
    # Execute "joule batch" command
    result = runner.invoke(app, ["batch", str(tmp_path), "--budget", "1", "--verbose"])

    assert result.exit_code == 0
    assert "Batch Optimization Report" in result.stdout
    assert "fast_sum" in result.stdout

