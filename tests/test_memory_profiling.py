"""Tests for memory profiling module."""

from __future__ import annotations

import pytest

from joule.profiling import TRACEMALLOC_AVAILABLE, MemoryMetrics, MemoryProfiler, create_memory_metrics


def test_tracemalloc_available() -> None:
    """Test that tracemalloc is available (should always be true in Python 3.4+)."""
    assert TRACEMALLOC_AVAILABLE is True


def test_memory_metrics_defaults() -> None:
    """Test MemoryMetrics default values."""
    metrics = MemoryMetrics()
    assert metrics.peak_memory_bytes == 0
    assert metrics.total_allocations == 0
    assert metrics.allocation_count == 0
    assert metrics.free_count == 0
    assert metrics.net_memory_bytes == 0
    assert metrics.memory_min_bytes == 0
    assert metrics.memory_max_bytes == 0
    assert metrics.workload_count == 0


def test_memory_metrics_to_dict() -> None:
    """Test MemoryMetrics serialization."""
    metrics = MemoryMetrics(
        peak_memory_bytes=1024 * 1024,  # 1 MiB
        total_allocations=2048 * 1024,
        allocation_count=100,
        free_count=50,
        net_memory_bytes=1024 * 1024,
        memory_min_bytes=512 * 1024,
        memory_max_bytes=1024 * 1024,
        workload_count=3,
    )
    d = metrics.to_dict()
    assert d["peak_memory_bytes"] == 1048576
    assert d["total_allocations"] == 2097152
    assert d["allocation_count"] == 100
    assert d["free_count"] == 50
    assert d["net_memory_bytes"] == 1048576
    assert d["memory_min_bytes"] == 524288
    assert d["memory_max_bytes"] == 1048576
    assert d["workload_count"] == 3


def test_memory_profiler_context_manager() -> None:
    """Test MemoryProfiler context manager."""
    if not TRACEMALLOC_AVAILABLE:
        pytest.skip("tracemalloc not available")

    with MemoryProfiler() as profiler:
        # Allocate some memory
        data = [0] * 10000
        current, peak = profiler.get_peak_memory()
        assert current > 0
        assert peak > 0


def test_memory_profiler_line_stats() -> None:
    """Test that line stats can be retrieved."""
    if not TRACEMALLOC_AVAILABLE:
        pytest.skip("tracemalloc not available")

    with MemoryProfiler() as profiler:
        # Allocate some memory
        data = [0] * 10000  # noqa: F841
        stats = profiler.get_line_stats()
        # Should have some stats (may be empty depending on Python version)
        assert isinstance(stats, dict)


def test_create_memory_metrics() -> None:
    """Test creating MemoryMetrics from line stats."""
    line_stats = {
        10: {"size_bytes": 1024, "count": 5},
        11: {"size_bytes": 2048, "count": 3},
        12: {"size_bytes": 512, "count": 10},
    }

    metrics = create_memory_metrics(line_stats, (10, 12))
    assert metrics.peak_memory_bytes == 2048
    assert metrics.total_allocations == 3584  # 1024 + 2048 + 512
    assert metrics.allocation_count == 18  # 5 + 3 + 10


def test_create_memory_metrics_empty() -> None:
    """Test creating MemoryMetrics from empty line stats."""
    metrics = create_memory_metrics({}, (1, 10))
    assert metrics.peak_memory_bytes == 0
    assert metrics.total_allocations == 0
    assert metrics.allocation_count == 0


def test_memory_profiler_get_memory_diff() -> None:
    """Test memory diff functionality."""
    if not TRACEMALLOC_AVAILABLE:
        pytest.skip("tracemalloc not available")

    with MemoryProfiler() as profiler:
        # Get initial diff
        diff1 = profiler.get_memory_diff()
        assert "size_diff_bytes" in diff1
        assert "count_diff" in diff1
        assert "peak_memory_bytes" in diff1

        # Allocate and get diff again
        data = [0] * 10000  # noqa: F841
        diff2 = profiler.get_memory_diff()
        assert diff2["peak_memory_bytes"] >= diff1["peak_memory_bytes"]
