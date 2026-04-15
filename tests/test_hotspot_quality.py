from __future__ import annotations

from pathlib import Path

from joule.utils.analysis import summarize_hotspots


def _function_entry(
    *,
    file: Path | str,
    line: int,
    function: str,
    ownership: str,
    cumulative: float,
    total: float,
    calls: int,
) -> dict:
    return {
        "file": str(file),
        "line": line,
        "function": function,
        "ownership": ownership,
        "cumulative_time_s": cumulative,
        "total_time_s": total,
        "total_calls": calls,
    }


def _ownership_entry(bucket: str, cumulative: float) -> dict:
    return {"bucket": bucket, "cumulative_time_s": cumulative}


def test_hotspot_summary_marks_low_signal_for_target_dilution(tmp_path: Path):
    target_file = tmp_path / "sample_pkg" / "algos.py"

    records = [
        {
            "workload_id": "pytest::sample",
            "workload_kind": "pytest",
            "workload_label": "sample",
            "workload_selector": "tests/test_algos.py::test_membership_total",
            "success": True,
            "stderr": "",
            "profile": {
                "functions": [
                    _function_entry(
                        file=target_file,
                        line=12,
                        function="membership_total",
                        ownership="project",
                        cumulative=0.05,
                        total=0.05,
                        calls=12,
                    ),
                    _function_entry(
                        file="/usr/lib/python3.12/unittest/case.py",
                        line=88,
                        function="assertEqual",
                        ownership="stdlib-or-site",
                        cumulative=0.95,
                        total=0.95,
                        calls=120,
                    ),
                ],
                "ownership": [
                    _ownership_entry("stdlib-or-site", 0.95),
                    _ownership_entry("project", 0.05),
                ],
            },
        }
    ]

    summary = summarize_hotspots(records, limit=5, target_file=target_file)

    assert summary["signal_quality"]["low_signal"] is True
    assert "target_file_under_20pct" in summary["signal_quality"]["low_signal_reasons"]
    assert "non_project_dominant" in summary["signal_quality"]["low_signal_reasons"]
    assert summary["recommendations"]
    assert any("Target file contributes under 20%" in rec for rec in summary["recommendations"])
    assert summary["insights"]["strongest_signal_workload"] is not None
    assert summary["insights"]["weakest_signal_workload"] is not None


def test_hotspot_summary_recommends_primary_target_hotspot(tmp_path: Path):
    target_file = tmp_path / "sample_pkg" / "algos.py"

    records = [
        {
            "workload_id": "harness::sample",
            "workload_kind": "harness",
            "workload_label": "sample harness",
            "workload_selector": "sample_pkg.harnesses:membership_harness",
            "success": True,
            "stderr": "",
            "profile": {
                "functions": [
                    _function_entry(
                        file=target_file,
                        line=12,
                        function="membership_total",
                        ownership="project",
                        cumulative=0.8,
                        total=0.8,
                        calls=40,
                    ),
                    _function_entry(
                        file=target_file,
                        line=16,
                        function="_internal_helper",
                        ownership="project",
                        cumulative=0.1,
                        total=0.1,
                        calls=24,
                    ),
                    _function_entry(
                        file="/usr/lib/python3.12/typing.py",
                        line=700,
                        function="cast",
                        ownership="stdlib-or-site",
                        cumulative=0.1,
                        total=0.1,
                        calls=60,
                    ),
                ],
                "ownership": [
                    _ownership_entry("project", 0.9),
                    _ownership_entry("stdlib-or-site", 0.1),
                ],
            },
        }
    ]

    summary = summarize_hotspots(records, limit=5, target_file=target_file)

    assert summary["signal_quality"]["low_signal"] is False
    assert summary["target_top_functions"]
    assert summary["target_top_functions"][0]["function"] == "membership_total"
    assert summary["target_top_functions"][0]["share"] > 0.5
    assert any("Prioritize target hotspot" in rec for rec in summary["recommendations"])
