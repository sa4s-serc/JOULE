from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from joule.models import TargetSpec
from joule.transformers.deterministic import default_deterministic_operators


SNAPSHOT_PATH = Path(__file__).parent / "golden" / "deterministic_operator_snapshots.json"
SNAPSHOTS: dict[str, dict[str, str]] = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
OPERATORS = {operator.name: operator for operator in default_deterministic_operators()}


def _target(source: str) -> TargetSpec:
    return TargetSpec(
        project_root=Path("."),
        module="sample",
        file_path=Path("sample.py"),
        function_name="f",
        qualname="f",
        owner_path=[],
        line_start=1,
        line_end=max(1, source.count("\n") + 1),
        source=source,
    )


def test_snapshot_catalog_matches_registered_operators():
    assert set(SNAPSHOTS) == set(OPERATORS)


@pytest.mark.parametrize("operator_name", sorted(SNAPSHOTS))
def test_deterministic_operator_source_to_source_snapshot(operator_name: str):
    snapshot = SNAPSHOTS[operator_name]
    operator = OPERATORS[operator_name]

    source = snapshot["source"]
    expected = snapshot["expected"]

    results = operator.generate(_target(source))
    assert len(results) == 1, f"{operator_name}: expected one candidate, found {len(results)}"

    candidate = results[0].candidate_source
    ast.parse(candidate)
    assert candidate == expected
