from __future__ import annotations

import ast
import hashlib
import math
import sys
from collections import OrderedDict

import numpy as np

from joule.models import SearchContext
from joule.surrogate.types import FEATURE_SCHEMA_VERSION
from joule.utils.ast_cache import get_parsed_tree as _get_parsed_tree



class SourceFeatureExtractor:
    def __init__(self, *, cache_size: int = 2048) -> None:
        self.schema_version = FEATURE_SCHEMA_VERSION
        self._cache_size = max(64, int(cache_size))
        self._base_cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def features(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> np.ndarray:
        base_features = self._base_features(source)
        hints = feature_hints or {}
        parent_len_delta = float(hints.get("parent_len_delta", 0.0))
        generation_depth = float(hints.get("generation_depth", 0.0))
        if context is not None:
            parent_len_delta = float(abs(len(source) - len(context.parent_source)))
            generation_depth = float(context.generation_depth)
        dynamic = np.array(
            [
                parent_len_delta,
                generation_depth,
                float(hints.get("ast_shape_delta", 0.0)),
                float(hints.get("allocation_pattern_delta", 0.0)),
                float(hints.get("call_density_delta", 0.0)),
                # Phase 9 operator-identity hints (default 0 when not provided)
                float(hints.get("operator_index", 0.0)),
                float(hints.get("operator_tier", 0.0)),
                float(hints.get("op_success_rate", 0.5)),
                float(hints.get("op_frontier_rate", 0.0)),
            ],
            dtype=float,
        )
        return np.concatenate((base_features, dynamic))

    def source_hash(self, source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _base_features(self, source: str) -> np.ndarray:
        source_hash = self.source_hash(source)
        cached = self._base_cache.get(source_hash)
        if cached is not None:
            self._base_cache.move_to_end(source_hash)
            return cached

        tree, nodes = _get_parsed_tree(source)
        if tree is None:
            nodes = []
            tree = ast.Module(body=[], type_ignores=[])


        node_count = len(nodes)

        # original 17 features
        loop_count = sum(isinstance(n, (ast.For, ast.While, ast.comprehension)) for n in nodes)
        comp_count = sum(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for n in nodes)
        call_count = sum(isinstance(n, ast.Call) for n in nodes)
        branch_count = sum(isinstance(n, (ast.If, ast.Match, ast.IfExp)) for n in nodes)
        assign_count = sum(isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for n in nodes)
        container_count = sum(isinstance(n, (ast.List, ast.Tuple, ast.Set, ast.Dict)) for n in nodes)
        literal_count = sum(isinstance(n, ast.Constant) for n in nodes)
        subscript_count = sum(isinstance(n, ast.Subscript) for n in nodes)
        lambda_count = sum(isinstance(n, ast.Lambda) for n in nodes)
        function_count = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in nodes)
        try_count = sum(isinstance(n, ast.Try) for n in nodes)
        compare_count = sum(isinstance(n, ast.Compare) for n in nodes)
        return_count = sum(isinstance(n, ast.Return) for n in nodes)
        annotated_assign_count = sum(isinstance(n, ast.AnnAssign) for n in nodes)
        annotation_density = float(annotated_assign_count) / max(1.0, float(node_count))
        branch_density = float(branch_count) / max(1.0, float(node_count))

        # Phase 1 additions: smell-category structural indicators

        # C3.S4 — nested loop indicator
        has_nested_loop = int(_has_nested_loop(nodes))

        # C3.S3 / C8.S2 — call inside a loop body (loop-invariant candidate)
        loop_contains_call = int(_loop_contains_call(nodes))

        # C4.S6 — bare except (exception used as control flow)
        has_bare_except = int(_has_bare_except(nodes))

        # C1.S2 — augmented assignment count (x += y vs x = x + y)
        augassign_count = sum(isinstance(n, ast.AugAssign) for n in nodes)

        # C10.S4 — string concatenation inside a loop
        has_string_concat_loop = int(_has_string_concat_loop(nodes))

        # C8.S1 / C7.S3 — function calls itself (recursive)
        has_recursive_call = int(_has_recursive_call(nodes))

        # C8.S3 — attribute chain depth (obj.a.b.c style access)
        max_attr_chain = _max_attribute_chain_depth(nodes)

        # C1.S8 / C2.S2 — import statements in the function body
        import_count = sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes)

        # C3.S1 — ratio of comprehensions to total iteration constructs
        comp_to_loop_ratio = float(comp_count) / max(1.0, float(loop_count + comp_count))

        # C6.S1 — list/dict/set literals created inside loops
        list_in_loop = int(_container_created_in_loop(nodes))

        # C5.S2 — subscript access on a Name inside a loop
        dict_subscript_in_loop = int(_subscript_in_loop(nodes))

        # C6.S3 / C10.S3 — yield / generator usage
        yield_count = sum(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in nodes)

        # C4.S1 — BoolOp operand count (short-circuit candidates)
        bool_op_count = sum(isinstance(n, ast.BoolOp) for n in nodes)

        # C3.S1 — manual range(len(x)) pattern
        has_range_len_loop = int(_has_range_len_loop(nodes))

        # C6.S6 — open() call not inside a with block
        has_bare_open = int(_has_bare_open(nodes))

        # Phase 2 additions: 6 new structural/complexity features

        # Cyclomatic-complexity proxy: branches + loops + exceptions + bool-ops
        cyclomatic_complexity = branch_count + loop_count + try_count + bool_op_count

        # Loop-internal AugAssign reductions (x += y, x *= y inside a loop body)
        loop_reduction_count = _loop_augassign_count(nodes)

        # Pure-function heuristic: no global/nonlocal, no I/O, no mutable defaults
        is_pure_function = int(_is_pure_function(nodes))

        # Name-reuse ratio: Load-ctx Names / max(1, Store-ctx Names + args)
        load_names = sum(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) for n in nodes)
        store_names = sum(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) for n in nodes)
        arg_names = sum(isinstance(n, ast.arg) for n in nodes)
        name_reuse_ratio = float(load_names) / max(1.0, float(store_names + arg_names))

        # Dict/list subscript access density
        subscript_density = float(subscript_count) / max(1.0, float(node_count))

        # Decorator presence (any decorator on any function/class)
        has_decorator = int(any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and n.decorator_list
            for n in nodes
        ))

        # 1. Identifier entropy (Shannon entropy of Name.ids)
        names = [n.id for n in nodes if isinstance(n, ast.Name)]
        if names:
            from collections import Counter
            counts = Counter(names)
            total = len(names)
            identifier_entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        else:
            identifier_entropy = 0.0

        # 2. Import profile (standard library vs third-party)
        stdlib_imports_count = 0.0
        third_party_imports_count = 0.0
        for n in nodes:
            if isinstance(n, ast.Import):
                for name in n.names:
                    root = name.name.split(".", 1)[0].strip()
                    if root in sys.stdlib_module_names:
                        stdlib_imports_count += 1.0
                    else:
                        third_party_imports_count += 1.0
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    root = n.module.split(".", 1)[0].strip()
                    if root in sys.stdlib_module_names:
                        stdlib_imports_count += 1.0
                    else:
                        third_party_imports_count += 1.0

        base = np.array(
            [
                # original 17
                float(len(source)),
                float(node_count),
                float(loop_count),
                float(comp_count),
                float(call_count),
                float(branch_count),
                float(assign_count),
                float(container_count),
                float(literal_count),
                float(subscript_count),
                float(lambda_count),
                float(function_count),
                float(try_count),
                float(compare_count),
                float(return_count),
                annotation_density,
                branch_density,
                # Phase 1 additions: 16 new smell-category indicators
                float(has_nested_loop),
                float(loop_contains_call),
                float(has_bare_except),
                float(augassign_count),
                float(has_string_concat_loop),
                float(has_recursive_call),
                float(max_attr_chain),
                float(import_count),
                comp_to_loop_ratio,
                float(list_in_loop),
                float(dict_subscript_in_loop),
                float(yield_count),
                float(bool_op_count),
                float(has_range_len_loop),
                float(has_bare_open),
                # Phase 2 additions: 6 new complexity/purity features
                float(cyclomatic_complexity),
                float(loop_reduction_count),
                float(is_pure_function),
                name_reuse_ratio,
                subscript_density,
                float(has_decorator),
                # Batch 6 additions: 3 new features
                identifier_entropy,
                stdlib_imports_count,
                third_party_imports_count,
            ],
            dtype=float,
        )
        self._base_cache[source_hash] = base
        self._base_cache.move_to_end(source_hash)
        while len(self._base_cache) > self._cache_size:
            self._base_cache.popitem(last=False)
        return base


# helpers

def _has_nested_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, (ast.For, ast.While)):
                    return True
    return False


def _loop_contains_call(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.Call):
                    return True
    return False


def _has_bare_except(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    return True
    return False


def _has_string_concat_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
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


def _max_attribute_chain_depth(nodes: list[ast.AST]) -> int:
    max_depth = 0
    for node in nodes:
        if isinstance(node, ast.Attribute):
            depth = 1
            inner = node.value
            while isinstance(inner, ast.Attribute):
                depth += 1
                inner = inner.value
            max_depth = max(max_depth, depth)
    return max_depth


def _container_created_in_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, (ast.List, ast.Dict, ast.Set)):
                    return True
    return False


def _subscript_in_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name):
                    return True
    return False


def _has_range_len_loop(nodes: list[ast.AST]) -> bool:
    for node in nodes:
        if isinstance(node, ast.For):
            # for i in range(len(x))
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


def _has_bare_open(nodes: list[ast.AST]) -> bool:
    """True when open() is called outside a `with` statement."""
    with_bodies: set[int] = set()
    for node in nodes:
        if isinstance(node, ast.With):
            for child in ast.walk(node):
                with_bodies.add(id(child))
    for node in nodes:
        if id(node) in with_bodies:
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            return True
    return False


# Phase 2 helpers

def _loop_augassign_count(nodes: list[ast.AST]) -> int:
    """Count AugAssign nodes that appear inside a loop body (not just anywhere)."""
    count = 0
    for node in nodes:
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.AugAssign) and isinstance(child.op, (ast.Add, ast.Mult, ast.BitOr, ast.BitAnd)):
                    count += 1
    return count


def _is_pure_function(nodes: list[ast.AST]) -> bool:
    """Heuristic: True when no global/nonlocal, no I/O calls, no mutable default args."""
    _io_names = {"open", "print", "input", "write", "read"}
    for node in nodes:
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _io_names:
                return False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    return False
    return True

