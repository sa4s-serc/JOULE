from __future__ import annotations

import ast


IMPURE_CALL_NAMES = {"print", "open", "write", "remove", "unlink", "system", "popen"}


def analyze_purity(source: str) -> tuple[bool, list[str]]:
    tree = ast.parse(source)
    reasons: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            reasons.append("uses global/nonlocal state")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in IMPURE_CALL_NAMES:
                reasons.append(f"calls {node.func.id}()")
        if isinstance(node, (ast.Delete, ast.Raise, ast.Yield, ast.YieldFrom)):
            reasons.append(f"contains {type(node).__name__}")
    return not reasons, reasons
