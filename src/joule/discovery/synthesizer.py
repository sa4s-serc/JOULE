from __future__ import annotations

import inspect
from pathlib import Path

from joule.models import TargetSpec, WorkloadKind, WorkloadSpec


class GoldenTraceSynthesizer:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def synthesize(self, target: TargetSpec) -> WorkloadSpec | None:
        signature = inspect.signature(_load_callable(target))
        missing_required = [
            parameter.name
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Signature.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if missing_required:
            return None
        return WorkloadSpec(
            kind=WorkloadKind.GOLDEN_TRACE,
            identifier=f"golden::{target.qualname}",
            label=f"golden trace for {target.qualname}",
            selector=f"{target.file_path}::{target.function_name}",
            metadata={"project_root": str(self.project_root)},
        )


def _load_callable(target: TargetSpec):
    import importlib
    import sys

    if str(target.project_root) not in sys.path:
        sys.path.insert(0, str(target.project_root))
    src_path = target.project_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    module = importlib.import_module(target.module)
    return getattr(module, target.function_name)
