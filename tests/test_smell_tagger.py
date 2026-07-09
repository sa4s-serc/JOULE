"""Tests for SmellTagger (Phase 2) and Phase 1 surrogate feature extensions."""
from __future__ import annotations

import numpy as np
import pytest

from joule.transformers.smell_tagger import tag_source
from joule.surrogate.features import SourceFeatureExtractor
from joule.surrogate.types import FEATURE_SCHEMA_VERSION


# SmellTagger tests

def test_tag_source_returns_frozenset():
    result = tag_source("def f(x): return x")
    assert isinstance(result, frozenset)


def test_tag_source_syntax_error_returns_empty():
    result = tag_source("def f(: invalid")
    assert result == frozenset()


def test_tag_source_detects_c3_range_len_loop():
    source = """
def f(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    tags = tag_source(source)
    assert "C3" in tags
    assert "C10" in tags   # range(len()) is also a C10 primitive smell


def test_tag_source_detects_c3_nested_loop():
    source = """
def f(xs, ys):
    result = []
    for x in xs:
        for y in ys:
            result.append(x * y)
    return result
"""
    tags = tag_source(source)
    assert "C3" in tags
    assert "C7" in tags   # nested loop = algorithmic smell too


def test_tag_source_detects_c5_list_membership():
    source = """
def f(x):
    return x in [1, 3, 5, 7, 9, 11]
"""
    tags = tag_source(source)
    assert "C5" in tags


def test_tag_source_detects_c5_dict_keys_membership():
    source = """
def f(d, k):
    return k in d.keys()
"""
    tags = tag_source(source)
    assert "C5" in tags


def test_tag_source_detects_c6_mutable_default_arg():
    source = """
def accumulate(x, acc=[]):
    acc.append(x)
    return acc
"""
    tags = tag_source(source)
    assert "C6" in tags


def test_tag_source_detects_c6_bare_open():
    source = """
def read_data(path):
    f = open(path)
    data = f.read()
    f.close()
    return data
"""
    tags = tag_source(source)
    assert "C6" in tags


def test_tag_source_no_c6_with_context_manager():
    source = """
def read_data(path):
    with open(path) as f:
        return f.read()
"""
    tags = tag_source(source)
    assert "C6" not in tags


def test_tag_source_detects_c4_bare_except():
    source = """
def safe_get(d, k):
    try:
        return d[k]
    except:
        return None
"""
    tags = tag_source(source)
    assert "C4" in tags


def test_tag_source_detects_c4_return_bool():
    source = """
def is_valid(x):
    if x > 0:
        return True
    else:
        return False
"""
    tags = tag_source(source)
    assert "C4" in tags


def test_tag_source_detects_c8_repeated_calls():
    source = """
def process(data):
    n = len(data)
    if len(data) == 0:
        return 0
    return n
"""
    tags = tag_source(source)
    assert "C8" in tags


def test_tag_source_detects_c7_recursive():
    source = """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
"""
    tags = tag_source(source)
    assert "C7" in tags
    assert "C8" in tags


def test_tag_source_detects_c10_string_concat_loop():
    source = """
def build(words):
    result = ""
    for w in words:
        result += w + ","
    return result
"""
    tags = tag_source(source)
    assert "C10" in tags


def test_tag_source_detects_c10_manual_reduction():
    source = """
def total(nums):
    s = 0
    for n in nums:
        s += n
    return s
"""
    tags = tag_source(source)
    assert "C10" in tags


def test_tag_source_clean_function_minimal_tags():
    source = """
def add(a: int, b: int) -> int:
    return a + b
"""
    tags = tag_source(source)
    # Clean function should have very few or no smells
    assert len(tags) <= 1


# Surrogate feature vector tests

def test_feature_schema_version_is_3():
    assert FEATURE_SCHEMA_VERSION == 3


def test_feature_vector_length():
    extractor = SourceFeatureExtractor()
    source = "def f(x):\n    return x + 1\n"
    features = extractor.features(source)
    # 38 base + 9 dynamic = 47 total
    assert len(features) == 47


def test_feature_vector_base_length():
    extractor = SourceFeatureExtractor()
    source = "def f(x):\n    return x + 1\n"
    base = extractor._base_features(source)
    # 17 original + 15 Phase 1 additions + 6 Phase 2 additions = 38
    assert len(base) == 38


def test_feature_vector_nested_loop_indicator():
    extractor = SourceFeatureExtractor()
    flat = "def f(xs):\n    for x in xs:\n        pass\n"
    nested = "def f(xs, ys):\n    for x in xs:\n        for y in ys:\n            pass\n"
    flat_feat = extractor._base_features(flat)
    nested_feat = extractor._base_features(nested)
    # has_nested_loop is feature index 17 (first Phase 1 addition)
    assert flat_feat[17] == 0.0
    assert nested_feat[17] == 1.0


def test_feature_vector_string_concat_loop_indicator():
    extractor = SourceFeatureExtractor()
    no_concat = "def f(ws):\n    return ''.join(ws)\n"
    with_concat = "def f(ws):\n    s = ''\n    for w in ws:\n        s += w\n    return s\n"
    assert extractor._base_features(no_concat)[21] == 0.0
    assert extractor._base_features(with_concat)[21] == 1.0


def test_feature_vector_recursive_indicator():
    extractor = SourceFeatureExtractor()
    iterative = "def f(n):\n    return sum(range(n))\n"
    recursive = "def f(n):\n    if n <= 0: return 0\n    return n + f(n-1)\n"
    assert extractor._base_features(iterative)[22] == 0.0
    assert extractor._base_features(recursive)[22] == 1.0


def test_feature_vector_range_len_loop_indicator():
    extractor = SourceFeatureExtractor()
    idiomatic = "def f(data):\n    for x in data:\n        pass\n"
    antipattern = "def f(data):\n    for i in range(len(data)):\n        pass\n"
    # has_range_len_loop is index 30 in base features
    assert extractor._base_features(idiomatic)[30] == 0.0
    assert extractor._base_features(antipattern)[30] == 1.0


def test_feature_vector_bare_open_indicator():
    extractor = SourceFeatureExtractor()
    safe = "def f(p):\n    with open(p) as f:\n        return f.read()\n"
    unsafe = "def f(p):\n    f = open(p)\n    return f.read()\n"
    # has_bare_open is index 31
    assert extractor._base_features(safe)[31] == 0.0
    assert extractor._base_features(unsafe)[31] == 1.0


def test_feature_vector_caching_works():
    extractor = SourceFeatureExtractor(cache_size=10)
    source = "def f(x):\n    return x * 2\n"
    f1 = extractor._base_features(source)
    f2 = extractor._base_features(source)
    assert np.array_equal(f1, f2)
    assert len(extractor._base_cache) == 1


def test_feature_vector_syntax_error_returns_zeros():
    extractor = SourceFeatureExtractor()
    bad = "def f(: broken syntax"
    feat = extractor._base_features(bad)
    # Loop/comp/call counts should all be 0
    assert feat[2] == 0.0  # loop_count
    assert feat[3] == 0.0  # comp_count


def test_feature_hints_populate_dynamic_slots():
    extractor = SourceFeatureExtractor()
    source = "def f(x):\n    return x\n"
    hints = {
        "parent_len_delta": 5.0,
        "generation_depth": 2.0,
        "operator_index": 7.0,
        "operator_tier": 1.0,
        "op_success_rate": 0.8,
        "op_frontier_rate": 0.3,
    }
    features = extractor.features(source, feature_hints=hints)
    base_len = len(extractor._base_features(source))
    dynamic = features[base_len:]
    assert dynamic[0] == pytest.approx(5.0)   # parent_len_delta
    assert dynamic[1] == pytest.approx(2.0)   # generation_depth
    assert dynamic[5] == pytest.approx(7.0)   # operator_index
    assert dynamic[6] == pytest.approx(1.0)   # operator_tier
    assert dynamic[7] == pytest.approx(0.8)   # op_success_rate
    assert dynamic[8] == pytest.approx(0.3)   # op_frontier_rate


# Registry smell-routing tests

def test_targets_smells_on_all_deterministic_operators():
    from joule.transformers.deterministic import default_deterministic_operators
    ops = default_deterministic_operators()
    missing = [op.name for op in ops if not op.targets_smells]
    assert missing == [], f"Operators missing targets_smells: {missing}"


def test_targets_smells_on_deterministic_base_class():
    from joule.transformers.base import BaseOperator
    # default is frozenset() — subclasses override
    assert BaseOperator.targets_smells == frozenset()


def test_registry_smell_overlap_boosts_matching_operator():
    """Operator targeting a smell present in source should rank higher than one that doesn't."""
    from joule.transformers.registry import OperatorRegistry
    from joule.models import SearchPhase

    registry = OperatorRegistry(llm_model="", include_llm=False)

    # Source with clear C5 smell: list membership check
    source_with_c5 = "def f(x):\n    return x in [1, 3, 5, 7, 9, 11]\n"

    from joule.models import TargetSpec
    from pathlib import Path
    target = TargetSpec(
        project_root=Path("."),
        module="m",
        file_path=Path("m.py"),
        function_name="f",
        qualname="f",
        owner_path=[],
        line_start=1,
        line_end=2,
        source=source_with_c5,
    )

    ranked = registry.select_operators_for_candidate(
        target=target,
        context=None,
        phase=SearchPhase.EXPLORATION,
        parent_generation=0,
        top_k=len(registry.operators),
    )

    # ContainerMembershipOperator targets C5 — should precede operators with no C5
    c5_ops = {op.name for op in ranked if "C5" in op.targets_smells}
    non_c5_ops = {op.name for op in ranked if not op.targets_smells & {"C5"}}

    if c5_ops and non_c5_ops:
        # At least the first C5 operator should appear before the last non-C5 operator
        c5_positions = [i for i, op in enumerate(ranked) if op.name in c5_ops]
        non_c5_positions = [i for i, op in enumerate(ranked) if op.name in non_c5_ops]
        assert min(c5_positions) < max(non_c5_positions)


def test_registry_tier_phase_coupling_exploration_prefers_tier_l():
    """In exploration phase, Tier L operators should generally rank above Tier H."""
    from joule.transformers.registry import OperatorRegistry
    from joule.models import SearchPhase, Tier

    registry = OperatorRegistry(llm_model="", include_llm=False)
    # Neutral source — no strong smell signals
    source = "def f(x):\n    return x + 1\n"
    from joule.models import TargetSpec
    from pathlib import Path
    target = TargetSpec(
        project_root=Path("."),
        module="m",
        file_path=Path("m.py"),
        function_name="f",
        qualname="f",
        owner_path=[],
        line_start=1,
        line_end=2,
        source=source,
    )
    all_ops = registry.ranked(phase=SearchPhase.EXPLORATION, parent_generation=0)
    tier_l = [op for op in all_ops if op.tier == Tier.L]
    tier_h = [op for op in all_ops if op.tier.value == "H"]

    if tier_l and tier_h:
        # Average rank of L operators should be better (lower index) than H
        avg_l = sum(i for i, op in enumerate(all_ops) if op.tier == Tier.L) / len(tier_l)
        avg_h = sum(i for i, op in enumerate(all_ops) if op.tier.value == "H") / len(tier_h)
        assert avg_l < avg_h, "Tier L should have better average rank than Tier H in exploration"
