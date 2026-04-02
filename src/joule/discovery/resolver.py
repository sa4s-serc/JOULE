from __future__ import annotations

import ast
from pathlib import Path

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
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            segment = ast.get_source_segment(source, node) or ""
            pure, reasons = analyze_purity(segment)
            metadata = {"purity": pure, "purity_reasons": reasons}
            return TargetSpec(
                project_root=root,
                module=_module_name(root, file_path),
                file_path=file_path,
                function_name=node.name,
                qualname=node.name,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                source=segment,
                metadata=metadata,
            )
    raise ValueError(f"Function {function_name!r} not found in {file_path}")


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
    if not workloads:
        synthesizer = GoldenTraceSynthesizer(target.project_root)
        fallback = synthesizer.synthesize(target)
        if fallback is not None:
            workloads = [fallback]
            notes.append("no aligned tests found; synthesized golden trace fallback")
    if not workloads:
        raise ValueError(
            f"Unable to resolve workloads for {target.qualname}. "
            "Provide --tests/--properties/--harness or make the target callable without required args."
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
