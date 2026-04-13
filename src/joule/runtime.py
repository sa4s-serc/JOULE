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
) -> dict:
    command = worker_command(
        target,
        workload,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
        profile_mode="hotspots",
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
        if args.profile_mode == "hotspots":
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
