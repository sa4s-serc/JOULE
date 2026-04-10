from __future__ import annotations

import ast
from pathlib import Path
import textwrap

from joule.models import TargetSpec
from joule.transformers.deterministic import (
    CounterSubstitution,
    DefaultDictSubstitution,
    EnumerateSubstitution,
    HeapNLargestSmallest,
    IteratorSubstitution,
    ListPopZeroToDeque,
    LocalImportHoisting,
    LoopGlobalToLocalHoisting,
    LoopMembershipSetCache,
    MemoizationAddition,
    MultipleAssignmentFusion,
    SeenSetForAppendDedup,
    SortedToInPlaceSort,
    StringConcatToJoin,
    TupleUnpackInLoop,
)


def _target(source: str) -> TargetSpec:
    return TargetSpec(
        project_root=Path("."),
        module="sample",
        file_path=Path("sample.py"),
        function_name="target",
        qualname="target",
        owner_path=[],
        line_start=1,
        line_end=max(1, source.count("\n") + 1),
        source=source,
    )


def _single_candidate(operator, source: str) -> str:
    results = operator.generate(_target(source))
    assert results
    candidate = results[0].candidate_source
    ast.parse(candidate)
    return candidate


def test_iterator_substitution_rewrites_iter_call():
    source = textwrap.dedent(
        """
        def f(xs):
            total = 0
            for value in iter(xs):
                total += value
            return total
        """
    )
    candidate = _single_candidate(IteratorSubstitution(), source)
    assert "for value in xs" in candidate


def test_enumerate_substitution_rewrites_range_len_loop():
    source = textwrap.dedent(
        """
        def f(xs):
            out = []
            for i in range(len(xs)):
                value = xs[i]
                out.append((i, value))
            return out
        """
    )
    candidate = _single_candidate(EnumerateSubstitution(), source)
    assert "for i, value in enumerate(xs)" in candidate


def test_string_concat_to_join_rewrites_chained_addition():
    source = textwrap.dedent(
        """
        def f(a, b, c):
            return str(a) + str(b) + str(c)
        """
    )
    candidate = _single_candidate(StringConcatToJoin(), source)
    assert ".join((str(a), str(b), str(c)))" in candidate


def test_multiple_assignment_fusion_rewrites_adjacent_assignments():
    source = textwrap.dedent(
        """
        def f():
            a = 1
            b = 2
            return a + b
        """
    )
    candidate = _single_candidate(MultipleAssignmentFusion(), source)
    assert "a, b = (1, 2)" in candidate


def test_tuple_unpack_in_loop_rewrites_indexed_pair_access():
    source = textwrap.dedent(
        """
        def f(pairs):
            total = 0
            for pair in pairs:
                a = pair[0]
                b = pair[1]
                total += a + b
            return total
        """
    )
    candidate = _single_candidate(TupleUnpackInLoop(), source)
    assert "for a, b in pairs" in candidate


def test_sorted_to_in_place_sort_rewrites_supported_pattern():
    source = textwrap.dedent(
        """
        def f(xs):
            xs = list(xs)
            xs = sorted(xs)
            return xs
        """
    )
    candidate = _single_candidate(SortedToInPlaceSort(), source)
    assert "xs.sort()" in candidate


def test_list_pop_zero_to_deque_rewrites_queue_pattern():
    source = textwrap.dedent(
        """
        def f():
            queue = [1, 2, 3]
            out = []
            while queue:
                out.append(queue.pop(0))
            return out
        """
    )
    candidate = _single_candidate(ListPopZeroToDeque(), source)
    assert "from collections import deque" in candidate
    assert "queue = deque([1, 2, 3])" in candidate
    assert "queue.popleft()" in candidate


def test_local_import_hoisting_moves_safe_import_to_module_scope():
    source = textwrap.dedent(
        """
        def f(x):
            import math
            return math.sqrt(x)
        """
    )
    candidate = _single_candidate(LocalImportHoisting(), source)
    assert candidate.count("import math") == 1
    assert "def f(x):\n    return math.sqrt(x)" in candidate


def test_loop_global_to_local_hoisting_introduces_local_aliases():
    source = textwrap.dedent(
        """
        def f(rows):
            out = []
            for row in rows:
                out.append(len(row))
            return out
        """
    )
    candidate = _single_candidate(LoopGlobalToLocalHoisting(), source)
    assert "_len_local = len" in candidate
    assert "_len_local(row)" in candidate


def test_loop_membership_set_cache_creates_cached_set():
    source = textwrap.dedent(
        """
        def f(xs, lookup):
            total = 0
            for x in xs:
                if x in lookup:
                    total += 1
            return total
        """
    )
    candidate = _single_candidate(LoopMembershipSetCache(), source)
    assert "_lookup_set = set(lookup)" in candidate
    assert "if x in _lookup_set" in candidate


def test_heap_n_largest_smallest_rewrites_sorted_slice_topk():
    source = textwrap.dedent(
        """
        def f(xs, k):
            return sorted(xs)[:k]
        """
    )
    candidate = _single_candidate(HeapNLargestSmallest(), source)
    assert "import heapq" in candidate
    assert "heapq.nsmallest(k, xs)" in candidate


def test_memoization_addition_adds_lru_cache_decorator():
    source = textwrap.dedent(
        """
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)
        """
    )
    candidate = _single_candidate(MemoizationAddition(), source)
    assert "from functools import lru_cache" in candidate
    assert "@lru_cache(maxsize=None)" in candidate


def test_counter_substitution_rewrites_manual_counting():
    source = textwrap.dedent(
        """
        def f(xs):
            counts = {}
            for x in xs:
                if x in counts:
                    counts[x] += 1
                else:
                    counts[x] = 1
            return counts
        """
    )
    candidate = _single_candidate(CounterSubstitution(), source)
    assert "from collections import Counter" in candidate
    assert "counts = Counter()" in candidate
    assert "if x in counts" not in candidate
    assert "counts[x] += 1" in candidate


def test_defaultdict_substitution_rewrites_guarded_grouping():
    source = textwrap.dedent(
        """
        def f(pairs):
            groups = {}
            for key, value in pairs:
                if key not in groups:
                    groups[key] = []
                groups[key].append(value)
            return groups
        """
    )
    candidate = _single_candidate(DefaultDictSubstitution(), source)
    assert "from collections import defaultdict" in candidate
    assert "groups = defaultdict(lambda: [])" in candidate
    assert "if key not in groups" not in candidate


def test_seen_set_for_append_dedup_adds_seen_cache():
    source = textwrap.dedent(
        """
        def f(items):
            out = []
            for item in items:
                if item not in out:
                    out.append(item)
            return out
        """
    )
    candidate = _single_candidate(SeenSetForAppendDedup(), source)
    assert "_out_seen = set()" in candidate
    assert "if item not in _out_seen" in candidate
    assert "_out_seen.add(item)" in candidate
