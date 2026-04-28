from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from joule.models import TargetSpec, WorkloadSpec
from joule.profiling.core import ProfilingError, execute_workload
from joule.runtime_helpers.worker import load_target_callable

# Optional line_profiler for granular analysis
try:
    from line_profiler import LineProfiler

    LINE_PROFILER_AVAILABLE = True
except ImportError:
    LineProfiler = None  # type: ignore[assignment,misc]
    LINE_PROFILER_AVAILABLE = False

# line_profiler timer unit: the stats object carries the actual unit per-run,
# so we always read it from stats.unit rather than guessing.
# Fallback is 1e-6 (microseconds) which is the most common platform default.
DEFAULT_TIMER_UNIT_S = 1e-6  # microseconds — correct fallback for most platforms


def _get_timer_unit(stats: Any = None) -> float:
    """Return the timer unit in seconds per tick.

    Prefer reading from the stats object (stats.unit), which line_profiler
    always populates.  Fall back to the module-level constant only when no
    stats object is available.
    """
    if stats is not None and hasattr(stats, "unit"):
        return float(stats.unit)
    try:
        import line_profiler as _lp
        if hasattr(_lp, "get_unit"):
            return float(_lp.get_unit())
    except Exception:
        pass
    return DEFAULT_TIMER_UNIT_S


def _parse_line_stats(stats: Any) -> dict[int, tuple[int, float]]:
    """Parse line_profiler stats into ``{line_number: (hits, time_s)}``.

    line_profiler's ``stats.timings`` is::

        {(filename, first_lineno, func_name): [(lineno, hits, time_ticks), ...]}

    Each inner tuple is ``(lineno, hits, time_ticks)`` — three elements, not two.
    ``time_ticks`` must be multiplied by ``stats.unit`` to get seconds.
    """
    if not stats or not getattr(stats, "timings", None):
        return {}

    timer_unit = _get_timer_unit(stats)
    line_stats: dict[int, tuple[int, float]] = {}

    for _key, timings in stats.timings.items():
        # Each timing entry: (lineno, hits, time_ticks)
        for entry in timings:
            if len(entry) < 3:
                continue
            line_no, hits, time_ticks = entry[0], entry[1], entry[2]
            time_s = time_ticks * timer_unit
            if line_no in line_stats:
                prev_hits, prev_time = line_stats[line_no]
                line_stats[line_no] = (prev_hits + hits, prev_time + time_s)
            else:
                line_stats[line_no] = (hits, time_s)

    return line_stats


def _serialize_line_profile(
    line_profiler: Any, target_obj: Callable[..., Any]
) -> dict[str, Any]:
    """Serialize line profiler statistics for the target function."""
    from joule.utils.code_analysis import (
        analyze_function_ast,
        get_function_line_range,
        map_line_profiler_to_blocks,
    )

    stats = line_profiler.get_stats()
    if not stats or not stats.timings:
        raise ProfilingError(
            "No line profile data captured for target function",
            reason="no_line_timings",
        )

    # Extract timings for target function
    target_code = getattr(target_obj, "__code__", None)
    if not target_code:
        raise ProfilingError(
            "Could not get code object for target function",
            reason="no_code_object",
        )

    # Build line stats dict using the timer unit embedded in the stats object
    timer_unit_s = _get_timer_unit(stats)
    line_stats = _parse_line_stats(stats)

    if not line_stats:
        raise ProfilingError(
            "No line timings captured for target function",
            reason="empty_line_stats",
        )

    # Analyze function structure with AST
    code_blocks: list[dict[str, Any]] = []
    ast_error: str | None = None
    try:
        blocks = analyze_function_ast(target_obj)
        code_blocks = map_line_profiler_to_blocks(line_stats, blocks)
    except Exception as exc:
        ast_error = str(exc)

    # Get function line range
    try:
        line_start, line_end = get_function_line_range(target_obj)
    except Exception:
        line_start = min(line_stats.keys()) if line_stats else 0
        line_end = max(line_stats.keys()) if line_stats else 0

    # Calculate summary — sum across all profiled lines
    total_time = sum(t for _, t in line_stats.values())
    # total_hits: count only lines that belong to the target function's range
    total_hits = sum(h for ln, (h, _) in line_stats.items() if line_start <= ln <= line_end)

    # Raw line metrics for detailed inspection
    raw_line_metrics = [
        {"line": ln, "hits": h, "time_s": round(t, 6)}
        for ln, (h, t) in sorted(line_stats.items())
    ]

    result: dict[str, Any] = {
        "function_name": getattr(target_obj, "__name__", "unknown"),
        "file": getattr(target_code, "co_filename", "unknown"),
        "line_range": [line_start, line_end],
        "total_time_s": round(total_time, 6),
        "total_hits": total_hits,
        "code_blocks": code_blocks,
        "raw_line_count": len(line_stats),
        "raw_line_metrics": raw_line_metrics,
        "timer_unit_s": timer_unit_s,
        "profiler": "line_profiler",
        "profiler_available": True,
    }

    if ast_error:
        result["ast_error"] = ast_error

    return result


def execute_granular_profiling(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    """Execute workload with both function-level and granular line-level profiling.

    Args:
        target: Target specification
        workload: Workload specification
        project_root: Project root path
        overlay_root: Optional overlay path
        inner_repetitions: Number of inner repetitions

    Returns:
        Payload with both cProfile and line-level profile data

    Raises:
        ProfilingError: If line_profiler is not available or profiling fails
    """
    if not LINE_PROFILER_AVAILABLE:
        raise ProfilingError(
            "line_profiler not available. Install with: pip install line_profiler",
            reason="line_profiler_missing",
        )

    # Load the target object for line profiling using load_target_callable
    target_obj: Callable[..., Any] | None = None
    line_profiler: Any = LineProfiler()

    try:
        target_obj = load_target_callable(target, project_root, overlay_root)
    except Exception as exc:
        raise ProfilingError(
            f"Failed to load target for profiling: {exc}",
            reason="target_load_failed",
        ) from exc

    if not callable(target_obj):
        raise ProfilingError(
            f"Target is not callable: {target.qualname}",
            reason="target_not_callable",
        )

    # Add target function to line profiler
    try:
        line_profiler.add_function(target_obj)
    except Exception as exc:
        raise ProfilingError(
            f"Failed to add target to line profiler: {exc}",
            reason="profiler_add_failed",
        ) from exc

    # Enable both profilers
    import cProfile

    cprofiler = cProfile.Profile()
    cprofiler.enable()
    line_profiler.enable()

    try:
        payload = execute_workload(
            target,
            workload,
            project_root=project_root,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
        )
    finally:
        # Disable profilers in reverse order
        line_profiler.disable()
        cprofiler.disable()

    # Serialize cProfile results (function-level)
    from joule.profiling.hotspots import _serialize_profile

    profile_data = _serialize_profile(cprofiler, project_root, overlay_root)

    # Serialize line profiler results (granular)
    try:
        granular_data = _serialize_line_profile(line_profiler, target_obj)
        profile_data["granular"] = granular_data
    except ProfilingError:
        raise
    except Exception as exc:
        raise ProfilingError(
            f"Failed to serialize line profile: {exc}",
            reason="serialization_failed",
        ) from exc

    payload["profile"] = profile_data
    return payload
