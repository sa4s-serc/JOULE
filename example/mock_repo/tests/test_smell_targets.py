"""Tests for smell_targets.py — correctness oracle for optimization runs.

Each test validates the semantic contract of its target function.
JOULE uses these tests as the correctness gate during optimization.
"""
from __future__ import annotations

import pytest

from sample_pkg.smell_targets import (
    build_report,
    classify_events,
    collect_tokens,
    extract_numbers,
    find_common_elements,
    index_based_sum,
    path_count,
    safe_lookup,
    score_items,
    tally_categories,
)


# ── index_based_sum ────────────────────────────────────────────────────────

def test_index_based_sum_basic():
    assert index_based_sum([1.0, 2.0, 3.0, 4.0]) == pytest.approx(10.0)


def test_index_based_sum_empty():
    assert index_based_sum([]) == pytest.approx(0.0)


def test_index_based_sum_single():
    assert index_based_sum([42.0]) == pytest.approx(42.0)


def test_index_based_sum_floats():
    assert index_based_sum([0.1, 0.2, 0.3]) == pytest.approx(0.6)


# ── build_report ───────────────────────────────────────────────────────────

def test_build_report_basic():
    records = [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]
    result = build_report(records, rounds=1)
    assert "a=1;" in result
    assert "b=2;" in result


def test_build_report_empty_records():
    assert build_report([], rounds=5) == ""


def test_build_report_skips_blank():
    records = [{"name": "", "value": "x"}, {"name": "k", "value": "v"}]
    result = build_report(records, rounds=1)
    assert "k=v;" in result
    assert "=x;" not in result


def test_build_report_rounds():
    records = [{"name": "x", "value": "1"}]
    r1 = build_report(records, rounds=1)
    r3 = build_report(records, rounds=3)
    assert len(r3) == len(r1) * 3


# ── classify_events ────────────────────────────────────────────────────────

def test_classify_events_partitions_correctly():
    event_ids = [1, 2, 3, 4, 5]
    priority_ids = [2, 4]
    result = classify_events(event_ids, priority_ids)
    # Each id appears 100 times (rounds=100) in each bucket
    assert set(x for x in result["priority"]) == {2, 4}
    assert set(x for x in result["normal"]) == {1, 3, 5}


def test_classify_events_empty_events():
    result = classify_events([], [1, 2])
    assert result == {"priority": [], "normal": []}


def test_classify_events_no_priority():
    result = classify_events([1, 2, 3], [])
    assert all(e not in result["priority"] for e in [1, 2, 3])
    assert len(result["normal"]) == 300  # 3 items × 100 rounds


# ── safe_lookup ────────────────────────────────────────────────────────────

def test_safe_lookup_present_keys():
    assert safe_lookup({"a": 1, "b": 2}, ["a", "b"]) == [1, 2]


def test_safe_lookup_missing_keys():
    assert safe_lookup({"a": 1}, ["a", "x", "y"]) == [1, 0, 0]


def test_safe_lookup_empty():
    assert safe_lookup({}, []) == []


def test_safe_lookup_all_missing():
    assert safe_lookup({}, ["p", "q", "r"]) == [0, 0, 0]


# ── collect_tokens ─────────────────────────────────────────────────────────

def test_collect_tokens_returns_list():
    # Use fresh list to avoid default arg state leakage between test runs
    result = collect_tokens("hello world", acc=[])
    assert result == ["hello", "world"]


def test_collect_tokens_multiple_calls_independent():
    r1 = collect_tokens("foo bar", acc=[])
    r2 = collect_tokens("baz", acc=[])
    assert r1 == ["foo", "bar"]
    assert r2 == ["baz"]


# ── path_count ─────────────────────────────────────────────────────────────

def test_path_count_1x1():
    assert path_count(1, 1) == 1


def test_path_count_2x2():
    assert path_count(2, 2) == 2


def test_path_count_3x3():
    assert path_count(3, 3) == 6


def test_path_count_single_row():
    assert path_count(1, 5) == 1


def test_path_count_single_col():
    assert path_count(5, 1) == 1


def test_path_count_4x4():
    assert path_count(4, 4) == 20


# ── extract_numbers ────────────────────────────────────────────────────────

def test_extract_numbers_basic():
    result = extract_numbers(["abc 12 def 34", "no numbers here", "99"])
    assert result[0] == ["12", "34"]
    assert result[1] == []
    assert result[2] == ["99"]


def test_extract_numbers_empty_list():
    assert extract_numbers([]) == []


def test_extract_numbers_empty_string():
    assert extract_numbers([""]) == [[]]


# ── find_common_elements ───────────────────────────────────────────────────

def test_find_common_elements_basic():
    result = find_common_elements([1, 2, 3, 4], [3, 4, 5, 6])
    assert sorted(result) == [3, 4]


def test_find_common_elements_no_overlap():
    assert find_common_elements([1, 2], [3, 4]) == []


def test_find_common_elements_identical():
    result = find_common_elements([1, 2, 3], [1, 2, 3])
    assert sorted(result) == [1, 2, 3]


def test_find_common_elements_empty():
    assert find_common_elements([], [1, 2]) == []
    assert find_common_elements([1, 2], []) == []


def test_find_common_elements_no_duplicates_in_result():
    # Even if value appears multiple times in either list
    result = find_common_elements([1, 1, 2], [1, 2, 2])
    assert len(result) == len(set(result))


# ── score_items ────────────────────────────────────────────────────────────

def test_score_items_basic():
    items = [{"a": 1.0, "b": 2.0}]
    weights = {"a": 1.0, "b": 1.0}
    result = score_items(items, weights, scale=100.0)
    assert result == pytest.approx([150.0])  # (1+2)/(1+1) * 100


def test_score_items_empty_weights():
    result = score_items([{"a": 1.0}], {}, scale=100.0)
    assert result == [0.0]


def test_score_items_empty_items():
    assert score_items([], {"a": 1.0}) == []


def test_score_items_missing_key_in_item():
    items = [{"a": 5.0}]
    weights = {"a": 1.0, "b": 1.0}
    result = score_items(items, weights, scale=100.0)
    assert result == pytest.approx([250.0])  # (5+0)/(1+1) * 100


# ── tally_categories ───────────────────────────────────────────────────────

def test_tally_categories_basic():
    items = [("fruit", 3), ("veggie", 2), ("fruit", 1), ("other", 5)]
    valid = ["fruit", "veggie"]
    result = tally_categories(items, valid)
    assert result == {"fruit": 4, "veggie": 2}


def test_tally_categories_no_valid():
    result = tally_categories([("a", 1), ("b", 2)], [])
    assert result == {}


def test_tally_categories_empty_items():
    assert tally_categories([], ["fruit"]) == {}


def test_tally_categories_all_invalid():
    result = tally_categories([("x", 1), ("y", 2)], ["fruit"])
    assert result == {}
