from __future__ import annotations

import ast
from pathlib import Path

from joule.discovery.purity import analyze_purity
from joule.models import DiscoveryResult, TargetSpec


class StaticProfiler:
    def discover(self, project_root: Path, limit: int = 5) -> list[DiscoveryResult]:
        results: list[DiscoveryResult] = []
        for file_path in project_root.rglob("*.py"):
            relative = file_path.relative_to(project_root)
            if (
                file_path.is_relative_to(project_root / ".venv")
                or "tests" in relative.parts
                or file_path.name in {"harnesses.py", "properties.py", "conftest.py"}
            ):
                continue
            source = file_path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in tree.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if node.name.startswith("property_") or node.name.endswith("_harness"):
                    continue
                lines = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
                loops = sum(isinstance(inner, (ast.For, ast.While, ast.comprehension)) for inner in ast.walk(node))
                calls = sum(isinstance(inner, ast.Call) for inner in ast.walk(node))
                score = (lines * 0.5) + (loops * 3.0) + calls
                segment = ast.get_source_segment(source, node) or ""
                pure, reasons = analyze_purity(segment)
                if not pure:
                    continue
                results.append(
                    DiscoveryResult(
                        target=TargetSpec(
                            project_root=project_root,
                            module=_module_name(project_root, file_path),
                            file_path=file_path,
                            function_name=node.name,
                            qualname=node.name,
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno),
                            source=segment,
                        ),
                        score=score,
                        reasons=[f"{lines} lines", f"{loops} loops/comprehensions", f"{calls} calls", *reasons],
                        workloads=[],
                    )
                )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]


def _module_name(project_root: Path, file_path: Path) -> str:
    if "src" in file_path.parts:
        index = file_path.parts.index("src") + 1
        relative_parts = file_path.parts[index:]
    else:
        relative_parts = file_path.relative_to(project_root).parts
    return ".".join(Path(*relative_parts).with_suffix("").parts)
