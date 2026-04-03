def membership_total(values: list[int]) -> int:
    total = 0
    for _ in range(150):
        for value in values:
            if value in [1, 3, 5, 7, 9, 11, 13, 15]:
                total += value
    return total


def unreferenced_total(limit: int = 200) -> int:
    return sum([value for value in range(limit) if value % 3 == 0])
