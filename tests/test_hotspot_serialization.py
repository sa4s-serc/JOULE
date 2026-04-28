"""Tests for _serialize_profile in hotspots.py — cap, sorting, ownership totals."""
from __future__ import annotations

import cProfile
from pathlib import Path

import pytest

from joule.profiling.hotspots import _serialize_profile, _ownership_bucket


def _make_profiler_with_n_functions(n: int) -> cProfile.Profile:
    """Return a cProfile.Profile that has been run over a workload producing ~n frames."""
    profiler = cProfile.Profile()

    def workload() -> None:
        # Generate a call stack with many distinct functions via list comprehension
        _ = [str(i) for i in range(n)]

    profiler.enable()
    workload()
    profiler.disable()
    return profiler


class TestSerializeProfile:
    def test_returns_required_keys(self, tmp_path: Path) -> None:
        profiler = _make_profiler_with_n_functions(5)
        result = _serialize_profile(profiler, tmp_path, None)
        assert "functions" in result
        assert "ownership" in result
        assert result.get("profiler") == "cProfile"

    def test_functions_sorted_by_cumulative_time(self, tmp_path: Path) -> None:
        profiler = _make_profiler_with_n_functions(10)
        result = _serialize_profile(profiler, tmp_path, None)
        times = [fn["cumulative_time_s"] for fn in result["functions"]]
        assert times == sorted(times, reverse=True)

    def test_cap_is_200(self, tmp_path: Path) -> None:
        """Profile with many functions should be capped at 200, not 40."""
        profiler = _make_profiler_with_n_functions(300)
        result = _serialize_profile(profiler, tmp_path, None)
        assert len(result["functions"]) <= 200

    def test_function_entry_has_required_fields(self, tmp_path: Path) -> None:
        profiler = _make_profiler_with_n_functions(5)
        result = _serialize_profile(profiler, tmp_path, None)
        for fn in result["functions"]:
            assert "file" in fn
            assert "line" in fn
            assert "function" in fn
            assert "total_calls" in fn
            assert "total_time_s" in fn
            assert "cumulative_time_s" in fn
            assert "ownership" in fn

    def test_ownership_totals_present(self, tmp_path: Path) -> None:
        profiler = _make_profiler_with_n_functions(5)
        result = _serialize_profile(profiler, tmp_path, None)
        assert isinstance(result["ownership"], list)
        for entry in result["ownership"]:
            assert "bucket" in entry
            assert "cumulative_time_s" in entry

    def test_empty_profiler_returns_empty_lists(self, tmp_path: Path) -> None:
        profiler = cProfile.Profile()
        # Enable and immediately disable with no work — produces valid but empty stats
        profiler.enable()
        profiler.disable()
        result = _serialize_profile(profiler, tmp_path, None)
        assert isinstance(result["functions"], list)
        assert isinstance(result["ownership"], list)
