from __future__ import annotations

import cProfile
import os
import pstats
from pathlib import Path
from typing import Any

from joule.models import TargetSpec, WorkloadSpec
from joule.profiling.core import execute_workload


def _ownership_bucket(filename: str, project_root: Path, overlay_root: Path | None) -> str:
    """Classify a file into ownership buckets.

    Order of checks matters:
    1. Builtins / frozen modules (no real path)
    2. Candidate overlay (must beat project_root check)
    3. Virtual-env inside project root — must be stdlib-or-site, not project
    4. Project source
    5. stdlib / site-packages anywhere else on the path
    6. Everything else → external
    """
    if not filename or filename.startswith("~") or filename.startswith("<"):
        return "builtin"
    file_path = Path(filename)
    file_str = str(file_path)
    if overlay_root and file_str.startswith(str(overlay_root)):
        return "candidate-overlay"
    # Exclude common virtual-env directories that live inside the project root
    _venv_markers = (
        f"{file_str}{os.sep}.venv{os.sep}",
        f"{os.sep}.venv{os.sep}",
        f"{os.sep}venv{os.sep}",
        f"{os.sep}.env{os.sep}",
        f"{os.sep}site-packages{os.sep}",
    )
    is_venv = any(marker in file_str for marker in _venv_markers) or (
        os.sep + ".venv" + os.sep in file_str
        or "/site-packages/" in file_str
    )
    if not is_venv and file_str.startswith(str(project_root)):
        return "project"
    if "/python" in file_str.lower() or "lib/python" in file_str.lower() or is_venv:
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
        "functions": functions[:200],
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
