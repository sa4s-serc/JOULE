def membership_total(values: list[int]) -> int:
    total = 0
    for _ in range(150):
        for value in values:
            if value in [1, 3, 5, 7, 9, 11, 13, 15]:
                total += value
    return total


def unreferenced_total(limit: int = 200) -> int:
    return sum([value for value in range(limit) if value % 3 == 0])


def optimization_surface_demo(values: list[int], lookup: dict[int, int]) -> tuple[str, int, bool]:
    labels = []
    for index in range(len(values)):
        value = values[index]
        if value in [1, 3, 5, 7, 9, 11]:
            labels.append("v=" + str(value) + ";")

    deduped = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)

    if True:
        subtotal = 0
    else:
        subtotal = -1

    for item in values:
        if item in lookup.keys():
            subtotal += lookup[item]

    joined = ",".join([label for label in deduped])
    return joined, subtotal, not (0 in lookup)
