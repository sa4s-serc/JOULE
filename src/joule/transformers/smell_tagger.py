"""
Lightweight taxonomy-aware smell tagger.

Maps a Python source string to the set of Energy-Smells taxonomy categories
(C1–C12) that are likely present, using pure-AST heuristics. No ML, no LLM.

Used by OperatorRegistry to bias operator selection toward operators whose
`targets_smells` overlap with the detected categories.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from joule.utils.ast_cache import get_parsed_tree


def tag_source(source: str) -> frozenset[str]:
    """Return the set of smell category tags likely present in *source*.

    Returns an empty frozenset on parse errors — callers treat that as
    "no smell information available" and apply no bias.

    Uses the shared ``joule.utils.ast_cache`` so that the same source
    string is only parsed once even when both the smell tagger and the
    surrogate feature extractor call this function for the same candidate.
    """
    tree, nodes = get_parsed_tree(source)
    if tree is None:
        return frozenset()

    tags: set[str] = set()

    # C1 — Redundant Computation
    if _has_dead_assignment(nodes):
        tags.add("C1")
    if _has_repeated_call(nodes):
        tags.add("C1")

    # C2 — Unnecessary Call Overhead
    if _has_static_method_candidate(nodes):
        tags.add("C2")

    # C3 — Inefficient Iteration
    if _has_loop(nodes):
        tags.add("C3")
    if _has_nested_loop(nodes):
        tags.add("C3")
    if _has_range_len_loop(nodes):
        tags.add("C3")
    if _has_loop_append(nodes):
        tags.add("C3")

    # C4 — Inefficient Control Flow
    if _has_bare_except(nodes):
        tags.add("C4")
    if _has_consecutive_ifs(tree):
        tags.add("C4")
    if _has_return_bool_pattern(nodes):
        tags.add("C4")

    # C5 — Suboptimal Data Structures
    if _has_list_membership_check(nodes):
        tags.add("C5")
    if _has_dict_keys_membership(nodes):
        tags.add("C5")

    # C6 — Unnecessary Memory
    if _has_list_created_in_loop(nodes):
        tags.add("C6")
    if _has_bare_open(nodes):
        tags.add("C6")
    if _has_mutable_default_arg(nodes):
        tags.add("C6")

    # C7 — Suboptimal Algorithmic
    if _has_recursive_call(nodes):
        tags.add("C7")
    if _has_nested_loop(nodes):
        tags.add("C7")

    # C8 — Missing Reuse
    if _has_repeated_call(nodes):
        tags.add("C8")
    if _has_regex_runtime_call(nodes):
        tags.add("C8")
    if _has_recursive_call(nodes):
        tags.add("C8")

    # C10 — Underused Language Primitives
    if _has_range_len_loop(nodes):
        tags.add("C10")
    if _has_string_concat_loop(nodes):
        tags.add("C10")
    if _has_manual_reduction(nodes):
        tags.add("C10")

    # C9 — I/O Access
    if _has_io_access(nodes):
        tags.add("C9")

    # C11 — Concurrency opportunity (independent loop iterations)
    if _has_concurrency_opportunity(nodes):
        tags.add("C11")

    # C12 — Hardware locality (strided / non-sequential subscript patterns)
    if _has_strided_access(nodes):
        tags.add("C12")

    return frozenset(tags)


# ---------------------------------------------------------------------------
# Enriched smell report (confidence + evidence)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SmellEvidence:
    """Evidence for a single Energy-Smell category.

    Attributes
    ----------
    category:
        Category code, e.g. ``"C3"``.
    confidence:
        Float in [0.0, 1.0].  Currently computed as a weighted count of
        predicates triggered for this category (each predicate contributes
        1.0 / max_predicates).
    evidence:
        Human-readable descriptions of each triggered predicate, e.g.
        ``["nested loop detected", "range(len(x)) loop detected"]``.
    """

    category: str
    confidence: float
    evidence: list[str] = field(default_factory=list)

    def to_record(self) -> dict:
        return {
            "category": self.category,
            "confidence": round(float(self.confidence), 4),
            "evidence": list(self.evidence),
        }


# Maximum number of individual predicates we check per category (used for
# normalising confidence scores so they stay in [0, 1]).
_MAX_PREDICATES_PER_CATEGORY: dict[str, int] = {
    "C1": 2, "C2": 1, "C3": 4, "C4": 3, "C5": 2,
    "C6": 3, "C7": 2, "C8": 3, "C9": 1, "C10": 3,
    "C11": 1, "C12": 1,
}


def tag_source_with_evidence(source: str) -> dict[str, SmellEvidence]:
    """Return per-category smell evidence for *source*.

    Unlike :func:`tag_source`, this function returns a mapping from
    category code to a :class:`SmellEvidence` object containing a
    confidence score (0–1) and a list of human-readable evidence strings.

    Returns an empty dict on parse errors.

    Example::

        report = tag_source_with_evidence(source)
        for code, smell in report.items():
            print(f"{code}: confidence={smell.confidence:.2f}")
            for ev in smell.evidence:
                print(f"  - {ev}")
    """
    tree, nodes = get_parsed_tree(source)
    if tree is None:
        return {}

    hits: dict[str, list[str]] = {}

    def _record(category: str, description: str) -> None:
        hits.setdefault(category, []).append(description)

    # C1 — Redundant Computation
    if _has_dead_assignment(nodes):
        _record("C1", "self-assignment detected (x = x)")
    if _has_repeated_call(nodes):
        _record("C1", "repeated identical call expression detected")

    # C2 — Unnecessary Call Overhead
    if _has_static_method_candidate(nodes):
        _record("C2", "instance method never uses self — static method candidate")

    # C3 — Inefficient Iteration
    if _has_loop(nodes):
        _record("C3", "explicit for/while loop detected")
    if _has_nested_loop(nodes):
        _record("C3", "nested loop detected (O(n²) risk)")
    if _has_range_len_loop(nodes):
        _record("C3", "range(len(x)) pattern — prefer enumerate()")
    if _has_loop_append(nodes):
        _record("C3", "list.append() inside loop — prefer comprehension")

    # C4 — Inefficient Control Flow
    if _has_bare_except(nodes):
        _record("C4", "bare except clause detected")
    if _has_consecutive_ifs(tree):
        _record("C4", "consecutive if statements — consider elif")
    if _has_return_bool_pattern(nodes):
        _record("C4", "explicit return True/False after comparison")

    # C5 — Suboptimal Data Structures
    if _has_list_membership_check(nodes):
        _record("C5", "membership test on list — consider set")
    if _has_dict_keys_membership(nodes):
        _record("C5", "d.keys() membership check — use 'x in d'")

    # C6 — Unnecessary Memory
    if _has_list_created_in_loop(nodes):
        _record("C6", "container created inside loop body")
    if _has_bare_open(nodes):
        _record("C6", "open() call outside with-statement")
    if _has_mutable_default_arg(nodes):
        _record("C6", "mutable default argument (list/dict/set)")

    # C7 — Suboptimal Algorithmic
    if _has_recursive_call(nodes):
        _record("C7", "recursive call detected — consider iterative/DP")
    if _has_nested_loop(nodes):
        _record("C7", "nested loop detected — O(n²) algorithm risk")

    # C8 — Missing Reuse
    if _has_repeated_call(nodes):
        _record("C8", "repeated identical call — cache the result")
    if _has_regex_runtime_call(nodes):
        _record("C8", "runtime re.compile() inside function — pre-compile")
    if _has_recursive_call(nodes):
        _record("C8", "recursive call — consider memoisation")

    # C9 — I/O Access
    if _has_io_access(nodes):
        _record("C9", "file / network / DB I/O detected")

    # C10 — Underused Language Primitives
    if _has_range_len_loop(nodes):
        _record("C10", "range(len(x)) — prefer enumerate() or zip()")
    if _has_string_concat_loop(nodes):
        _record("C10", "string concatenation in loop — prefer str.join()")
    if _has_manual_reduction(nodes):
        _record("C10", "manual accumulator — prefer sum()/min()/max()/any()/all()")

    # C11 — Concurrency opportunity
    if _has_concurrency_opportunity(nodes):
        _record("C11", "independent loop iterations detected — ThreadPoolExecutor candidate")

    # C12 — Hardware locality
    if _has_strided_access(nodes):
        _record("C12", "strided subscript access (a[i*k]) — cache-unfriendly")

    result: dict[str, SmellEvidence] = {}
    for category, descriptions in hits.items():
        max_p = _MAX_PREDICATES_PER_CATEGORY.get(category, 1)
        confidence = min(1.0, len(descriptions) / max_p)
        result[category] = SmellEvidence(
            category=category,
            confidence=confidence,
            evidence=descriptions,
        )
    return result


# AST predicates

def _has_loop(nodes: list[ast.AST]) -> bool:
    return any(isinstance(n, (ast.For, ast.While)) for n in nodes)


def _has_nested_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, (ast.For, ast.While)):
                    return True
    return False


def _has_range_len_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.For):
            if (
                isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"
                and node.iter.args
                and isinstance(node.iter.args[0], ast.Call)
                and isinstance(node.iter.args[0].func, ast.Name)
                and node.iter.args[0].func.id == "len"
            ):
                return True
    return False


def _has_loop_append(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "append"
                ):
                    return True
    return False


def _has_bare_except(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    return True
    return False


def _has_consecutive_ifs(tree: ast.AST) -> bool:
    """True when 3+ consecutive `if` statements appear in the same block."""
    def _check_body(body: list[ast.stmt]) -> bool:
        run = 0
        for stmt in body:
            if isinstance(stmt, ast.If):
                run += 1
                if run >= 3:
                    return True
            else:
                run = 0
        return False

    for node in ast.walk(tree):
        body: list[ast.stmt] | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            body = node.body
        elif isinstance(node, (ast.For, ast.While, ast.With)):
            body = node.body
        if body and _check_body(body):
            return True
    return False


def _has_return_bool_pattern(nodes: list[ast.AST]) -> bool:
    """Detects `if cond: return True / else: return False`."""
    for node in nodes:
        if not isinstance(node, ast.If):
            continue
        if not node.orelse:
            continue
        body_returns_bool = (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Return)
            and isinstance(node.body[0].value, ast.Constant)
            and node.body[0].value.value in (True, False)
        )
        else_returns_bool = (
            len(node.orelse) == 1
            and isinstance(node.orelse[0], ast.Return)
            and isinstance(node.orelse[0].value, ast.Constant)
            and node.orelse[0].value.value in (True, False)
        )
        if body_returns_bool and else_returns_bool:
            return True
    return False


def _has_list_membership_check(nodes: list[ast.AST]) -> bool:
    """Detects `x in [...]` or `x in (...)` where a set would be O(1)."""
    for node in nodes:
        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, (ast.List, ast.Tuple)):
                    if len(getattr(comp, "elts", [])) >= 3:
                        return True
    return False


def _has_dict_keys_membership(nodes: list[ast.AST]) -> bool:
    """Detects `x in d.keys()`."""
    for node in nodes:
        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)):
                    if (
                        isinstance(comp, ast.Call)
                        and isinstance(comp.func, ast.Attribute)
                        and comp.func.attr == "keys"
                    ):
                        return True
    return False


def _has_list_created_in_loop(nodes: list[ast.AST]) -> bool:
    """Detect list creation (assignment) inside loops — a memory-waste signal.

    Only flags list literals that are part of an assignment statement.
    List literals used as function call arguments (e.g. ``func([1,2,3])``) are
    intentional and not a C6 smell.
    """
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.Assign) and isinstance(child.value, ast.List):
                    return True
    return False


def _has_bare_open(nodes: list[ast.AST]) -> bool:
    with_node_ids: set[int] = set()
    for node in nodes:
        if isinstance(node, ast.With):
            for child in ast.walk(node):
                with_node_ids.add(id(child))
    for node in nodes:
        if id(node) in with_node_ids:
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            return True
    return False


def _has_mutable_default_arg(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    return True
    return False


def _has_recursive_call(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == node.name
                ):
                    return True
    return False


def _has_repeated_call(nodes: list[ast.AST]) -> bool:
    """True when the same function call (by name) appears 2+ times in one scope."""
    from collections import Counter
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            call_names = [
                child.func.id
                for child in ast.walk(node)
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
            ]
            counts = Counter(call_names)
            if any(v >= 2 for v in counts.values()):
                return True
    return False


def _has_regex_runtime_call(nodes: list[ast.AST]) -> bool:
    """Detects `re.search/match/...` calls not pre-compiled."""
    _RE_METHODS = {"search", "match", "fullmatch", "findall", "sub", "split", "finditer"}
    for node in nodes:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
            and node.func.attr in _RE_METHODS
        ):
            return True
    return False


def _has_string_concat_loop(nodes: list[ast.AST]) -> bool:
    """Detect string concatenation via += inside loops.

    Only flags when the augmented-assignment target is plausibly a string.
    We look for a prior assignment of the target name to a string constant
    (e.g. ``s = ""`` or ``s = ''``) in the same function scope to avoid
    false-positiving on integer accumulation patterns like ``total += n``.
    """
    for node in nodes:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Collect names initialized to string constants in this function.
        string_vars: set[str] = set()
        for stmt in ast.walk(node):
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                string_vars.add(stmt.targets[0].id)
        if not string_vars:
            continue
        # Look for AugAssign(Add) on one of those names inside a loop.
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for loop_child in ast.walk(child):
                    if (
                        isinstance(loop_child, ast.AugAssign)
                        and isinstance(loop_child.op, ast.Add)
                        and isinstance(loop_child.target, ast.Name)
                        and loop_child.target.id in string_vars
                    ):
                        return True
    return False


def _has_manual_reduction(nodes: list[ast.AST]) -> bool:
    """Detects manual accumulation loops that sum/min/max could replace."""
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.AugAssign)
                    and isinstance(child.op, (ast.Add, ast.Mult))
                    and isinstance(child.target, ast.Name)
                ):
                    return True
    return False


def _has_dead_assignment(nodes: list[ast.AST]) -> bool:
    """Detects `x = x` style no-op assignments."""
    for node in nodes:
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
                and node.targets[0].id == node.value.id
            ):
                return True
    return False


def _has_static_method_candidate(nodes: list[ast.AST]) -> bool:
    """Detects instance methods that never access `self`."""
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                # skip __init__, __new__, classmethods, staticmethods
                decorator_names = {
                    d.id if isinstance(d, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else "")
                    for d in item.decorator_list
                }
                if decorator_names & {"staticmethod", "classmethod", "property"}:
                    continue
                if not item.args.args:
                    continue
                first_arg = item.args.args[0].arg
                # check if self/cls is ever used in the body
                self_used = any(
                    isinstance(n, ast.Name) and n.id == first_arg
                    for n in ast.walk(item)
                    if n is not item.args.args[0]
                )
                if not self_used:
                    return True
    return False


# C9 / C11 / C12 helpers

_IO_MODULE_METHODS: dict[str, set[str]] = {
    "json": {"load", "loads", "dump", "dumps"},
    "csv": {"reader", "writer"},
    "pickle": {"load", "loads", "dump", "dumps"},
    "sqlite3": {"connect"},
    "urllib": {"urlopen", "urlretrieve"},
    "requests": {"get", "post", "put", "delete", "head", "patch"},
    "pathlib": {"read_text", "write_text", "read_bytes", "write_bytes", "open"},
}


def _has_io_access(nodes: list[ast.AST]) -> bool:
    """C9: Detect file/network/DB I/O patterns."""
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # bare open() call
        if isinstance(func, ast.Name) and func.id == "open":
            return True
        # module.method() patterns
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            methods = _IO_MODULE_METHODS.get(func.value.id)
            if methods and func.attr in methods:
                return True
        # pathlib Path(...).method() — two-level attribute chain
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"read_text", "write_text", "read_bytes", "write_bytes", "open", "open_binary"}
        ):
            return True
    return False


def _has_concurrency_opportunity(nodes: list[ast.AST]) -> bool:
    """C11: Detect for-loops where the body is likely independent (no carried deps).

    Heuristic: the loop body contains only calls or assignments whose RHS does
    not reference the accumulator introduced in the same body. We flag loops
    that iterate over a name, have a non-trivial body (>1 stmt or contains a
    call), and do NOT have any loop-carried AugAssign that references the iter
    variable — these are strong candidates for ThreadPoolExecutor.map.
    """
    for node in nodes:
        if not isinstance(node, ast.For):
            continue
        # Iterable must be a name or attribute (not a generator)
        if not isinstance(node.iter, (ast.Name, ast.Attribute, ast.Call)):
            continue
        # Body must contain at least one Call node
        body_calls = [
            c for stmt in node.body for c in ast.walk(stmt)
            if isinstance(c, ast.Call)
        ]
        if not body_calls:
            continue
        # No augmented assignment on the loop target (loop-carried dependency)
        # Check for any AugAssign in the loop body — this indicates a
        # loop-carried dependency (accumulator pattern) which prevents
        # safe parallelisation.  The check is on any name, not just the
        # loop variable, since patterns like `total += f(x)` are carried.
        has_carried_dep = False
        for stmt in node.body:
            for child in ast.walk(stmt):
                if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
                    has_carried_dep = True
                    break
            if has_carried_dep:
                break
        if not has_carried_dep:
            return True
    return False


def _has_strided_access(nodes: list[ast.AST]) -> bool:
    """C12: Detect strided / non-sequential subscript access: a[i * k] or a[i + k].

    This pattern can be cache-unfriendly and is a sign of potential hardware
    locality issues (e.g., column-major access of a row-major array).
    """
    for node in nodes:
        if not isinstance(node, ast.Subscript):
            continue
        index = node.slice
        # BinOp index: a[i * stride] or a[i + offset] where index involves a Name
        if isinstance(index, ast.BinOp) and isinstance(index.op, (ast.Mult, ast.Add, ast.Sub)):
            names_in_index = [n for n in ast.walk(index) if isinstance(n, ast.Name)]
            if len(names_in_index) >= 1:
                return True
    return False
