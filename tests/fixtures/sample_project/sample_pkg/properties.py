from sample_pkg.algos import membership_total


def property_membership_total() -> None:
    values = list(range(20)) * 10
    expected = sum(value for value in values if value in {1, 3, 5, 7, 9, 11, 13, 15}) * 200
    assert membership_total(values) == expected


def property_counter_histogram() -> None:
    from sample_pkg.algos import counter_histogram

    tokens = ["A", "b", "a", "B", "a", "  ", "C"]
    assert counter_histogram(tokens) == {"a": 3, "b": 2, "c": 1}


def property_tuple_unpack_accumulator() -> None:
    from sample_pkg.algos import tuple_unpack_accumulator

    pairs = [(1, 2), (2, 3), (3, 4), (4, 5)]
    assert tuple_unpack_accumulator(pairs) == 40
