from __future__ import annotations

import ast


# Calls that indicate genuine side effects (I/O, process control, filesystem mutation).
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
        # ast.Delete mutates external bindings; flag it.
        # ast.Yield/YieldFrom and ast.Raise are NOT side effects — generators and
        # exception-raising functions are valid optimization targets.
        if isinstance(node, ast.Delete):
            reasons.append("contains Delete")
    return not reasons, reasons
