"""Tests for summarize_harness — total_external_functions accuracy, share calc."""
from __future__ import annotations

import pytest

from joule.profiling.summarize import summarize_harness, PROJECT_LIKE_BUCKETS


def _fn(file: str, function: str, ownership: str, time: float, calls: int = 10) -> dict:
    return {
        "file": file,
        "function": function,
        "ownership": ownership,
        "cumulative_time_s": time,
        "total_calls": calls,
    }


class TestSummarizeHarness:
    def test_basic_share_calculation(self) -> None:
        fns = [
            _fn("/proj/a.py", "proj_fn", "project", 0.8),
            _fn("/usr/lib/os.py", "os_fn", "stdlib-or-site", 0.2),
        ]
        ownership = {"project": 0.8, "stdlib-or-site": 0.2}
        result = summarize_harness(fns, ownership)
        assert result.share == pytest.approx(0.2)
        assert result.total_time_s == pytest.approx(0.2)

    def test_total_external_functions_counts_non_project(self) -> None:
        fns = [
            _fn("/proj/a.py", "a", "project", 0.5),
            _fn("/usr/lib/os.py", "b", "stdlib-or-site", 0.2),
            _fn("/ext/lib.py", "c", "external", 0.1),
            _fn("/ext/lib2.py", "d", "external", 0.1),
        ]
        ownership = {"project": 0.5, "stdlib-or-site": 0.2, "external": 0.2}
        result = summarize_harness(fns, ownership)
        assert result.total_external_functions == 3  # b, c, d

    def test_total_external_functions_with_explicit_count(self) -> None:
        fns = [
            _fn("/usr/lib/os.py", "b", "stdlib-or-site", 0.2),
        ]
        ownership = {"stdlib-or-site": 0.2}
        # Pass explicit count (simulating pre-sliced list)
        result = summarize_harness(fns, ownership, total_non_project_count=50)
        assert result.total_external_functions == 50

    def test_top_calls_limited_by_limit_param(self) -> None:
        fns = [_fn(f"/lib/{i}.py", f"fn{i}", "stdlib-or-site", float(i) * 0.1)
               for i in range(10)]
        ownership = {"stdlib-or-site": 5.0}
        result = summarize_harness(fns, ownership, limit=3)
        assert len(result.top_calls) <= 3

    def test_top_calls_have_required_fields(self) -> None:
        fns = [_fn("/usr/lib/os.py", "os_fn", "stdlib-or-site", 0.5)]
        ownership = {"stdlib-or-site": 0.5}
        result = summarize_harness(fns, ownership)
        for call in result.top_calls:
            assert "function" in call
            assert "file" in call
            assert "time_s" in call
            assert "calls" in call

    def test_all_project_functions_zero_harness(self) -> None:
        fns = [_fn("/proj/a.py", "a", "project", 1.0)]
        ownership = {"project": 1.0}
        result = summarize_harness(fns, ownership)
        assert result.total_time_s == pytest.approx(0.0)
        assert result.share == pytest.approx(0.0)
        assert result.total_external_functions == 0

    def test_candidate_overlay_treated_as_project(self) -> None:
        fns = [
            _fn("/overlay/a.py", "a", "candidate-overlay", 0.9),
            _fn("/usr/lib/os.py", "b", "stdlib-or-site", 0.1),
        ]
        ownership = {"candidate-overlay": 0.9, "stdlib-or-site": 0.1}
        result = summarize_harness(fns, ownership)
        # candidate-overlay is project-like, so only stdlib counts as harness
        assert result.total_external_functions == 1
        assert result.total_time_s == pytest.approx(0.1)

    def test_empty_functions_list(self) -> None:
        result = summarize_harness([], {})
        assert result.total_time_s == pytest.approx(0.0)
        assert result.share == pytest.approx(0.0)
        assert result.top_calls == []

    def test_to_dict_serialization(self) -> None:
        fns = [_fn("/usr/lib/os.py", "fn", "stdlib-or-site", 0.5)]
        ownership = {"stdlib-or-site": 0.5}
        result = summarize_harness(fns, ownership)
        d = result.to_dict()
        assert "total_time_s" in d
        assert "share" in d
        assert "top_calls" in d
        assert "total_external_functions" in d
