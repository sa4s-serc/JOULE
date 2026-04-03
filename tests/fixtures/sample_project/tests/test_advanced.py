from sample_pkg.algos import NumberCruncher, async_square_total


def test_generator_total() -> None:
    cruncher = NumberCruncher()
    expected = sum(value for value in range(50) if value % 2 == 0)
    assert cruncher.generator_total() == expected


def test_async_square_total() -> None:
    import asyncio

    expected = sum(value * value for value in range(10))
    assert asyncio.run(async_square_total()) == expected
