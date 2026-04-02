from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from joule.models import TargetSpec, WorkloadKind, WorkloadSpec


def load_object(selector: str, project_root: Path, overlay_root: Path | None = None):
    if overlay_root:
        sys.path.insert(0, str(overlay_root))
    src_path = project_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    sys.path.insert(0, str(project_root))
    if ".py::" in selector:
        module_path, object_name = selector.split("::", 1)
        file_path = Path(module_path)
        if not file_path.is_absolute():
            file_path = project_root / file_path
        module_name = file_path.with_suffix("").name
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to import {selector}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return getattr(module, object_name)
    module_name, object_name = selector.replace("::", ":").split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, object_name)


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
    payload: dict[str, object]
    with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
        if workload.kind is WorkloadKind.PYTEST:
            selector = _normalize_pytest_selector(workload.selector, project_root)
            return_code = 0
            success = True
            for _ in range(inner_repetitions):
                logical_invocations += 1
                result = pytest.main([selector, "-q"], plugins=[])
                return_code = int(result)
                if return_code != 0:
                    success = False
                    break
            payload = {"return_code": return_code, "success": success}
        elif workload.kind is WorkloadKind.PROPERTY:
            callback = load_object(workload.selector, project_root, overlay_root=overlay_root)
            for _ in range(inner_repetitions):
                logical_invocations += 1
                callback()
            payload = {"return_code": 0, "success": True}
        elif workload.kind is WorkloadKind.HARNESS:
            callback = load_object(workload.selector, project_root, overlay_root=overlay_root)
            target_callable = _load_target_callable(target, project_root, overlay_root)
            signature = inspect.signature(callback)
            for _ in range(inner_repetitions):
                logical_invocations += 1
                if len(signature.parameters) == 0:
                    callback()
                else:
                    callback(target_callable)
            payload = {"return_code": 0, "success": True}
        elif workload.kind is WorkloadKind.GOLDEN_TRACE:
            target_callable = _load_target_callable(target, project_root, overlay_root)
            signature = inspect.signature(target_callable)
            kwargs = {
                parameter.name: parameter.default
                for parameter in signature.parameters.values()
                if parameter.default is not inspect.Signature.empty
            }
            for _ in range(inner_repetitions):
                logical_invocations += 1
                target_callable(**kwargs)
            payload = {"return_code": 0, "success": True, "mode": "default-args"}
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
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=subprocess_env(target.project_root, overlay_root),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return {
            "success": False,
            "return_code": 124,
            "stdout": stdout or "",
            "stderr": (stderr or "").strip() or f"Timed out after {timeout_s:.1f}s",
            "logical_invocations": inner_repetitions,
            "inner_repetitions": inner_repetitions,
        }
    return _decode_worker_payload(stdout, stderr, process.returncode, inner_repetitions)


def worker_command(
    target: TargetSpec,
    workload: WorkloadSpec,
    *,
    overlay_root: Path | None = None,
    inner_repetitions: int = 1,
) -> list[str]:
    command = [
        sys.executable,
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
    env["PYTHONPATH"] = ":".join(pythonpath)
    return env


def _load_target_callable(target: TargetSpec, project_root: Path, overlay_root: Path | None):
    if overlay_root:
        sys.path.insert(0, str(overlay_root))
    src_path = project_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    sys.path.insert(0, str(project_root))
    module = importlib.import_module(target.module)
    return getattr(module, target.function_name)


def _decode_worker_payload(stdout: str, stderr: str, return_code: int, inner_repetitions: int) -> dict:
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {
                "success": False,
                "return_code": return_code or 1,
                "stdout": stdout,
                "stderr": stderr.strip(),
            }
    else:
        payload = {"success": False, "return_code": return_code or 1, "stdout": "", "stderr": stderr.strip()}
    payload["stdout"] = payload.get("stdout", "")
    payload["stderr"] = payload.get("stderr", "") or stderr.strip()
    payload["return_code"] = int(payload.get("return_code", return_code or 1))
    payload["success"] = bool(payload.get("success", False))
    payload["logical_invocations"] = int(payload.get("logical_invocations", inner_repetitions))
    payload["inner_repetitions"] = int(payload.get("inner_repetitions", inner_repetitions))
    return payload


def _normalize_pytest_selector(selector: str, project_root: Path) -> str:
    if "::" not in selector:
        return selector
    file_part, rest = selector.split("::", 1)
    file_path = Path(file_part)
    if not file_path.is_absolute():
        file_path = project_root / file_path
    return f"{file_path}::{rest}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-json", required=True)
    parser.add_argument("--workload-json", required=True)
    parser.add_argument("--overlay-root")
    parser.add_argument("--inner-repetitions", type=int, default=1)
    args = parser.parse_args(argv)
    target = TargetSpec.from_record(json.loads(args.target_json))
    workload = WorkloadSpec.from_record(json.loads(args.workload_json))
    try:
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
