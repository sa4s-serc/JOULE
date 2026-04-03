def membership_total(values: list[int]) -> int:
    total = 0
    for _ in range(200):
        for value in values:
            if value in [1, 3, 5, 7, 9, 11, 13, 15]:
                total += value
    return total


def unreferenced_total(limit: int = 200) -> int:
    return sum([value for value in range(limit) if value % 3 == 0])


async def async_square_total(limit: int = 10) -> int:
    return sum(value * value for value in range(limit))


async def async_orphan_total(limit: int = 10) -> int:
    return sum(value + 1 for value in range(limit))


class NumberCruncher:
    def generator_total(self, limit: int = 50) -> int:
        return sum([value for value in range(limit) if value % 2 == 0])


def impure_total(limit: int = 5) -> int:
    print("side effect")
    return limit


def outer_total(limit: int = 5) -> int:
    def inner_total(value: int) -> int:
        return value * 2

    return sum(inner_total(value) for value in range(limit))
