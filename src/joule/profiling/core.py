from __future__ import annotations

import enum
import importlib
import io
from pathlib import Path
from typing import Any

from joule.models import TargetSpec, WorkloadSpec
from joule.runtime_helpers.worker import (
    execute_async_harness_workload,
    execute_golden_trace_workload,
    execute_harness_workload,
    execute_property_workload,
    execute_pytest_workload,
    extend_runtime_import_paths,
    load_module_for_file_selector,
    resolve_attr_path,
)


class ProfileMode(enum.Enum):
    """Profiling mode for workload execution."""

    HOTSPOTS = "hotspots"  # Function-level cProfile
    GRANULAR = "granular"  # Function + line-level profiling


class ProfilingError(Exception):
    """Raised when profiling fails in granular mode.

    This is a hard error that should not be silently caught when
    granular profiling is explicitly requested.
    """

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": True,
            "error_type": "ProfilingError",
            "message": self.message,
            "reason": self.reason,
        }


def load_object(selector: str, project_root: Path, overlay_root: Path | None = None) -> Any:
    """Load a target object by selector.

    Supports both file selectors (path.py::object) and module selectors (module::object).
    """
    extend_runtime_import_paths(project_root, overlay_root)
    if ".py::" in selector:
        module, object_name = load_module_for_file_selector(selector, project_root)
        return resolve_attr_path(module, object_name)
    module_name, object_name = selector.replace("::", ":").split(":", 1)
    module = importlib.import_module(module_name)
    return resolve_attr_path(module, object_name)


def _normalize_pytest_selector(selector: str, project_root: Path) -> str:
    """Normalize pytest selector to absolute path."""
    if "::" not in selector:
        return selector
    file_part, rest = selector.split("::", 1)
    file_path = Path(file_part)
    if not file_path.is_absolute():
        file_path = project_root / file_part
    return f"{file_path}::{rest}"


def execute_workload(
    target: TargetSpec,
    workload: WorkloadSpec,
    project_root: Path,
    overlay_root: Path | None = None,
    *,
    inner_repetitions: int = 1,
) -> dict:
    """Execute a workload and capture output."""
    from contextlib import redirect_stderr, redirect_stdout

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    logical_invocations = 0
    payload: dict[str, Any]

    from joule.models import WorkloadKind

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
        elif workload.kind is WorkloadKind.ASYNC_HARNESS:
            payload, logical_invocations = execute_async_harness_workload(
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


