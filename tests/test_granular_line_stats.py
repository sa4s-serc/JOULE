"""Tests for _parse_line_stats and _get_timer_unit in granular.py.

These cover the corrected tuple format (lineno, hits, time_ticks) and
timer unit resolution from stats.unit.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from joule.profiling.granular import (
    _parse_line_stats,
    _get_timer_unit,
    DEFAULT_TIMER_UNIT_S,
)


# ---------------------------------------------------------------------------
# _get_timer_unit
# ---------------------------------------------------------------------------

class TestGetTimerUnit:
    def test_reads_unit_from_stats_object(self) -> None:
        stats = SimpleNamespace(unit=1e-6)
        assert _get_timer_unit(stats) == pytest.approx(1e-6)

    def test_reads_unit_as_float(self) -> None:
        stats = SimpleNamespace(unit=1e-9)
        assert _get_timer_unit(stats) == pytest.approx(1e-9)

    def test_none_stats_returns_default(self) -> None:
        result = _get_timer_unit(None)
        assert result == pytest.approx(DEFAULT_TIMER_UNIT_S)

    def test_stats_without_unit_attr_returns_default(self) -> None:
        stats = SimpleNamespace()  # no .unit attribute
        result = _get_timer_unit(stats)
        assert result == pytest.approx(DEFAULT_TIMER_UNIT_S)

    def test_default_is_microseconds(self) -> None:
        # The corrected default should be 1e-6 (microseconds), not 1e-9
        assert DEFAULT_TIMER_UNIT_S == pytest.approx(1e-6)


# ---------------------------------------------------------------------------
# _parse_line_stats — correct (lineno, hits, time_ticks) format
# ---------------------------------------------------------------------------

def _make_stats(timings: dict, unit: float = 1e-6) -> Any:
    """Build a fake stats object matching line_profiler's structure."""
    return SimpleNamespace(timings=timings, unit=unit)


class TestParseLineStats:
    def test_basic_single_line(self) -> None:
        # (lineno, hits, time_ticks) — 3-tuple
        stats = _make_stats({
            ("file.py", 10, "func"): [(15, 100, 500)],  # line 15, 100 hits, 500 ticks
        }, unit=1e-6)
        result = _parse_line_stats(stats)
        assert 15 in result
        hits, time_s = result[15]
        assert hits == 100
        assert time_s == pytest.approx(500 * 1e-6)

    def test_multiple_lines_in_same_function(self) -> None:
        stats = _make_stats({
            ("file.py", 10, "func"): [
                (10, 1, 100),   # line 10
                (11, 50, 2000), # line 11
                (12, 50, 1500), # line 12
            ],
        }, unit=1e-6)
        result = _parse_line_stats(stats)
        assert set(result.keys()) == {10, 11, 12}
        assert result[11][0] == 50
        assert result[11][1] == pytest.approx(2000 * 1e-6)

    def test_same_line_across_multiple_keys_accumulated(self) -> None:
        # Two different function keys both have line 20
        stats = _make_stats({
            ("file.py", 10, "func_a"): [(20, 30, 300)],
            ("file.py", 10, "func_b"): [(20, 70, 700)],
        }, unit=1e-6)
        result = _parse_line_stats(stats)
        assert result[20][0] == 100   # 30 + 70
        assert result[20][1] == pytest.approx(1000 * 1e-6)  # 300 + 700

    def test_empty_timings_returns_empty(self) -> None:
        stats = _make_stats({})
        assert _parse_line_stats(stats) == {}

    def test_none_stats_returns_empty(self) -> None:
        assert _parse_line_stats(None) == {}

    def test_stats_with_no_timings_attr_returns_empty(self) -> None:
        stats = SimpleNamespace()  # no .timings
        assert _parse_line_stats(stats) == {}

    def test_short_entry_skipped(self) -> None:
        # Entry with fewer than 3 elements should be skipped gracefully
        stats = _make_stats({
            ("file.py", 10, "func"): [(10, 5)],  # only 2 elements — malformed
        }, unit=1e-6)
        result = _parse_line_stats(stats)
        assert result == {}

    def test_timer_unit_applied_correctly(self) -> None:
        # With unit=1e-3 (milliseconds), 1000 ticks = 1.0 second
        stats = _make_stats({
            ("file.py", 10, "func"): [(10, 1, 1000)],
        }, unit=1e-3)
        result = _parse_line_stats(stats)
        assert result[10][1] == pytest.approx(1.0)

    def test_line_numbers_are_per_line_not_function_start(self) -> None:
        """Critical: line numbers come from the timing entries, not the key."""
        # Key has first_lineno=10, but timing entries have lines 15, 16, 17
        stats = _make_stats({
            ("file.py", 10, "func"): [
                (15, 10, 100),
                (16, 20, 200),
                (17, 30, 300),
            ],
        }, unit=1e-6)
        result = _parse_line_stats(stats)
        # Should have lines 15, 16, 17 — NOT line 10 (the function start)
        assert 10 not in result
        assert 15 in result
        assert 16 in result
        assert 17 in result
