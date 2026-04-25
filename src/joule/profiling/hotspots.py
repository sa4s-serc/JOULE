from __future__ import annotations

import cProfile
import pstats
from pathlib import Path
from typing import Any

from joule.models import TargetSpec, WorkloadSpec
from joule.profiling.core import execute_workload


def _ownership_bucket(filename: str, project_root: Path, overlay_root: Path | None) -> str:
    """Classify a file into ownership buckets."""
    if not filename or filename.startswith("~"):
        return "builtin"
    file_path = Path(filename)
    if overlay_root and str(file_path).startswith(str(overlay_root)):
        return "candidate-overlay"
    if str(file_path).startswith(str(project_root)):
        return "project"
    if "/python" in str(file_path).lower() or "lib/python" in str(file_path).lower():
        return "stdlib-or-site"
    return "external"


def _serialize_profile(
    profiler: cProfile.Profile, project_root: Path, overlay_root: Path | None
) -> dict[str, Any]:
    """Serialize cProfile stats into a structured format."""
    stats = pstats.Stats(profiler)
    functions: list[dict[str, Any]] = []
    ownership_totals: dict[str, float] = {}
    raw_stats = getattr(stats, "stats", {})

    for (filename, line_no, function_name), stat in raw_stats.items():
        primitive_calls, total_calls, total_time, cumulative_time, _callers = stat
        ownership = _ownership_bucket(filename, project_root, overlay_root)
        ownership_totals[ownership] = ownership_totals.get(ownership, 0.0) + cumulative_time
        functions.append(
            {
                "file": filename,
                "line": int(line_no),
                "function": function_name,
                "primitive_calls": int(primitive_calls),
                "total_calls": int(total_calls),
                "total_time_s": float(total_time),
                "cumulative_time_s": float(cumulative_time),
                "ownership": ownership,
            }
        )

    functions.sort(key=lambda item: item["cumulative_time_s"], reverse=True)
    ownership_info = [
        {"bucket": bucket, "cumulative_time_s": total}
        for bucket, total in sorted(
            ownership_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return {
        "functions": functions[:40],
        "ownership": ownership_info,
        "profiler": "cProfile",
    }


def execute_hotspot_profiling(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    """Execute workload with function-level profiling only.

    Args:
        target: Target specification
        workload: Workload specification
        project_root: Project root path
        overlay_root: Optional overlay path
        inner_repetitions: Number of inner repetitions

    Returns:
        Payload with cProfile data
    """
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        payload = execute_workload(
            target,
            workload,
            project_root=project_root,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
        )
    finally:
        profiler.disable()

    payload["profile"] = _serialize_profile(profiler, project_root, overlay_root)
    return payload
