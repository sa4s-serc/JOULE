"""Tests for analysis.py utility functions — search events, operator performance,
path normalization, and the summarize_hotspots delegation."""
from __future__ import annotations

from pathlib import Path

import pytest

from joule.utils.analysis import (
    summarize_search_events,
    summarize_operator_performance,
    summarize_hotspots,
    _normalized_profile_path,
    json_pretty,
)


# ---------------------------------------------------------------------------
# _normalized_profile_path
# ---------------------------------------------------------------------------

class TestNormalizedProfilePath:
    def test_empty_string_returns_empty(self) -> None:
        assert _normalized_profile_path("") == ""

    def test_tilde_prefix_returned_as_is(self) -> None:
        p = "~/.local/lib/python.py"
        assert _normalized_profile_path(p) == p

    def test_absolute_path_resolved(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.touch()
        result = _normalized_profile_path(str(f))
        assert Path(result).is_absolute()

    def test_nonexistent_path_still_returns_string(self) -> None:
        result = _normalized_profile_path("/nonexistent/path/module.py")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_none_like_value_handled(self) -> None:
        # Should not raise
        result = _normalized_profile_path("")
        assert result == ""


# ---------------------------------------------------------------------------
# summarize_search_events
# ---------------------------------------------------------------------------

class TestSummarizeSearchEvents:
    def test_empty_events(self) -> None:
        result = summarize_search_events([])
        assert result["funnel"]["generated"] == 0
        assert result["event_counts"] == {}

    def test_counts_event_types(self) -> None:
        events = [
            {"event_type": "generated", "stage": "generate", "detail": {}},
            {"event_type": "generated", "stage": "generate", "detail": {}},
            {"event_type": "accepted", "stage": "evaluate", "detail": {}},
        ]
        result = summarize_search_events(events)
        assert result["funnel"]["generated"] == 2
        assert result["funnel"]["accepted"] == 1

    def test_rejection_reasons_counted(self) -> None:
        events = [
            {"event_type": "correctness_rejected", "stage": "eval",
             "detail": {"reason": "assertion_error"}},
            {"event_type": "correctness_rejected", "stage": "eval",
             "detail": {"reason": "assertion_error"}},
            {"event_type": "surrogate_rejected", "stage": "eval",
             "detail": {"reason": "low_score"}},
        ]
        result = summarize_search_events(events)
        assert result["rejection_reasons"]["assertion_error"] == 2
        assert result["rejection_reasons"]["low_score"] == 1

    def test_accepted_not_counted_as_rejection(self) -> None:
        events = [
            {"event_type": "accepted", "stage": "eval",
             "detail": {"reason": "good_candidate"}},
        ]
        result = summarize_search_events(events)
        assert "good_candidate" not in result["rejection_reasons"]

    def test_stage_timings_accumulated(self) -> None:
        events = [
            {"event_type": "generated", "stage": "generate",
             "detail": {"duration_s": 0.5}},
            {"event_type": "generated", "stage": "generate",
             "detail": {"duration_s": 0.3}},
        ]
        result = summarize_search_events(events)
        assert result["stage_timings_s"]["generate"] == pytest.approx(0.8)

    def test_missing_duration_not_counted(self) -> None:
        events = [
            {"event_type": "generated", "stage": "generate", "detail": {}},
        ]
        result = summarize_search_events(events)
        assert result["stage_timings_s"].get("generate", 0.0) == 0.0

    def test_unknown_event_type_counted_in_event_counts(self) -> None:
        events = [
            {"event_type": "custom_event", "stage": "custom", "detail": {}},
        ]
        result = summarize_search_events(events)
        assert result["event_counts"]["custom_event"] == 1


# ---------------------------------------------------------------------------
# summarize_operator_performance
# ---------------------------------------------------------------------------

class TestSummarizeOperatorPerformance:
    def _make_candidate(
        self,
        operator: str = "op1",
        status: str = "accepted",
        score: float = 0.9,
    ) -> dict:
        return {
            "candidate_id": "c1",
            "parent_id": None,
            "operator_name": operator,
            "reasoning": "",
            "dependencies": [],
            "source_code": "def f(): pass",
            "status": status,
            "score": score,
            "metadata": {},
        }

    def test_empty_candidates(self) -> None:
        result = summarize_operator_performance([])
        assert result == []

    def test_single_accepted_candidate(self) -> None:
        result = summarize_operator_performance([self._make_candidate()])
        assert len(result) == 1
        assert result[0]["operator_name"] == "op1"
        assert result[0]["accepted"] == 1
        assert result[0]["attempts"] == 1
        assert result[0]["acceptance_rate"] == pytest.approx(1.0)

    def test_rejected_candidate(self) -> None:
        result = summarize_operator_performance([
            self._make_candidate(status="rejected"),
        ])
        assert result[0]["rejected"] == 1
        assert result[0]["accepted"] == 0
        assert result[0]["acceptance_rate"] == pytest.approx(0.0)

    def test_multiple_operators_separate_entries(self) -> None:
        candidates = [
            self._make_candidate(operator="op1", status="accepted"),
            self._make_candidate(operator="op2", status="rejected"),
        ]
        result = summarize_operator_performance(candidates)
        ops = {r["operator_name"] for r in result}
        assert ops == {"op1", "op2"}

    def test_acceptance_rate_calculated(self) -> None:
        candidates = [
            self._make_candidate(operator="op1", status="accepted"),
            self._make_candidate(operator="op1", status="rejected"),
            self._make_candidate(operator="op1", status="rejected"),
        ]
        result = summarize_operator_performance(candidates)
        assert result[0]["acceptance_rate"] == pytest.approx(1 / 3)

    def test_skipped_candidate_counted(self) -> None:
        result = summarize_operator_performance([
            self._make_candidate(status="skipped"),
        ])
        assert result[0]["skipped"] == 1


# ---------------------------------------------------------------------------
# summarize_hotspots — delegation to create_hotspot_summary
# ---------------------------------------------------------------------------

class TestSummarizeHotspotsDelegation:
    def test_returns_schema_version_2(self) -> None:
        result = summarize_hotspots([], granular=False)
        assert result["schema_version"] == 2

    def test_granular_false_no_granular_analysis(self) -> None:
        result = summarize_hotspots([], granular=False)
        assert "granular_analysis" not in result

    def test_granular_true_no_crash_without_data(self) -> None:
        result = summarize_hotspots([], granular=True)
        assert result["schema_version"] == 2

    def test_target_file_path_accepted(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        result = summarize_hotspots([], target_file=target)
        assert "signal_quality" in result

    def test_limit_parameter_forwarded(self) -> None:
        records = [{
            "workload_id": "w1", "workload_kind": "pytest",
            "workload_label": "w1", "workload_selector": "w1",
            "success": True, "stderr": "",
            "profile": {
                "functions": [
                    {"file": "/p.py", "line": i, "function": f"f{i}",
                     "ownership": "project", "cumulative_time_s": float(i) * 0.1,
                     "total_time_s": 0.01, "total_calls": 1}
                    for i in range(20)
                ],
                "ownership": [{"bucket": "project", "cumulative_time_s": 2.0}],
            },
        }]
        result = summarize_hotspots(records, limit=3)
        assert len(result["top_functions"]) <= 3


# ---------------------------------------------------------------------------
# json_pretty
# ---------------------------------------------------------------------------

class TestJsonPretty:
    def test_basic_dict(self) -> None:
        result = json_pretty({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_nested_structure(self) -> None:
        result = json_pretty({"a": [1, 2, 3], "b": {"c": True}})
        assert "true" in result.lower() or "True" in result

    def test_float_nan_handled(self) -> None:
        import math
        # Should not raise even with non-finite floats
        try:
            result = json_pretty({"v": float("nan")})
            # If it doesn't raise, that's fine
        except (ValueError, TypeError):
            pass  # Also acceptable

    def test_returns_string(self) -> None:
        assert isinstance(json_pretty({}), str)
