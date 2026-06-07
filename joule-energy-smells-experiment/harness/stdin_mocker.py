"""
Generates realistic mock stdin lines for competitive programming snippets.

The approach is heuristic: we inspect the code to infer what kind of input
is expected (single int, pair of ints, list of ints, etc.) and produce
a minimal valid input that exercises the hot path.

For the experiment, correctness of the input is secondary — we just need
the code to run without crashing and exercise its main loop.
"""

import ast
import random
import re
from typing import Any


# ── Pattern heuristics ─────────────────────────────────────────────────────


def _contains(code: str, *patterns: str) -> bool:
    return any(p in code for p in patterns)


def _count_input_calls(code: str) -> int:
    return code.count("_mock_input(") + code.count("input(")


def _first_n_values(code: str) -> int:
    """Try to guess how many top-level input() calls there are."""
    return min(_count_input_calls(code), 20)


def generate_mock_stdin(code: str, tier: str, seed: int = 42) -> list[str]:
    """
    Returns a list of stdin lines to feed the snippet.

    The list is intentionally short and small-valued to keep execution fast,
    while still causing the main loop/algorithm to execute.
    """
    rng = random.Random(seed)
    lines: list[str] = []

    # eval(input()) — needs valid Python expressions
    if re.search(r"eval\(_mock_input\(\)\)|eval\(input\(\)\)", code):
        eval_calls = code.count("eval(_mock_input(") + code.count("eval(input(")
        # Generate valid Python expressions (integers, simple arithmetic)
        for _ in range(max(eval_calls, 5)):
            # Mix of simple integers and arithmetic expressions
            choice = rng.randint(1, 3)
            if choice == 1:
                lines.append(str(rng.randint(1, 100)))
            elif choice == 2:
                a = rng.randint(1, 20)
                b = rng.randint(1, 20)
                lines.append(f"{a} + {b}")
            else:
                a = rng.randint(1, 10)
                b = rng.randint(1, 5)
                lines.append(f"{a} * {b}")
        return lines

    # Single integer N — very common in CP
    if re.search(r"int\(_mock_input\(\)\)|int\(input\(\)\)", code):
        n = rng.randint(5, 50)
        lines.append(str(n))
        # Many problems follow N with N lines of data
        for _ in range(n):
            lines.append(str(rng.randint(1, 100)))
        return lines

    # Map-based pair: map(int, input().split())
    if "map(int," in code and ".split()" in code:
        pairs_needed = _first_n_values(code)
        for _ in range(max(pairs_needed, 3)):
            a = rng.randint(1, 20)
            b = rng.randint(1, 20)
            lines.append(f"{a} {b}")
        return lines

    # list(map(int, ...)) — sequence input
    if "list(map(int" in code:
        n = rng.randint(5, 15)
        lines.append(str(n))
        lines.append(" ".join(str(rng.randint(1, 50)) for _ in range(n)))
        return lines

    # String input
    if 'input().split()' in code and 'int' not in code:
        lines.append("hello world foo bar")
        lines.append("baz qux")
        return lines

    # Default: provide some integers
    n_lines = max(_first_n_values(code), 5)
    for _ in range(n_lines):
        lines.append(str(rng.randint(1, 100)))

    return lines


def format_mock_stdin_as_python_list(lines: list[str]) -> str:
    """Format lines as a Python list literal for embedding in test file."""
    items = ", ".join(repr(l) for l in lines)
    return f"[{items}]"
