from __future__ import annotations

import ast
from pathlib import Path
import textwrap

from joule.integrations.git import apply_patch_to_target
from joule.models import TargetSpec
from joule.orchestrator.internal.mfbo_flow import dependency_policy_metadata
from joule.transformers.deterministic import (
    ChainedComparisonFusion,
    CounterSubstitution,
    DefaultDictSubstitution,
    EmptyLiteralOperator,
    EnumerateSubstitution,
    ForLoopToComprehension,
    GeneratorToYieldFrom,
    HeapNLargestSmallest,
    IteratorSubstitution,
    ListPopZeroToDeque,
    LocalImportHoisting,
    LoopGlobalToLocalHoisting,
    LoopMembershipSetCache,
    MemoizationAddition,
    MultipleAssignmentFusion,
    MultipleOrToSetMembership,
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


def test_replace_function_in_module_preserves_candidate_imports_and_decorators(tmp_path: Path):
    module_path = tmp_path / "sample.py"
    module_path.write_text(
        textwrap.dedent(
            """
            def target(x):
                return x + 1
            """
        ),
        encoding="utf-8",
    )
    target = TargetSpec(
        project_root=tmp_path,
        module="sample",
        file_path=module_path,
        function_name="target",
        qualname="target",
        owner_path=[],
        line_start=1,
        line_end=2,
        source=module_path.read_text(encoding="utf-8"),
    )
    candidate_source = textwrap.dedent(
        """
        from functools import lru_cache

        @lru_cache(maxsize=None)
        def target(x):
            return x + 2
        """
    )

    apply_patch_to_target(target, candidate_source)

    updated = module_path.read_text(encoding="utf-8")
    assert "from functools import lru_cache" in updated
    assert "@lru_cache(maxsize=None)" in updated
    assert "return x + 2" in updated


def test_dependency_policy_distinguishes_stdlib_and_external_dependencies():
    assert dependency_policy_metadata(["collections"])["dependency_policy_state"] == "stdlib_only"
    assert dependency_policy_metadata(["numpy"])["dependency_policy_state"] == "review_required"


def test_chained_comparison_fusion_skips_side_effectful_pivot_expression():
    source = textwrap.dedent(
        """
        def f(a, c):
            return a < bump() and bump() < c
        """
    )
    assert ChainedComparisonFusion().generate(_target(source)) == []


def test_empty_literal_operator_skips_shadowed_builtin_names():
    source = textwrap.dedent(
        """
        def f():
            list = tuple
            return list()
        """
    )
    assert EmptyLiteralOperator().generate(_target(source)) == []


def test_multiple_or_to_set_membership_skips_unhashable_rhs_values():
    source = textwrap.dedent(
        """
        def f(x):
            return x == [] or x == [1]
        """
    )
    assert MultipleOrToSetMembership().generate(_target(source)) == []


def test_for_loop_to_comprehension_skips_self_referential_append_expression():
    source = textwrap.dedent(
        """
        def f(n):
            out = []
            for _ in range(n):
                out.append(len(out))
            return out
        """
    )
    assert ForLoopToComprehension().generate(_target(source)) == []


def test_generator_to_yield_from_skips_when_loop_target_used_after_loop():
    source = textwrap.dedent(
        """
        def f(xs):
            for item in xs:
                yield item
            return item
        """
    )
    assert GeneratorToYieldFrom().generate(_target(source)) == []


def test_local_import_hoisting_skips_module_name_collision():
    source = textwrap.dedent(
        """
        math = object()

        def f(x):
            import math
            return math.sqrt(x)
        """
    )
    assert LocalImportHoisting().generate(_target(source)) == []
