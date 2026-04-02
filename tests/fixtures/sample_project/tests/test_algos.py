from sample_pkg.algos import membership_total


def test_membership_total() -> None:
    values = list(range(16))
    expected = sum(value for value in values if value in {1, 3, 5, 7, 9, 11, 13, 15}) * 200
    assert membership_total(values) == expected
