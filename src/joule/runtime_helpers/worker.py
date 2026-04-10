from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from joule.models import TargetSpec, WorkloadSpec


def extend_runtime_import_paths(project_root: Path, overlay_root: Path | None) -> None:
    if overlay_root:
        sys.path.insert(0, str(overlay_root))
    src_path = project_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))
    sys.path.insert(0, str(project_root))


def load_module_for_file_selector(selector: str, project_root: Path) -> tuple[object, str]:
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
    return module, object_name


def load_target_callable(target: TargetSpec, project_root: Path, overlay_root: Path | None) -> Any:
    extend_runtime_import_paths(project_root, overlay_root)
    module = importlib.import_module(target.module)
    current = module
    for owner in target.owner_path:
        current = getattr(current, owner)
    return getattr(current, target.function_name)


def resolve_attr_path(root: object, attribute_path: str) -> Any:
    current = root
    for segment in attribute_path.split("."):
        current = getattr(current, segment)
    return current


def call_maybe_async(callback: Any, *args: Any, **kwargs: Any) -> Any:
    result = callback(*args, **kwargs)
    if inspect.isawaitable(result):
        async def _await_result() -> Any:
            return await result

        return asyncio.run(_await_result())
    return result


def invoke_worker(
    *,
    command: list[str],
    env: dict[str, str],
    timeout_s: float,
    inner_repetitions: int,
    include_profile: bool,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return timeout_payload(
            stdout=stdout,
            stderr=stderr,
            timeout_s=timeout_s,
            inner_repetitions=inner_repetitions,
            include_profile=include_profile,
        )
    return decode_worker_payload(stdout, stderr, process.returncode, inner_repetitions)


def timeout_payload(
    *,
    stdout: str,
    stderr: str,
    timeout_s: float,
    inner_repetitions: int,
    include_profile: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "return_code": 124,
        "stdout": stdout or "",
        "stderr": (stderr or "").strip() or f"Timed out after {timeout_s:.1f}s",
        "logical_invocations": inner_repetitions,
        "inner_repetitions": inner_repetitions,
    }
    if include_profile:
        payload["profile"] = {"functions": [], "ownership": []}
    return payload


def decode_worker_payload(stdout: str, stderr: str, return_code: int, inner_repetitions: int) -> dict[str, Any]:
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


def execute_pytest_workload(
    *,
    selector: str,
    project_root: Path,
    inner_repetitions: int,
    normalize_selector,
) -> tuple[dict[str, Any], int]:
    normalized_selector = normalize_selector(selector, project_root)
    return_code = 0
    success = True
    invocations = 0
    for _ in range(inner_repetitions):
        invocations += 1
        result = pytest.main([normalized_selector, "-q"], plugins=[])
        return_code = int(result)
        if return_code != 0:
            success = False
            break
    return {"return_code": return_code, "success": success}, invocations


def execute_property_workload(
    *,
    selector: str,
    project_root: Path,
    overlay_root: Path | None,
    inner_repetitions: int,
    load_object_fn,
) -> tuple[dict[str, Any], int]:
    callback = load_object_fn(selector, project_root, overlay_root=overlay_root)
    for _ in range(inner_repetitions):
        call_maybe_async(callback)
    return {"return_code": 0, "success": True}, inner_repetitions


def execute_harness_workload(
    *,
    target: TargetSpec,
    selector: str,
    project_root: Path,
    overlay_root: Path | None,
    inner_repetitions: int,
    load_object_fn,
) -> tuple[dict[str, Any], int]:
    callback = load_object_fn(selector, project_root, overlay_root=overlay_root)
    target_callable = load_target_callable(target, project_root, overlay_root)
    signature = inspect.signature(callback)
    expects_target = len(signature.parameters) > 0
    for _ in range(inner_repetitions):
        if expects_target:
            call_maybe_async(callback, target_callable)
        else:
            call_maybe_async(callback)
    return {"return_code": 0, "success": True}, inner_repetitions


def execute_golden_trace_workload(
    *,
    target: TargetSpec,
    project_root: Path,
    overlay_root: Path | None,
    inner_repetitions: int,
) -> tuple[dict[str, Any], int]:
    target_callable = load_target_callable(target, project_root, overlay_root)
    kwargs = default_signature_kwargs(target_callable)
    for _ in range(inner_repetitions):
        call_maybe_async(target_callable, **kwargs)
    return {"return_code": 0, "success": True, "mode": "default-args"}, inner_repetitions


def default_signature_kwargs(callback: Any) -> dict[str, Any]:
    signature = inspect.signature(callback)
    return {
        parameter.name: parameter.default
        for parameter in signature.parameters.values()
        if parameter.default is not inspect.Signature.empty
    }
