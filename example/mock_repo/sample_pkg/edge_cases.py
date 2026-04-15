from __future__ import annotations


def recursive_inventory_checksum(values: list[int], index: int = 0) -> int:
    if index >= len(values):
        return 0
    return values[index] + recursive_inventory_checksum(values, index + 1)


def impure_inventory_trace(values: list[int]) -> int:
    print("computing inventory trace")
    return sum(values)


def nested_factory_total(limit: int = 6) -> int:
    def inner(value: int) -> int:
        return value * 3

    return sum(inner(value) for value in range(limit))
