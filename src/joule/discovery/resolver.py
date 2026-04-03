from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

from joule.config import JouleSettings
from joule.discovery.profiler import StaticProfiler
from joule.discovery.purity import analyze_purity
from joule.discovery.synthesizer import GoldenTraceSynthesizer
from joule.discovery.workloads import build_bundle, discover_pytest_workloads, resolve_explicit_workloads
from joule.models import DiscoveryResult, TargetSpec, WorkloadBundle


def resolve_target(path: Path, function_name: str, project_root: Path | None = None) -> TargetSpec:
    file_path = path.resolve()
    root = project_root or _find_root(file_path)
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    matches = [candidate for candidate in _iter_supported_targets(tree, source) if _matches_target(candidate, function_name)]
    if not matches:
        raise ValueError(
            f"Target {function_name!r} not found in {file_path}. "
            "JOULE v0 supports top-level functions, async functions, and class methods. "
            "Nested/local functions are out of scope."
        )
    exact = [candidate for candidate in matches if candidate["qualname"] == function_name]
    if len(exact) == 1:
        return _build_target_spec(root, file_path, exact[0])
    if len(matches) == 1:
        return _build_target_spec(root, file_path, matches[0])
    options = ", ".join(sorted(candidate["qualname"] for candidate in matches))
    raise ValueError(f"Ambiguous target {function_name!r} in {file_path}; choose one of: {options}")


def resolve_workload_bundle(
    settings: JouleSettings,
    target: TargetSpec,
    *,
    tests: list[str] | None,
    properties: list[str] | None,
    harness: str | None,
) -> WorkloadBundle:
    explicit = resolve_explicit_workloads(tests=tests, properties=properties, harness=harness)
    notes: list[str] = []
    workloads = explicit
    if not workloads:
        workloads = discover_pytest_workloads(
            target.project_root,
            target,
            limit=settings.workload_discovery_limit,
        )
        if workloads:
            notes.append("aligned pytest workloads discovered heuristically")
    else:
        notes.append("using explicit workload selectors")
    if not workloads:
        synthesizer = GoldenTraceSynthesizer(target.project_root)
        fallback = synthesizer.synthesize(target)
        if fallback is not None:
            workloads = [fallback]
            notes.append("no aligned tests found; using safe default-argument fallback")
    if not workloads:
        raise ValueError(
            f"Unable to resolve workloads for {target.qualname}. "
            "Provide --tests/--properties/--harness, add an aligned pytest case, or make the target callable "
            "with only safe default arguments. Async targets and instance methods require explicit workloads "
            "unless they are callable without additional state."
        )
    return build_bundle(target, workloads, notes)


def discover_targets(settings: JouleSettings, path: Path) -> list[DiscoveryResult]:
    root = _find_root(path)
    profiler = StaticProfiler()
    results = profiler.discover(root, limit=settings.workload_discovery_limit)
    for result in results:
        result.workloads = discover_pytest_workloads(root, result.target, limit=3)
    return results


def _find_root(path: Path) -> Path:
    candidate = path if path.is_dir() else path.parent
    for current in [candidate.resolve(), *candidate.resolve().parents]:
        if (current / "pyproject.toml").exists():
            return current
    return candidate.resolve()


def _module_name(project_root: Path, file_path: Path) -> str:
    if "src" in file_path.parts:
        index = file_path.parts.index("src") + 1
        relative = Path(*file_path.parts[index:]).with_suffix("")
    else:
        relative = file_path.relative_to(project_root).with_suffix("")
    return ".".join(relative.parts)


def _iter_supported_targets(tree: ast.Module, source: str) -> list[dict]:
    targets: list[dict] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            targets.append(_target_payload(node, source, owner_path=[]))
            continue
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    targets.append(_target_payload(child, source, owner_path=[node.name]))
    return targets


def _target_payload(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str, *, owner_path: list[str]) -> dict:
    segment = dedent(ast.get_source_segment(source, node) or "")
    qualname = ".".join([*owner_path, node.name]) if owner_path else node.name
    pure, reasons = analyze_purity(segment)
    return {
        "node": node,
        "segment": segment,
        "owner_path": owner_path,
        "qualname": qualname,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
        "purity": pure,
        "purity_reasons": reasons,
    }


def _build_target_spec(project_root: Path, file_path: Path, payload: dict) -> TargetSpec:
    if not payload["purity"]:
        reasons = ", ".join(payload["purity_reasons"]) or "unknown side effects"
        raise ValueError(
            f"Target {payload['qualname']!r} is not eligible for JOULE v0 because it appears impure: {reasons}"
        )
    return TargetSpec(
        project_root=project_root,
        module=_module_name(project_root, file_path),
        file_path=file_path,
        function_name=payload["node"].name,
        qualname=payload["qualname"],
        owner_path=list(payload["owner_path"]),
        line_start=payload["node"].lineno,
        line_end=getattr(payload["node"], "end_lineno", payload["node"].lineno),
        source=payload["segment"],
        is_async=payload["is_async"],
        metadata={
            "purity": payload["purity"],
            "purity_reasons": payload["purity_reasons"],
            "owner_path": payload["owner_path"],
            "target_kind": "method" if payload["owner_path"] else "function",
            "async": payload["is_async"],
        },
    )


def _matches_target(candidate: dict, requested: str) -> bool:
    return requested in {candidate["qualname"], candidate["node"].name}
