from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib
import io
import json
import os
from pathlib import Path
import sys
from typing import Any

from joule.models import TargetSpec, WorkloadKind, WorkloadSpec
from joule.profiling.core import (
    execute_workload,
    load_object,
)
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


def execute_workload_with_profile(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    """Execute workload with function-level profiling."""
    from joule.profiling.hotspots import execute_hotspot_profiling

    return execute_hotspot_profiling(
        target=target,
        workload=workload,
        project_root=project_root,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
    )


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

    Raises:
        ProfilingError: If line_profiler is not available or profiling fails.
                      This is a hard error - granular mode must fail fast.
    """
    from joule.profiling.granular import execute_granular_profiling

    return execute_granular_profiling(
        target=target,
        workload=workload,
        project_root=project_root,
        overlay_root=overlay_root,
        inner_repetitions=inner_repetitions,
    )


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
