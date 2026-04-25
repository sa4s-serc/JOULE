"""Memory profiling using tracemalloc for granular hotspot analysis.

This module provides memory allocation tracking at the line level
to enrich hotspot analysis with memory metrics.
"""

from __future__ import annotations

import tracemalloc
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from joule.profiling.core import ProfilingError
from joule.profiling.schema import MemoryMetrics


def _format_size(num: int, suffix: str = "B") -> str:
    """Convert bytes to human readable format."""
    for unit in ("", "Ki", "Mi", "Gi", "Ti"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Pi{suffix}"


class MemoryProfiler:
    """Context manager for memory profiling using tracemalloc."""

    def __init__(self, top_n: int = 25) -> None:
        self.top_n = top_n
        self._started = False
        self._snapshot_start: tracemalloc.Snapshot | None = None

    def __enter__(self) -> MemoryProfiler:
        """Start memory profiling."""
        tracemalloc.start()
        self._started = True
        self._snapshot_start = tracemalloc.take_snapshot()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop memory profiling."""
        if self._started:
            tracemalloc.stop()
            self._started = False

    def get_snapshot(self) -> tracemalloc.Snapshot | None:
        """Get current memory snapshot."""
        if not self._started:
            return None
        return tracemalloc.take_snapshot()

    def get_peak_memory(self) -> tuple[int, int]:
        """Get peak memory usage (current, peak).

        Returns:
            Tuple of (current_size_bytes, peak_size_bytes)
        """
        if not self._started:
            return 0, 0
        current, peak = tracemalloc.get_traced_memory()
        return current, peak

    def get_line_stats(
        self,
        filter_filename: str | None = None,
    ) -> dict[int, dict[str, Any]]:
        """Get per-line memory statistics.

        Args:
            filter_filename: Optional filename to filter results

        Returns:
            Dictionary mapping line_number -> memory stats dict
        """
        if not self._started:
            return {}

        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")

        line_stats: dict[int, dict[str, Any]] = defaultdict(
            lambda: {
                "size_bytes": 0,
                "count": 0,
                "tracebacks": [],
            }
        )

        for stat in stats:
            # Access Frame object attributes
            frame = stat.traceback[-1]
            filename = frame.filename
            lineno = frame.lineno

            # Filter by filename if provided
            if filter_filename and filter_filename not in filename:
                continue

            line_stats[lineno]["size_bytes"] += stat.size
            line_stats[lineno]["count"] += stat.count
            line_stats[lineno]["tracebacks"].append(
                {
                    "file": filename,
                    "line": lineno,
                    "size": stat.size,
                    "count": stat.count,
                }
            )

        return dict(line_stats)

    def get_top_allocations(
        self,
        n: int | None = None,
        filter_filename: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get top memory allocations.

        Args:
            n: Number of top allocations to return (default: self.top_n)
            filter_filename: Optional filename to filter results

        Returns:
            List of allocation records with line info
        """
        n = n or self.top_n
        if not self._started:
            return []

        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")

        results: list[dict[str, Any]] = []
        for stat in stats[:n]:
            # Access Frame object attributes
            frame = stat.traceback[-1]
            filename = frame.filename
            lineno = frame.lineno

            # Filter by filename if provided
            if filter_filename and filter_filename not in filename:
                continue

            results.append({
                "file": filename,
                "line": lineno,
                "size_bytes": stat.size,
                "count": stat.count,
                "size_human": _format_size(stat.size),
            })

        return results

    def get_memory_diff(self) -> dict[str, Any]:
        """Get memory difference since profiler started.

        Returns:
            Dictionary with memory diff statistics
        """
        if not self._started or not self._snapshot_start:
            return {
                "size_diff_bytes": 0,
                "count_diff": 0,
                "peak_memory_bytes": 0,
            }

        snapshot_now = tracemalloc.take_snapshot()
        top_stats = snapshot_now.compare_to(self._snapshot_start, "lineno")

        total_size_diff = 0
        total_count_diff = 0

        for stat in top_stats:
            total_size_diff += stat.size_diff
            total_count_diff += stat.count_diff

        _, peak = tracemalloc.get_traced_memory()

        return {
            "size_diff_bytes": total_size_diff,
            "count_diff": total_count_diff,
            "peak_memory_bytes": peak,
        }


def create_memory_metrics(
    line_stats: dict[int, dict[str, Any]],
    line_range: tuple[int, int],
) -> MemoryMetrics:
    """Create MemoryMetrics from line-level tracemalloc stats.

    Args:
        line_stats: Dictionary mapping line_number -> memory stats
        line_range: (start_line, end_line) of the code block

    Returns:
        MemoryMetrics for the block
    """
    peak_bytes = 0
    total_allocations = 0
    allocation_count = 0

    for line_num, stats in line_stats.items():
        if line_range[0] <= line_num <= line_range[1]:
            peak_bytes = max(peak_bytes, stats.get("size_bytes", 0))
            total_allocations += stats.get("size_bytes", 0)
            allocation_count += stats.get("count", 0)

    return MemoryMetrics(
        peak_memory_bytes=peak_bytes,
        total_allocations=total_allocations,
        allocation_count=allocation_count,
        free_count=0,  # tracemalloc doesn't track frees directly
        net_memory_bytes=total_allocations,
        memory_min_bytes=0,
        memory_max_bytes=peak_bytes,
        workload_count=1,
    )


def merge_memory_metrics(metrics_list: list[MemoryMetrics]) -> MemoryMetrics:
    """Merge multiple MemoryMetrics (e.g., from multiple workloads).

    Args:
        metrics_list: List of MemoryMetrics to merge

    Returns:
        Merged MemoryMetrics
    """
    if not metrics_list:
        return MemoryMetrics()

    total_peak = max(m.peak_memory_bytes for m in metrics_list)
    total_allocs = sum(m.total_allocations for m in metrics_list)
    total_count = sum(m.allocation_count for m in metrics_list)
    total_free = sum(m.free_count for m in metrics_list)

    all_mins = [m.memory_min_bytes for m in metrics_list if m.memory_min_bytes > 0]
    all_maxs = [m.memory_max_bytes for m in metrics_list if m.memory_max_bytes > 0]

    return MemoryMetrics(
        peak_memory_bytes=total_peak,
        total_allocations=total_allocs,
        allocation_count=total_count // max(len(metrics_list), 1),
        free_count=total_free // max(len(metrics_list), 1),
        net_memory_bytes=total_allocs - total_free,
        memory_min_bytes=min(all_mins) if all_mins else 0,
        memory_max_bytes=max(all_maxs) if all_maxs else total_peak,
        workload_count=len(metrics_list),
    )
