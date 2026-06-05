from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

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
            for node, owner_path in _iter_supported_nodes(tree):
                if node.name.startswith("property_") or node.name.endswith("_harness"):
                    continue
                lines = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
                loops = sum(isinstance(inner, (ast.For, ast.While, ast.comprehension)) for inner in ast.walk(node))
                calls = sum(isinstance(inner, ast.Call) for inner in ast.walk(node))
                loop_density = loops / max(lines, 1)
                nesting = _max_nesting_depth(node)
                size_score = lines * 0.3
                loop_score = loop_density * 20.0 + loops * 2.0
                call_score = calls * 0.8
                nest_score = nesting * 2.0
                score = size_score + loop_score + call_score + nest_score
                segment = dedent(ast.get_source_segment(source, node) or "")
                pure, reasons = analyze_purity(segment)
                if not pure:
                    continue
                qualname = ".".join([*owner_path, node.name]) if owner_path else node.name
                results.append(
                    DiscoveryResult(
                        target=TargetSpec(
                            project_root=project_root,
                            module=_module_name(project_root, file_path),
                            file_path=file_path,
                            function_name=node.name,
                            qualname=qualname,
                            owner_path=list(owner_path),
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno),
                            source=segment,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            metadata={
                                "purity": pure,
                                "purity_reasons": reasons,
                                "owner_path": list(owner_path),
                                "target_kind": "method" if owner_path else "function",
                                "async": isinstance(node, ast.AsyncFunctionDef),
                            },
                        ),
                        score=score,
                        reasons=[
                            f"{lines} lines",
                            f"{loops} loops/comprehensions",
                            f"{calls} calls",
                            f"nesting={nesting}",
                            f"size_score={size_score:.2f}",
                            f"loop_score={loop_score:.2f}",
                            f"call_score={call_score:.2f}",
                            f"nest_score={nest_score:.2f}",
                            "async target" if isinstance(node, ast.AsyncFunctionDef) else "sync target",
                            *reasons,
                        ],
                        workloads=[],
                    )
                )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]


def _module_name(project_root: Path, file_path: Path) -> str:
    src_root = project_root / "src"
    if file_path.is_relative_to(src_root):
        relative = file_path.relative_to(src_root).with_suffix("")
    elif file_path.is_relative_to(project_root):
        relative = file_path.relative_to(project_root).with_suffix("")
    else:
        relative = Path(file_path.stem)
    return ".".join(relative.parts)


def _max_nesting_depth(node: ast.AST) -> int:
    """Return the maximum nesting depth of control-flow constructs inside node.

    Counts ancestor nodes that are ast.If, ast.For, ast.While, ast.With, or
    ast.Try when walking the subtree via a recursive DFS.
    """
    _nesting_types = (ast.If, ast.For, ast.While, ast.With, ast.Try)

    def _dfs(current: ast.AST, depth: int) -> int:
        max_depth = depth
        for child in ast.iter_child_nodes(current):
            child_depth = depth + 1 if isinstance(child, _nesting_types) else depth
            max_depth = max(max_depth, _dfs(child, child_depth))
        return max_depth

    return _dfs(node, 0)


def _iter_supported_nodes(tree: ast.Module) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, list[str]]]:
    nodes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, list[str]]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes.append((node, []))
            continue
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nodes.append((child, [node.name]))
    return nodes
