from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from joule.models import TargetSpec, WorkloadBundle, WorkloadKind, WorkloadSpec

TEST_FILE_PATTERNS = ("test_", "_test.py")


def resolve_explicit_workloads(
    *,
    tests: list[str] | None,
    properties: list[str] | None,
    harness: str | None,
) -> list[WorkloadSpec]:
    workloads: list[WorkloadSpec] = []
    for selector in tests or []:
        workloads.append(
            WorkloadSpec(
                kind=WorkloadKind.PYTEST,
                identifier=f"pytest::{selector}",
                label=selector,
                selector=selector,
                metadata={"provenance": "explicit", "resolution_strategy": "explicit-test-selector"},
            )
        )
    for selector in properties or []:
        workloads.append(
            WorkloadSpec(
                kind=WorkloadKind.PROPERTY,
                identifier=f"property::{selector}",
                label=selector,
                selector=selector,
                metadata={"provenance": "explicit", "resolution_strategy": "explicit-property-selector"},
            )
        )
    if harness:
        workloads.append(
            WorkloadSpec(
                kind=WorkloadKind.HARNESS,
                identifier=f"harness::{harness}",
                label=harness,
                selector=harness,
                metadata={"provenance": "explicit", "resolution_strategy": "explicit-harness-selector"},
            )
        )
    return workloads


def discover_pytest_workloads(project_root: Path, target: TargetSpec, limit: int = 8) -> list[WorkloadSpec]:
    workloads: list[WorkloadSpec] = []
    for file_path in _iter_test_files(project_root):
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                score = _test_relevance_score(node, target)
                if score <= 0:
                    continue
                selector = f"{file_path.relative_to(project_root)}::{node.name}"
                workloads.append(
                    WorkloadSpec(
                        kind=WorkloadKind.PYTEST,
                        identifier=f"pytest::{selector}",
                        label=selector,
                        selector=selector,
                        metadata={
                            "alignment_score": score,
                            "provenance": "heuristic-pytest",
                            "resolution_strategy": "heuristic-alignment",
                        },
                    )
                )
    workloads.sort(key=lambda item: item.metadata.get("alignment_score", 0), reverse=True)
    return workloads[:limit]


def build_bundle(target: TargetSpec, workloads: list[WorkloadSpec], notes: Iterable[str] = ()) -> WorkloadBundle:
    return WorkloadBundle(target=target, workloads=workloads, notes=list(notes))


def _iter_test_files(project_root: Path):
    seen: set[Path] = set()
    for pattern in ("tests/**/*.py", "test_*.py", "**/*_test.py"):
        for path in project_root.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def _test_relevance_score(node: ast.AST, target: TargetSpec) -> int:
    score = 0
    module_parts = set(target.module.split("."))
    file_tokens = set(target.file_path.stem.replace("-", "_").split("_"))
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name) and inner.id == target.function_name:
            score += 2
        if isinstance(inner, ast.Name) and inner.id in target.owner_path:
            score += 2
        if isinstance(inner, ast.Attribute) and inner.attr == target.function_name:
            score += 1
        if isinstance(inner, ast.Attribute) and inner.attr in target.owner_path:
            score += 1
        if isinstance(inner, ast.ImportFrom) and inner.module == target.module:
            score += 3
        if isinstance(inner, ast.ImportFrom) and inner.module and set(inner.module.split(".")) & module_parts:
            score += 1
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            lowered = inner.value.replace("-", "_")
            if target.qualname in lowered or target.function_name in lowered:
                score += 1
            if file_tokens & set(lowered.split("_")):
                score += 1
    return score
