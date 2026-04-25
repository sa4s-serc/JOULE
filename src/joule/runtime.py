from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import cProfile
import importlib
import io
import json
import os
from pathlib import Path
import pstats
import sys
from typing import Any

from joule.models import TargetSpec, WorkloadKind, WorkloadSpec

# Optional line_profiler for granular analysis
try:
    from line_profiler import LineProfiler
    LINE_PROFILER_AVAILABLE = True
except ImportError:
    LineProfiler = None  # type: ignore
    LINE_PROFILER_AVAILABLE = False
from joule.runtime_helpers.worker import (
    execute_golden_trace_workload,
    execute_harness_workload,
    execute_property_workload,
    execute_pytest_workload,
    extend_runtime_import_paths,
    invoke_worker as invoke_worker_process,
    load_module_for_file_selector,
    resolve_attr_path,
)


def load_object(selector: str, project_root: Path, overlay_root: Path | None = None) -> Any:
    extend_runtime_import_paths(project_root, overlay_root)
    if ".py::" in selector:
        module, object_name = load_module_for_file_selector(selector, project_root)
        return resolve_attr_path(module, object_name)
    module_name, object_name = selector.replace("::", ":").split(":", 1)
    module = importlib.import_module(module_name)
    return resolve_attr_path(module, object_name)


def execute_workload(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    logical_invocations = 0
    payload: dict[str, Any]
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        if workload.kind is WorkloadKind.PYTEST:
            payload, logical_invocations = execute_pytest_workload(
                selector=workload.selector,
                project_root=project_root,
                inner_repetitions=inner_repetitions,
                normalize_selector=_normalize_pytest_selector,
            )
        elif workload.kind is WorkloadKind.PROPERTY:
            payload, logical_invocations = execute_property_workload(
                selector=workload.selector,
                project_root=project_root,
                overlay_root=overlay_root,
                inner_repetitions=inner_repetitions,
                load_object_fn=load_object,
            )
        elif workload.kind is WorkloadKind.HARNESS:
            payload, logical_invocations = execute_harness_workload(
                target=target,
                selector=workload.selector,
                project_root=project_root,
                overlay_root=overlay_root,
                inner_repetitions=inner_repetitions,
                load_object_fn=load_object,
            )
        elif workload.kind is WorkloadKind.GOLDEN_TRACE:
            payload, logical_invocations = execute_golden_trace_workload(
                target=target,
                project_root=project_root,
                overlay_root=overlay_root,
                inner_repetitions=inner_repetitions,
            )
        else:
            raise ValueError(f"Unsupported workload kind: {workload.kind}")
    payload.update(
        {
            "stdout": captured_stdout.getvalue(),
            "stderr": captured_stderr.getvalue(),
            "logical_invocations": logical_invocations,
            "inner_repetitions": inner_repetitions,
        }
    )
    return payload


def invoke_worker(
    target: TargetSpec,
    workload: WorkloadSpec,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
    timeout_s: float = 30.0,
) -> dict:
    command = worker_command(target, workload, overlay_root=overlay_root, inner_repetitions=inner_repetitions)
    return invoke_worker_process(
        command=command,
        env=subprocess_env(target.project_root, overlay_root),
        timeout_s=timeout_s,
        inner_repetitions=inner_repetitions,
        include_profile=False,
    )


def invoke_profile_worker(
    target: TargetSpec,
    workload: WorkloadSpec,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
    timeout_s: float = 30.0,
    profile_mode: str = "hotspots",
) -> dict:
    command = worker_command(
        target,
        workload,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
        profile_mode=profile_mode,
    )
    return invoke_worker_process(
        command=command,
        env=subprocess_env(target.project_root, overlay_root),
        timeout_s=timeout_s,
        inner_repetitions=inner_repetitions,
        include_profile=True,
    )


def worker_command(
    target: TargetSpec,
    workload: WorkloadSpec,
    *,
    overlay_root: Path | None = None,
    inner_repetitions: int = 1,
    profile_mode: str | None = None,
) -> list[str]:
    command = [
        os.environ.get("PYTHON_EXECUTABLE", sys.executable),
        "-m",
        "joule.runtime",
        "--target-json",
        json.dumps(target.to_record()),
        "--workload-json",
        json.dumps(workload.to_record()),
        "--inner-repetitions",
        str(inner_repetitions),
    ]
    if overlay_root:
        command.extend(["--overlay-root", str(overlay_root)])
    if profile_mode:
        command.extend(["--profile-mode", profile_mode])
    return command


def subprocess_env(project_root: Path, overlay_root: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath = []
    repo_src = Path(__file__).resolve().parents[2]
    pythonpath.append(str(repo_src / "src"))
    if overlay_root:
        pythonpath.append(str(overlay_root))
    src_path = project_root / "src"
    if src_path.exists():
        pythonpath.append(str(src_path))
    pythonpath.append(str(project_root))
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


def _normalize_pytest_selector(selector: str, project_root: Path) -> str:
    if "::" not in selector:
        return selector
    file_part, rest = selector.split("::", 1)
    file_path = Path(file_part)
    if not file_path.is_absolute():
        file_path = project_root / file_path
    return f"{file_path}::{rest}"


def execute_workload_with_profile(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    profiler = cProfile.Profile()
    profiler.enable()
    payload = execute_workload(
        target,
        workload,
        project_root=project_root,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
    )
    profiler.disable()
    payload["profile"] = _serialize_profile(profiler, project_root, overlay_root)
    return payload


def execute_workload_with_granular_profile(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    """
    Execute workload with both function-level (cProfile) and line-level profiling.

    Line profiling is applied specifically to the target function to identify
    hotspots within loops, branches, and other code blocks.
    """
    if not LINE_PROFILER_AVAILABLE:
        # Fall back to standard profiling with warning
        payload = execute_workload_with_profile(
            target,
            workload,
            project_root=project_root,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
        )
        payload["profile"] = payload.get("profile", {})
        payload["profile"]["granular_warning"] = (
            "line_profiler not available. "
            "Install with: pip install line_profiler"
        )
        return payload

    # Load the target object for line profiling
    target_obj = None
    line_profiler = LineProfiler()
    try:
        extend_runtime_import_paths(project_root, overlay_root)
        if ".py::" in target.selector:
            module, object_name = load_module_for_file_selector(
                target.selector, project_root
            )
            target_obj = resolve_attr_path(module, object_name)
        else:
            module_name, object_name = target.selector.replace("::", ":").split(":", 1)
            module = importlib.import_module(module_name)
            target_obj = resolve_attr_path(module, object_name)

        # Add target function to line profiler
        if callable(target_obj):
            line_profiler.add_function(target_obj)
    except Exception as exc:
        # If we can't load target, continue with function-level only
        line_profiler = None  # type: ignore

    # Enable both profilers
    cprofiler = cProfile.Profile()
    cprofiler.enable()
    if line_profiler:
        line_profiler.enable()

    payload = execute_workload(
        target,
        workload,
        project_root=project_root,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
    )

    # Disable profilers
    cprofiler.disable()
    if line_profiler:
        line_profiler.disable()

    # Serialize cProfile results (function-level)
    profile_data = _serialize_profile(cprofiler, project_root, overlay_root)

    # Serialize line profiler results (granular)
    if line_profiler and target_obj:
        granular_data = _serialize_line_profile(line_profiler, target_obj)
        profile_data["granular"] = granular_data

    payload["profile"] = profile_data
    return payload


def _serialize_line_profile(
    line_profiler: Any, target_obj: Callable[..., Any]
) -> dict:
    """Serialize line profiler statistics for the target function."""
    try:
        from joule.utils.code_analysis import (
            analyze_function_ast,
            map_line_profiler_to_blocks,
            get_function_line_range,
        )
    except ImportError:
        return {"error": "code_analysis module not available"}

    # Get raw stats from line profiler
    stats = line_profiler.get_stats()
    if not stats or not stats.timings:
        return {"error": "No line profile data available"}

    # Extract timings for target function
    target_code = getattr(target_obj, "__code__", None)
    if not target_code:
        return {"error": "Could not get code object for target"}

    # Build line stats dict: {line_num: (hits, time_s)}
    line_stats: dict[int, tuple[int, float]] = {}
    for key, timings in stats.timings.items():
        # key is (filename, line_number, function_name)
        if len(key) >= 2:
            line_num = key[1]
            # timings is list of (hits, time) in profiler units
            total_hits = 0
            total_time = 0.0
            for hits, time in timings:
                total_hits += hits
                # Convert to seconds (line_profiler uses different units)
                total_time += time / 1e6  # Convert from microseconds to seconds
            line_stats[line_num] = (total_hits, total_time)

    # Analyze function structure with AST
    try:
        code_blocks = analyze_function_ast(target_obj)
    except Exception as exc:
        # If AST analysis fails, return raw line stats
        return {
            "function_name": getattr(target_obj, "__name__", "unknown"),
            "line_stats": [
                {"line": ln, "hits": h, "time_s": round(t, 6)}
                for ln, (h, t) in sorted(line_stats.items())
            ],
            "ast_error": str(exc),
        }

    # Map line stats to code blocks
    try:
        block_metrics = map_line_profiler_to_blocks(line_stats, code_blocks)
    except Exception as exc:
        block_metrics = []

    # Get function line range
    try:
        line_start, line_end = get_function_line_range(target_obj)
    except Exception:
        line_start = min(line_stats.keys()) if line_stats else 0
        line_end = max(line_stats.keys()) if line_stats else 0

    # Calculate summary
    total_time = sum(t for _, (_, t) in line_stats.items())
    total_hits = sum(h for _, (h, _) in line_stats.items())

    return {
        "function_name": getattr(target_obj, "__name__", "unknown"),
        "file": getattr(target_code, "co_filename", "unknown"),
        "line_range": [line_start, line_end],
        "total_time_s": round(total_time, 6),
        "total_hits": total_hits,
        "code_blocks": block_metrics,
        "raw_line_count": len(line_stats),
    }


def _serialize_profile(profiler: cProfile.Profile, project_root: Path, overlay_root: Path | None) -> dict:
    stats = pstats.Stats(profiler)
    functions = []
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
        for bucket, total in sorted(ownership_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    return {"functions": functions[:40], "ownership": ownership_info}


def _ownership_bucket(filename: str, project_root: Path, overlay_root: Path | None) -> str:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-json", required=True)
    parser.add_argument("--workload-json", required=True)
    parser.add_argument("--overlay-root")
    parser.add_argument("--inner-repetitions", type=int, default=1)
    parser.add_argument("--profile-mode")
    args = parser.parse_args(argv)
    target = TargetSpec.from_record(json.loads(args.target_json))
    workload = WorkloadSpec.from_record(json.loads(args.workload_json))
    try:
        if args.profile_mode == "granular":
            payload = execute_workload_with_granular_profile(
                target,
                workload,
                project_root=target.project_root,
                overlay_root=Path(args.overlay_root) if args.overlay_root else None,
                inner_repetitions=max(1, args.inner_repetitions),
            )
        elif args.profile_mode == "hotspots":
            payload = execute_workload_with_profile(
                target,
                workload,
                project_root=target.project_root,
                overlay_root=Path(args.overlay_root) if args.overlay_root else None,
                inner_repetitions=max(1, args.inner_repetitions),
            )
        else:
            payload = execute_workload(
                target,
                workload,
                project_root=target.project_root,
                overlay_root=Path(args.overlay_root) if args.overlay_root else None,
                inner_repetitions=max(1, args.inner_repetitions),
            )
        print(json.dumps(payload))
        return 0 if payload.get("success", False) else 1
    except Exception as exc:  # pragma: no cover - exercised via subprocess
        print(
            json.dumps(
                {
                    "success": False,
                    "return_code": 1,
                    "stdout": "",
                    "stderr": str(exc),
                    "logical_invocations": max(1, args.inner_repetitions),
                    "inner_repetitions": max(1, args.inner_repetitions),
                }
            )
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
