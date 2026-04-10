from sample_pkg.algos import membership_total, optimization_surface_demo


def test_membership_total() -> None:
    values = list(range(16))
    expected = sum(value for value in values if value in {1, 3, 5, 7, 9, 11, 13, 15}) * 150
    assert membership_total(values) == expected


def test_optimization_surface_demo() -> None:
    values = [0, 1, 1, 2, 3, 7, 7, 12]
    lookup = {1: 10, 3: 30, 7: 70}
    joined, subtotal, missing_zero = optimization_surface_demo(values, lookup)

    assert joined == "v=1;,v=3;,v=7;"
    assert subtotal == 190
    assert missing_zero is True
