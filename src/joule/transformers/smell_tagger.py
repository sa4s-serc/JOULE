"""
Lightweight taxonomy-aware smell tagger.

Maps a Python source string to the set of Energy-Smells taxonomy categories
(C1–C12) that are likely present, using pure-AST heuristics. No ML, no LLM.

Used by OperatorRegistry to bias operator selection toward operators whose
`targets_smells` overlap with the detected categories.
"""
from __future__ import annotations

import ast


def tag_source(source: str) -> frozenset[str]:
    """Return the set of smell category tags likely present in *source*.

    Returns an empty frozenset on parse errors — callers treat that as
    "no smell information available" and apply no bias.
    """
    try:
        tree = ast.parse(source)
        nodes = list(ast.walk(tree))
    except SyntaxError:
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

    return frozenset(tags)


# ── AST predicates ────────────────────────────────────────────────────────

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
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.List):
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
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
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
