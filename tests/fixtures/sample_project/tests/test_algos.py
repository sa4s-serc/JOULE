from sample_pkg.algos import (
    counter_histogram,
    deque_frontier,
    local_import_json_encode,
    membership_total,
    sort_then_membership,
    string_concat_report,
    tuple_unpack_accumulator,
)


def test_membership_total() -> None:
    values = list(range(16))
    expected = sum(value for value in values if value in {1, 3, 5, 7, 9, 11, 13, 15}) * 200
    assert membership_total(values) == expected


def test_string_concat_report() -> None:
    output = string_concat_report(["alpha", " beta ", ""], rounds=2)
    assert output == "alpha|beta|alpha|beta|"


def test_sort_then_membership() -> None:
    result = sort_then_membership([5, 1, 9, 1, 3], [1, 2, 9])
    assert result == {1: True, 2: False, 9: True}


def test_counter_histogram() -> None:
    result = counter_histogram(["A", "a ", "B", "", "b", "  a"])
    assert result == {"a": 3, "b": 2}


def test_deque_frontier() -> None:
    result = deque_frontier([10, 20, 30, 40], batch_size=3)
    assert result == [10, 20, 30]


def test_local_import_json_encode() -> None:
    result = local_import_json_encode([{"b": 2, "a": 1}, {"z": 9}])
    assert result == ['{"a": 1, "b": 2}', '{"z": 9}']


def test_tuple_unpack_accumulator() -> None:
    assert tuple_unpack_accumulator([(2, 4), (3, 5), (-1, 9)]) == 14
