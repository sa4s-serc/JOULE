"""Advanced tests for MemoryProfiler and memory metric helpers."""
from __future__ import annotations

import tracemalloc

import pytest

from joule.profiling.memory import (
    MemoryProfiler,
    create_memory_metrics,
    merge_memory_metrics,
)
from joule.profiling.schema import MemoryMetrics


class TestMemoryProfilerContextManager:
    def test_basic_enter_exit(self) -> None:
        with MemoryProfiler() as mp:
            assert mp._started is True
        assert mp._started is False

    def test_peak_memory_nonzero_during_profiling(self) -> None:
        with MemoryProfiler() as mp:
            _ = [0] * 10_000  # allocate some memory
            current, peak = mp.get_peak_memory()
        assert peak >= 0  # peak is always non-negative

    def test_get_peak_memory_outside_context_returns_zeros(self) -> None:
        mp = MemoryProfiler()
        current, peak = mp.get_peak_memory()
        assert current == 0
        assert peak == 0

    def test_get_snapshot_outside_context_returns_none(self) -> None:
        mp = MemoryProfiler()
        assert mp.get_snapshot() is None

    def test_get_snapshot_inside_context_returns_snapshot(self) -> None:
        with MemoryProfiler() as mp:
            snap = mp.get_snapshot()
        assert snap is not None

    def test_exception_inside_context_stops_profiler(self) -> None:
        mp = MemoryProfiler()
        try:
            with mp:
                raise ValueError("test error")
        except ValueError:
            pass
        assert mp._started is False

    def test_get_memory_diff_outside_context(self) -> None:
        mp = MemoryProfiler()
        diff = mp.get_memory_diff()
        assert diff["size_diff_bytes"] == 0
        assert diff["peak_memory_bytes"] == 0

    def test_get_memory_diff_inside_context(self) -> None:
        with MemoryProfiler() as mp:
            _ = bytearray(1024 * 100)  # allocate 100KB
            diff = mp.get_memory_diff()
        assert "size_diff_bytes" in diff
        assert "peak_memory_bytes" in diff

    def test_get_line_stats_outside_context_returns_empty(self) -> None:
        mp = MemoryProfiler()
        assert mp.get_line_stats() == {}

    def test_get_top_allocations_outside_context_returns_empty(self) -> None:
        mp = MemoryProfiler()
        assert mp.get_top_allocations() == []

    def test_tracemalloc_stopped_after_exit(self) -> None:
        with MemoryProfiler():
            assert tracemalloc.is_tracing()
        assert not tracemalloc.is_tracing()


class TestCreateMemoryMetrics:
    def test_basic_creation(self) -> None:
        line_stats = {
            10: {"size_bytes": 1024, "count": 5},
            11: {"size_bytes": 2048, "count": 3},
            15: {"size_bytes": 512, "count": 1},
        }
        metrics = create_memory_metrics(line_stats, line_range=(10, 12))
        assert metrics.peak_memory_bytes == 2048  # max of 1024, 2048
        assert metrics.allocation_count == 8  # 5 + 3
        assert metrics.total_allocations == 3072  # 1024 + 2048

    def test_lines_outside_range_excluded(self) -> None:
        line_stats = {
            5: {"size_bytes": 9999, "count": 100},  # outside range
            10: {"size_bytes": 100, "count": 1},
        }
        metrics = create_memory_metrics(line_stats, line_range=(10, 15))
        assert metrics.peak_memory_bytes == 100
        assert metrics.allocation_count == 1

    def test_empty_line_stats(self) -> None:
        metrics = create_memory_metrics({}, line_range=(1, 10))
        assert metrics.peak_memory_bytes == 0
        assert metrics.allocation_count == 0

    def test_workload_count_is_one(self) -> None:
        metrics = create_memory_metrics({10: {"size_bytes": 100, "count": 1}}, (10, 10))
        assert metrics.workload_count == 1


class TestMergeMemoryMetrics:
    def test_empty_list_returns_default(self) -> None:
        result = merge_memory_metrics([])
        assert result.peak_memory_bytes == 0
        assert result.workload_count == 0

    def test_single_metric_passthrough(self) -> None:
        m = MemoryMetrics(
            peak_memory_bytes=1000,
            total_allocations=500,
            allocation_count=10,
            workload_count=1,
        )
        result = merge_memory_metrics([m])
        assert result.peak_memory_bytes == 1000
        assert result.workload_count == 1

    def test_peak_is_max_across_metrics(self) -> None:
        metrics = [
            MemoryMetrics(peak_memory_bytes=100, workload_count=1),
            MemoryMetrics(peak_memory_bytes=500, workload_count=1),
            MemoryMetrics(peak_memory_bytes=200, workload_count=1),
        ]
        result = merge_memory_metrics(metrics)
        assert result.peak_memory_bytes == 500

    def test_total_allocations_summed(self) -> None:
        metrics = [
            MemoryMetrics(total_allocations=100, workload_count=1),
            MemoryMetrics(total_allocations=200, workload_count=1),
        ]
        result = merge_memory_metrics(metrics)
        assert result.total_allocations == 300

    def test_workload_count_is_list_length(self) -> None:
        metrics = [MemoryMetrics(workload_count=1) for _ in range(5)]
        result = merge_memory_metrics(metrics)
        assert result.workload_count == 5

    def test_to_dict_has_required_keys(self) -> None:
        m = MemoryMetrics(peak_memory_bytes=1024, allocation_count=5)
        d = m.to_dict()
        for key in ("peak_memory_bytes", "total_allocations", "allocation_count",
                    "free_count", "net_memory_bytes", "workload_count"):
            assert key in d
