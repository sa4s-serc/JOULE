from __future__ import annotations

from pathlib import Path
import ast
import shutil
import tempfile

from joule.integrations.libcst_tools import replace_function_in_module
from joule.models import TargetSpec, WorkloadBundle
from joule.runtime import invoke_worker


class CorrectnessEngine:
    def verify(
        self,
        target: TargetSpec,
        bundle: WorkloadBundle,
        candidate_source: str | None = None,
        *,
        timeout_s: float = 30.0,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        try:
            if candidate_source:
                ast.parse(candidate_source)
        except SyntaxError as exc:
            return False, [f"candidate syntax error: {exc}"]

        overlay_root: Path | None = None
        if candidate_source is not None:
            with tempfile.TemporaryDirectory(prefix="joule-correctness-") as temp_dir:
                overlay_root = Path(temp_dir)
                _materialize_overlay(target, overlay_root, candidate_source)
                for workload in bundle.workloads:
                    sample = invoke_worker(target, workload, overlay_root=overlay_root, timeout_s=timeout_s)
                    if not sample["success"]:
                        reasons.append(f"{workload.identifier} failed: {sample['stderr'].strip() or sample['stdout'].strip()}")
                        return False, reasons
            return True, reasons

        for workload in bundle.workloads:
            sample = invoke_worker(target, workload, overlay_root=None, timeout_s=timeout_s)
            if not sample["success"]:
                reasons.append(f"{workload.identifier} failed: {sample['stderr'].strip() or sample['stdout'].strip()}")
                return False, reasons
        return True, reasons


def _materialize_overlay(target: TargetSpec, overlay_root: Path, candidate_source: str) -> Path:
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
