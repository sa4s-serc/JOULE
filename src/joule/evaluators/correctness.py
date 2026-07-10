"""Correctness verification engine.

Runs candidate code under each workload and checks for failures.
Parallelises multi-workload verification using ``ThreadPoolExecutor``
so that independent subprocess invocations run concurrently.
"""

from __future__ import annotations

import ast
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING

from joule.integrations.libcst_tools import replace_function_in_module
from joule.models import TargetSpec, WorkloadBundle, WorkloadSpec
from joule.runtime import invoke_worker
from joule.utils.ast_cache import get_parsed_tree as _get_parsed_tree

if TYPE_CHECKING:
    pass


def _run_workload(
    target: TargetSpec,
    workload: WorkloadSpec,
    overlay_root: Path | None,
    timeout_s: float,
) -> tuple[str, dict]:
    """Run a single workload and return ``(workload_identifier, result_dict)``."""
    result = invoke_worker(target, workload, overlay_root=overlay_root, timeout_s=timeout_s)
    return workload.identifier, result


class CorrectnessEngine:
    """Verify that a candidate implementation passes all workloads.

    When *max_workers > 1* and the bundle has multiple workloads the
    verification subprocesses are launched in parallel using a
    ``ThreadPoolExecutor``.  Each subprocess is independent so there are
    no shared-state concerns.

    Parameters
    ----------
    max_workers:
        Maximum number of parallel subprocess invocations.  Defaults to
        ``1`` (sequential) for backward compatibility.  Set to
        ``settings.max_parallel_workers`` to match the oracle behaviour.
    """

    def __init__(self, max_workers: int = 1) -> None:
        self._max_workers = max(1, int(max_workers))

    def verify(
        self,
        target: TargetSpec,
        bundle: WorkloadBundle,
        candidate_source: str | None = None,
        *,
        timeout_s: float = 30.0,
    ) -> tuple[bool, list[str]]:
        """Return ``(passed, reasons)`` after running all workloads.

        Stops on the first failure when running sequentially; with
        parallel workers all in-flight futures are cancelled as soon as
        one fails (best-effort).
        """
        # Syntax pre-check: avoids spawning any subprocess for broken source.
        if candidate_source:
            tree, _ = _get_parsed_tree(candidate_source)
            if tree is None:
                # get_parsed_tree returns None on SyntaxError; re-parse to get
                # the exact error message.
                try:
                    ast.parse(candidate_source)
                except SyntaxError as exc:
                    return False, [f"candidate syntax error: {exc}"]

        if candidate_source is not None:
            overlay_context = tempfile.TemporaryDirectory(prefix="joule-correctness-")
            try:
                overlay_root = Path(overlay_context.name)
                _materialize_overlay(target, overlay_root, candidate_source)
                return self._run_workloads(target, bundle, overlay_root=overlay_root, timeout_s=timeout_s)
            finally:
                overlay_context.cleanup()

        return self._run_workloads(target, bundle, overlay_root=None, timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_workloads(
        self,
        target: TargetSpec,
        bundle: WorkloadBundle,
        *,
        overlay_root: Path | None,
        timeout_s: float,
    ) -> tuple[bool, list[str]]:
        workloads = bundle.workloads
        if len(workloads) <= 1 or self._max_workers <= 1:
            return self._run_sequential(target, workloads, overlay_root=overlay_root, timeout_s=timeout_s)
        return self._run_parallel(target, workloads, overlay_root=overlay_root, timeout_s=timeout_s)

    def _run_sequential(
        self,
        target: TargetSpec,
        workloads: list[WorkloadSpec],
        *,
        overlay_root: Path | None,
        timeout_s: float,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        for workload in workloads:
            _wid, sample = _run_workload(target, workload, overlay_root, timeout_s)
            if not sample["success"]:
                msg = sample["stderr"].strip() or sample["stdout"].strip()
                reasons.append(f"{workload.identifier} failed: {msg}")
                return False, reasons
        return True, reasons

    def _run_parallel(
        self,
        target: TargetSpec,
        workloads: list[WorkloadSpec],
        *,
        overlay_root: Path | None,
        timeout_s: float,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_workload: dict[Future[tuple[str, dict]], WorkloadSpec] = {
                executor.submit(_run_workload, target, workload, overlay_root, timeout_s): workload
                for workload in workloads
            }
            for future in as_completed(future_to_workload):
                workload = future_to_workload[future]
                try:
                    _wid, sample = future.result()
                except Exception as exc:
                    reasons.append(f"{workload.identifier} failed with exception: {exc}")
                    # Cancel remaining work — we already have a failure
                    for pending in future_to_workload:
                        pending.cancel()
                    return False, reasons
                if not sample["success"]:
                    msg = sample["stderr"].strip() or sample["stdout"].strip()
                    reasons.append(f"{workload.identifier} failed: {msg}")
                    for pending in future_to_workload:
                        pending.cancel()
                    return False, reasons
        return True, reasons


def _materialize_overlay(target: TargetSpec, overlay_root: Path, candidate_source: str) -> Path:
    """Write a patched version of the target's module into *overlay_root*.

    The overlay is a minimal filesystem tree containing only the files
    needed to import and execute the candidate, so that the worker
    subprocess picks up the rewritten function without modifying the
    project source tree.
    """
    relative = target.file_path.relative_to(target.project_root)
    destination = overlay_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    current = relative.parent
    while current != Path("."):
        source_init = target.project_root / current / "__init__.py"
        if source_init.exists():
            overlay_init = overlay_root / current / "__init__.py"
            overlay_init.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_init, overlay_init)
        current = current.parent
    rewritten = replace_function_in_module(target.file_path.read_text(encoding="utf-8"), target, candidate_source)
    destination.write_text(rewritten, encoding="utf-8")
    return destination
