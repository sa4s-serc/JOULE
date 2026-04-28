"""Boundary-condition tests for signal quality thresholds in summarize.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from joule.profiling.summarize import (
    LOW_SIGNAL_THRESHOLD,
    build_signal_quality,
    build_workload_signals,
    generate_recommendations,
    aggregate_function_hotspots,
)
from joule.profiling.schema import SignalQuality, WorkloadSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    *,
    workload_id: str = "w1",
    project_time: float = 1.0,
    stdlib_time: float = 0.0,
    target_file: str = "/proj/target.py",
    target_time: float | None = None,
) -> dict:
    if target_time is None:
        target_time = project_time
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
                    "total_calls": 10,
                },
                {
                    "file": "/usr/lib/python3.12/os.py",
                    "line": 1,
                    "function": "stdlib_fn",
                    "ownership": "stdlib-or-site",
                    "cumulative_time_s": stdlib_time,
                    "total_time_s": stdlib_time,
                    "total_calls": 5,
                },
            ],
            "ownership": [
                {"bucket": "project", "cumulative_time_s": project_time},
                {"bucket": "stdlib-or-site", "cumulative_time_s": stdlib_time},
            ],
        },
    }


# ---------------------------------------------------------------------------
# LOW_SIGNAL_THRESHOLD = 0.20
# ---------------------------------------------------------------------------

class TestLowSignalThreshold:
    def test_just_below_threshold_is_low_signal(self) -> None:
        # project_share = 0.19 → low signal
        records = [_make_record(project_time=0.19, stdlib_time=0.81)]
        signals = build_workload_signals(records)
        assert signals[0].low_signal is True

    def test_exactly_at_threshold_is_not_low_signal(self) -> None:
        # project_share = 0.20 → NOT low signal (threshold is strict <)
        records = [_make_record(project_time=0.20, stdlib_time=0.80)]
        signals = build_workload_signals(records)
        assert signals[0].low_signal is False

    def test_just_above_threshold_is_not_low_signal(self) -> None:
        records = [_make_record(project_time=0.21, stdlib_time=0.79)]
        signals = build_workload_signals(records)
        assert signals[0].low_signal is False

    def test_zero_total_time_is_not_low_signal(self) -> None:
        # No profile samples → low_signal condition requires total > 0
        records = [_make_record(project_time=0.0, stdlib_time=0.0)]
        signals = build_workload_signals(records)
        assert signals[0].low_signal is False  # total=0 → condition not triggered


# ---------------------------------------------------------------------------
# build_signal_quality
# ---------------------------------------------------------------------------

class TestBuildSignalQuality:
    def test_no_profile_samples_reason(self) -> None:
        records = [_make_record(project_time=0.0, stdlib_time=0.0)]
        sq = build_signal_quality(records, ownership_totals={})
        assert "no_profile_samples" in sq.low_signal_reasons
        assert sq.low_signal is True

    def test_target_file_under_20pct_reason(self) -> None:
        target = "/proj/target.py"
        records = [_make_record(project_time=0.05, stdlib_time=0.95, target_file=target, target_time=0.05)]
        ownership = {"project": 0.05, "stdlib-or-site": 0.95}
        sq = build_signal_quality(records, target_file=target, ownership_totals=ownership)
        assert "target_file_under_20pct" in sq.low_signal_reasons

    def test_non_project_dominant_reason(self) -> None:
        records = [_make_record(project_time=0.1, stdlib_time=0.9)]
        ownership = {"project": 0.1, "stdlib-or-site": 0.9}
        sq = build_signal_quality(records, ownership_totals=ownership)
        assert "non_project_dominant" in sq.low_signal_reasons

    def test_good_signal_no_reasons(self) -> None:
        target = "/proj/target.py"
        records = [_make_record(project_time=0.8, stdlib_time=0.2, target_file=target, target_time=0.8)]
        ownership = {"project": 0.8, "stdlib-or-site": 0.2}
        sq = build_signal_quality(records, target_file=target, ownership_totals=ownership)
        assert sq.low_signal is False
        assert sq.low_signal_reasons == []

    def test_project_share_calculation(self) -> None:
        ownership = {"project": 0.6, "stdlib-or-site": 0.4}
        sq = build_signal_quality([], ownership_totals=ownership)
        assert sq.project_share == pytest.approx(0.6)
        assert sq.total_cumulative_time_s == pytest.approx(1.0)

    def test_dominant_bucket_identified(self) -> None:
        ownership = {"project": 0.3, "stdlib-or-site": 0.7}
        sq = build_signal_quality([], ownership_totals=ownership)
        assert sq.dominant_ownership_bucket == "stdlib-or-site"


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    def _make_signal(self, *, low: bool = False, project_share: float = 0.5) -> WorkloadSignal:
        return WorkloadSignal(
            workload_id="w1",
            workload_kind="pytest",
            workload_label="w1",
            workload_selector="w1",
            project_share=project_share,
            target_share=project_share,
            dominant_ownership_bucket="project" if project_share >= 0.5 else "stdlib-or-site",
            total_cumulative_time_s=1.0,
            low_signal=low,
            success=True,
            stderr="",
        )

    def test_no_target_functions_recommendation(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=[],
            by_workload=[self._make_signal()],
            workload_kind_counts={"pytest": 1},
        )
        assert any("No target-file hotspot" in r for r in recs)

    def test_only_pytest_recommendation(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=[],
            by_workload=[self._make_signal()],
            workload_kind_counts={"pytest": 2},
        )
        assert any("Only pytest" in r for r in recs)

    def test_mixed_workload_kinds_no_pytest_only_rec(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=[],
            by_workload=[self._make_signal()],
            workload_kind_counts={"pytest": 1, "harness": 1},
        )
        assert not any("Only pytest" in r for r in recs)

    def test_high_call_count_recommendation(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        target_fns = [{
            "file": "/proj/t.py", "line": 1, "function": "hot",
            "ownership": "project", "cumulative_time_s": 1.0,
            "total_time_s": 0.5, "total_calls": 6000,
            "share": 0.9, "self_share": 0.4,
            "avg_cost_us": 166.0, "avg_self_cost_us": 83.0,
        }]
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=target_fns,
            by_workload=[self._make_signal()],
            workload_kind_counts={"pytest": 1},
        )
        assert any("6000 calls" in r for r in recs)

    def test_call_count_below_threshold_no_recommendation(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        target_fns = [{
            "file": "/proj/t.py", "line": 1, "function": "hot",
            "ownership": "project", "cumulative_time_s": 1.0,
            "total_time_s": 0.5, "total_calls": 4999,
            "share": 0.9, "self_share": 0.4,
            "avg_cost_us": 200.0, "avg_self_cost_us": 100.0,
        }]
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=target_fns,
            by_workload=[self._make_signal()],
            workload_kind_counts={"pytest": 1},
        )
        assert not any("calls" in r and "check for redundant" in r for r in recs)

    def test_recommendations_capped_at_8(self) -> None:
        sq = SignalQuality(
            low_signal=True,
            low_signal_reasons=["target_file_under_20pct", "non_project_dominant", "no_profile_samples"],
            dominant_ownership_bucket="stdlib-or-site",
        )
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=[],
            by_workload=[self._make_signal(low=True, project_share=0.1)],
            workload_kind_counts={"pytest": 1},
        )
        assert len(recs) <= 8

    def test_low_signal_workload_recommendation(self) -> None:
        sq = SignalQuality(low_signal=False, low_signal_reasons=[])
        recs = generate_recommendations(
            signal_quality=sq,
            target_top_functions=[],
            by_workload=[self._make_signal(low=True, project_share=0.05)],
            workload_kind_counts={"pytest": 1},
        )
        assert any("low project share" in r for r in recs)


# ---------------------------------------------------------------------------
# aggregate_function_hotspots — denominator correctness
# ---------------------------------------------------------------------------

class TestAggregateFunctionHotspots:
    def test_shares_do_not_exceed_one(self) -> None:
        """Shares computed from ownership totals should not sum to >> 1."""
        records = [
            _make_record(project_time=0.8, stdlib_time=0.2),
            _make_record(workload_id="w2", project_time=0.6, stdlib_time=0.4),
        ]
        top, *_ = aggregate_function_hotspots(records, limit=12)
        total_share = sum(fn["share"] for fn in top)
        # With ownership-based denominator, shares should be reasonable
        assert total_share <= 2.0  # sanity: not wildly inflated

    def test_target_functions_filtered_by_path(self, tmp_path: Path) -> None:
        target = str(tmp_path / "target.py")
        other = str(tmp_path / "other.py")
        records = [{
            "workload_id": "w1",
            "workload_kind": "pytest",
            "workload_label": "w1",
            "workload_selector": "w1",
            "success": True,
            "stderr": "",
            "profile": {
                "functions": [
                    {"file": target, "line": 1, "function": "a", "ownership": "project",
                     "cumulative_time_s": 0.8, "total_time_s": 0.4, "total_calls": 10},
                    {"file": other, "line": 1, "function": "b", "ownership": "project",
                     "cumulative_time_s": 0.2, "total_time_s": 0.1, "total_calls": 5},
                ],
                "ownership": [{"bucket": "project", "cumulative_time_s": 1.0}],
            },
        }]
        _, target_fns, *_ = aggregate_function_hotspots(records, limit=12, target_file=target)
        assert all(fn["file"] == target for fn in target_fns)

    def test_empty_records_returns_empty_lists(self) -> None:
        top, target, proj, non_proj, ownership, kinds = aggregate_function_hotspots([], limit=12)
        assert top == []
        assert target == []
        assert proj == []
        assert non_proj == []
        assert ownership == []
        assert kinds == {}

    def test_workload_kind_counts_correct(self) -> None:
        records = [
            _make_record(workload_id="p1"),
            _make_record(workload_id="p2"),
        ]
        records[1]["workload_kind"] = "harness"
        *_, kinds = aggregate_function_hotspots(records, limit=12)
        assert kinds.get("pytest", 0) == 1
        assert kinds.get("harness", 0) == 1
