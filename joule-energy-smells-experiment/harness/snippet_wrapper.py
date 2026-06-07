"""
Wraps raw code snippets into joule-compatible Python modules.

Tier A: has top-level functions + uses stdin
  → keep functions as-is, patch `input` at module level to read from a list
Tier B: script style + uses stdin
  → wrap entire body in def solution(), patch input
Tier C: clean functions, no stdin
  → keep as-is, only ensure there's a callable target
Tier D: script style, no stdin
  → wrap entire body in def solution()
"""

import ast
import re
import textwrap


# ── Stdin mock preamble ────────────────────────────────────────────────────

_STDIN_MOCK_PREAMBLE = '''\
import sys as _sys
import io as _io

# Joule stdin mock — initialized by test harness
_MOCK_STDIN_LINES: list[str] = []
_MOCK_STDIN_IDX = 0

def _mock_input(prompt=""):
    global _MOCK_STDIN_IDX
    if _MOCK_STDIN_IDX < len(_MOCK_STDIN_LINES):
        line = _MOCK_STDIN_LINES[_MOCK_STDIN_IDX]
        _MOCK_STDIN_IDX += 1
        return line
    return ""

def _reset_mock_stdin(lines: list[str]) -> None:
    global _MOCK_STDIN_LINES, _MOCK_STDIN_IDX
    _MOCK_STDIN_LINES = list(lines)
    _MOCK_STDIN_IDX = 0

# Capture output instead of printing (joule purity: no print() calls in target)
_OUTPUT_BUFFER = _io.StringIO()
def _capture_output(*args, sep=" ", end="\\n", **kwargs):
    _OUTPUT_BUFFER.write(sep.join(str(a) for a in args) + end)

def get_output() -> str:
    return _OUTPUT_BUFFER.getvalue()

'''

_CLEAN_PREAMBLE = '''\
import io as _io

# Capture output instead of printing (joule purity gate)
_OUTPUT_BUFFER = _io.StringIO()
def _capture_output(*args, sep=" ", end="\\n", **kwargs):
    _OUTPUT_BUFFER.write(sep.join(str(a) for a in args) + end)

def get_output() -> str:
    return _OUTPUT_BUFFER.getvalue()

'''

# ── Helpers ────────────────────────────────────────────────────────────────


def _patch_input_in_source(source: str) -> str:
    """Replace bare `input(` with `_mock_input(` in source text."""
    # Simple text replacement — fine for competitive programming snippets
    patched = source.replace("input(", "_mock_input(")
    # Also patch sys.stdin.readline() patterns
    patched = patched.replace("sys.stdin.readline()", "_mock_input()")
    patched = patched.replace("sys.stdin.readline().strip()", "_mock_input().strip()")
    patched = patched.replace("sys.stdin.read()", '"\n".join(_MOCK_STDIN_LINES)')
    return patched


def _patch_print_in_source(source: str) -> str:
    """Replace print( calls with _capture_output( to satisfy joule's purity check."""
    return re.sub(r'\bprint\(', '_capture_output(', source)


def _patch_open_stdin_in_source(source: str) -> str:
    """Replace open(0) / open('/dev/stdin') patterns with a mock stdin reader."""
    # open(0) is a common CP trick to read stdin as a file
    patched = source.replace("open(0)", "_io.StringIO('\\n'.join(_MOCK_STDIN_LINES))")
    patched = patched.replace("open('/dev/stdin')", "_io.StringIO('\\n'.join(_MOCK_STDIN_LINES))")
    patched = patched.replace('open("/dev/stdin")', "_io.StringIO('\\n'.join(_MOCK_STDIN_LINES))")
    return patched


def _strip_top_level_input_lambda(source: str) -> str:
    """
    Many CP snippets redefine input at the top:
        input = lambda: sys.stdin.readline().strip()
    Strip these — they conflict with our mock.
    """
    lines = source.splitlines()
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("input") and "lambda" in stripped and "stdin" in stripped:
            continue
        if stripped.startswith("input") and "sys.stdin" in stripped and "=" in stripped:
            continue
        filtered.append(line)
    return "\n".join(filtered)


def _get_top_level_func_names(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
        return [
            n.name
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    except SyntaxError:
        return []


def _get_import_block(source: str) -> str:
    """Extract all import statements from source."""
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            lines.append(line)
    return "\n".join(lines)


def _get_non_import_body(source: str) -> str:
    """Source minus import lines."""
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("import ") or stripped.startswith("from ")):
            lines.append(line)
    return "\n".join(lines)


# ── Main wrapping entry point ──────────────────────────────────────────────


def wrap_snippet(code: str, tier: str, function_name: str) -> str:
    """
    Returns the content of target.py ready to be written to disk.

    Parameters
    ----------
    code          : raw snippet source
    tier          : A | B | C | D
    function_name : the target function joule will optimize
    """
    if tier == "C":
        return _wrap_tier_c(code)
    if tier == "D":
        return _wrap_tier_d(code, function_name)
    if tier == "A":
        return _wrap_tier_a(code, function_name)
    if tier == "B":
        return _wrap_tier_b(code, function_name)
    raise ValueError(f"Unknown tier: {tier}")


def _wrap_tier_c(code: str) -> str:
    """Clean functions, no stdin — minimal wrapping, just patch print."""
    patched = _patch_print_in_source(code)
    return f"# Tier C: clean functions\n{_CLEAN_PREAMBLE}{patched}\n"


def _wrap_tier_d(code: str, fn_name: str) -> str:
    """Script with no stdin — wrap in a function."""
    patched = _patch_print_in_source(code)
    patched = _patch_open_stdin_in_source(patched)
    imports = _get_import_block(patched)
    body = _get_non_import_body(patched)
    indented_body = textwrap.indent(body, "    ")
    return (
        f"# Tier D: script wrapped as function\n"
        f"{_CLEAN_PREAMBLE}"
        f"{imports}\n\n"
        f"def {fn_name}():\n"
        f"{indented_body}\n"
    )


def _wrap_tier_a(code: str, fn_name: str) -> str:
    """Functions + stdin — inject mock stdin preamble.
    
    For tier A, we keep all top-level functions but move any module-level
    statement (that isn't a function/class/import/constant) inside the
    target function using a run() wrapper pattern. This handles the common
    CP pattern where X, Y = map(int, input().split()) is at module level.
    """
    cleaned = _strip_top_level_input_lambda(code)
    patched = _patch_input_in_source(cleaned)
    patched = _patch_print_in_source(patched)
    patched = _patch_open_stdin_in_source(patched)

    try:
        tree = ast.parse(patched)
    except SyntaxError:
        # Fallback: treat like tier B
        return _wrap_tier_b(code, fn_name)

    import_lines = []
    func_and_class_nodes = []
    module_level_exec = []  # non-import, non-function/class top-level statements

    for node in tree.body:
        src_lines = patched.splitlines()
        node_src = "\n".join(src_lines[node.lineno - 1 : node.end_lineno])  # type: ignore[attr-defined]

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append(node_src)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            func_and_class_nodes.append(node_src)
        else:
            module_level_exec.append(node_src)

    # Check if the desired fn_name is among the actual functions
    actual_fns = _get_top_level_func_names(patched)

    if module_level_exec and fn_name not in actual_fns:
        # Script-like tier A: all logic is at module level — treat like tier B
        return _wrap_tier_b(code, fn_name)

    if module_level_exec:
        # Move module-level exec statements into a wrapper that calls fn_name
        # We create a _run() function that sets up context and calls the target
        exec_body = textwrap.indent("\n".join(module_level_exec), "    ")
        # Check if the module-level exec already calls fn_name
        exec_str = "\n".join(module_level_exec)
        if f"{fn_name}(" in exec_str:
            # Module-level code already calls the function, don't call it again
            wrapper = (
                f"\ndef {fn_name}_run():\n"
                f"    \"\"\"Wrapper: executes module-level setup + {fn_name}.\"\"\"\n"
                f"{exec_body}\n"
            )
        else:
            wrapper = (
                f"\ndef {fn_name}_run():\n"
                f"    \"\"\"Wrapper: executes module-level setup + {fn_name}.\"\"\"\n"
                f"{exec_body}\n"
                f"    {fn_name}()\n"
            )
        # Redirect the target name to the wrapper for joule
        # Actually, simpler: make the fn_name be fn_name_run
        all_parts = (
            f"# Tier A: functions with mocked stdin\n"
            f"{_STDIN_MOCK_PREAMBLE}"
            f"{chr(10).join(import_lines)}\n\n"
            f"{chr(10).join(func_and_class_nodes)}\n"
            f"{wrapper}\n"
        )
        return all_parts

    # Clean tier A: all top-level logic is inside functions
    return (
        f"# Tier A: functions with mocked stdin\n"
        f"{_STDIN_MOCK_PREAMBLE}"
        f"{patched}\n"
    )


def _wrap_tier_b(code: str, fn_name: str) -> str:
    """Script + stdin — wrap body in solution(), inject mock stdin."""
    cleaned = _strip_top_level_input_lambda(code)
    patched = _patch_input_in_source(cleaned)
    patched = _patch_print_in_source(patched)
    patched = _patch_open_stdin_in_source(patched)

    imports = _get_import_block(patched)
    body = _get_non_import_body(patched)
    indented_body = textwrap.indent(body, "    ")

    return (
        f"# Tier B: script with mocked stdin, wrapped as function\n"
        f"{_STDIN_MOCK_PREAMBLE}"
        f"{imports}\n\n"
        f"def {fn_name}():\n"
        f"{indented_body}\n"
    )
