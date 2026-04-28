"""Tests for create_hotspot_summary — schema version, ProfileLevel, edge cases."""
from __future__ import annotations

from pathlib import Path

import pytest

from joule.profiling.schema import (
    ProfileLevel,
    create_hotspot_summary,
    HotspotSchema,
    SignalQuality,
    WorkloadSignal,
    HarnessSummary,
)


def _make_record(
    workload_id: str = "w1",
    project_time: float = 0.8,
    stdlib_time: float = 0.2,
    target_file: str = "/proj/target.py",
    target_time: float = 0.8,
    total_calls: int = 100,
) -> dict:
    return {
        "workload_id": workload_id,
        "workload_kind": "pytest",
        "workload_label": workload_id,
        "workload_selector": workload_id,
        "success": True,
        "stderr": "",
        "profile": {
            "functions": [
                {
                    "file": target_file,
                    "line": 10,
                    "function": "target_fn",
                    "ownership": "project",
                    "cumulative_time_s": target_time,
                    "total_time_s": target_time * 0.5,
                    "total_calls": total_calls,
                },
                {
                    "file": "/usr/lib/python3.12/os.py",
                    "line": 1,
                    "function": "stdlib_fn",
                    "ownership": "stdlib-or-site",
                    "cumulative_time_s": stdlib_time,
                    "total_time_s": stdlib_time,
                    "total_calls": 50,
                },
            ],
            "ownership": [
                {"bucket": "project", "cumulative_time_s": project_time},
                {"bucket": "stdlib-or-site", "cumulative_time_s": stdlib_time},
            ],
        },
    }


class TestSchemaVersion:
    def test_schema_version_is_2(self) -> None:
        result = create_hotspot_summary([], level=ProfileLevel.BASIC)
        assert result["schema_version"] == 2

    def test_schema_version_consistent_with_granular(self) -> None:
        result = create_hotspot_summary([], level=ProfileLevel.GRANULAR)
        assert result["schema_version"] == 2


class TestRequiredTopLevelKeys:
    def test_basic_level_has_all_required_keys(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        for key in (
            "schema_version", "by_workload", "top_functions",
            "target_top_functions", "project_top_functions",
            "non_project_top_functions", "ownership",
            "workload_kind_counts", "signal_quality",
            "insights", "recommendations",
        ):
            assert key in result, f"Missing key: {key}"

    def test_granular_level_without_data_has_no_granular_analysis(self) -> None:
        # Records have no granular data → granular_analysis should be absent
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.GRANULAR)
        assert "granular_analysis" not in result

    def test_basic_level_never_has_granular_analysis(self) -> None:
        record = _make_record()
        record["profile"]["granular"] = {
            "function_name": "target_fn",
            "file": "/proj/target.py",
            "line_range": [10, 30],
            "total_time_s": 0.5,
            "total_hits": 100,
            "code_blocks": [],
        }
        result = create_hotspot_summary([record], level=ProfileLevel.BASIC)
        assert "granular_analysis" not in result

    def test_granular_level_with_data_has_granular_analysis(self) -> None:
        record = _make_record()
        record["profile"]["granular"] = {
            "function_name": "target_fn",
            "file": "/proj/target.py",
            "line_range": [10, 30],
            "total_time_s": 0.5,
            "total_hits": 100,
            "code_blocks": [
                {
                    "type": "for_loop",
                    "line_range": [12, 20],
                    "description": "for x in items:",
                    "hits": 50,
                    "time_s": 0.3,
                }
            ],
        }
        result = create_hotspot_summary([record], level=ProfileLevel.GRANULAR)
        assert "granular_analysis" in result


class TestEmptyRecords:
    def test_empty_records_no_crash(self) -> None:
        result = create_hotspot_summary([], level=ProfileLevel.BASIC)
        assert result["top_functions"] == []
        assert result["target_top_functions"] == []
        assert result["by_workload"] == []

    def test_empty_records_signal_quality_has_no_samples(self) -> None:
        result = create_hotspot_summary([], level=ProfileLevel.BASIC)
        sq = result["signal_quality"]
        assert sq["low_signal"] is True
        assert "no_profile_samples" in sq["low_signal_reasons"]


class TestHarnessSummary:
    def test_harness_summary_present(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        assert "harness_summary" in result

    def test_harness_summary_has_required_fields(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        hs = result["harness_summary"]
        assert "total_time_s" in hs
        assert "share" in hs
        assert "top_calls" in hs
        assert "total_external_functions" in hs

    def test_harness_share_between_0_and_1(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        share = result["harness_summary"]["share"]
        assert 0.0 <= share <= 1.0


class TestInsightsStructure:
    def test_insights_has_primary_target_hotspot(self) -> None:
        result = create_hotspot_summary(
            [_make_record(target_time=0.8, project_time=0.8, stdlib_time=0.2)],
            level=ProfileLevel.BASIC,
            target_file="/proj/target.py",
        )
        assert "primary_target_hotspot" in result["insights"]

    def test_insights_has_workload_counts(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        assert result["insights"]["profiled_workload_count"] == 1

    def test_insights_strongest_weakest_same_when_one_workload(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        strongest = result["insights"]["strongest_signal_workload"]
        weakest = result["insights"]["weakest_signal_workload"]
        assert strongest is not None
        assert weakest is not None
        assert strongest["workload_id"] == weakest["workload_id"]


class TestProfilerCapability:
    def test_profiler_capability_present(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        assert "profiler_capability" in result

    def test_function_level_always_true(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        assert result["profiler_capability"]["function_level"] is True

    def test_granular_level_false_without_data(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.GRANULAR)
        assert result["profiler_capability"]["granular_level"] is False


class TestByWorkloadStructure:
    def test_by_workload_entries_have_signal(self) -> None:
        result = create_hotspot_summary([_make_record()], level=ProfileLevel.BASIC)
        for entry in result["by_workload"]:
            # WorkloadSignal.to_dict() fields
            assert "workload_id" in entry
            assert "project_share" in entry
            assert "low_signal" in entry

    def test_by_workload_sorted_by_project_share_descending(self) -> None:
        records = [
            _make_record("w1", project_time=0.9, stdlib_time=0.1),
            _make_record("w2", project_time=0.1, stdlib_time=0.9),
            _make_record("w3", project_time=0.5, stdlib_time=0.5),
        ]
        result = create_hotspot_summary(records, level=ProfileLevel.BASIC)
        shares = [e["project_share"] for e in result["by_workload"]]
        assert shares == sorted(shares, reverse=True)


class TestLimitParameter:
    def test_limit_respected_for_top_functions(self) -> None:
        records = [_make_record()]
        result = create_hotspot_summary(records, limit=1, level=ProfileLevel.BASIC)
        assert len(result["top_functions"]) <= 1

    def test_default_limit_is_12(self) -> None:
        # Create 20 distinct functions
        fns = []
        for i in range(20):
            fns.append({
                "file": f"/proj/mod{i}.py",
                "line": i,
                "function": f"fn{i}",
                "ownership": "project",
                "cumulative_time_s": float(20 - i) * 0.05,
                "total_time_s": 0.01,
                "total_calls": 1,
            })
        record = {
            "workload_id": "w1", "workload_kind": "pytest",
            "workload_label": "w1", "workload_selector": "w1",
            "success": True, "stderr": "",
            "profile": {
                "functions": fns,
                "ownership": [{"bucket": "project", "cumulative_time_s": 1.0}],
            },
        }
        result = create_hotspot_summary([record], level=ProfileLevel.BASIC)
        assert len(result["top_functions"]) <= 12
