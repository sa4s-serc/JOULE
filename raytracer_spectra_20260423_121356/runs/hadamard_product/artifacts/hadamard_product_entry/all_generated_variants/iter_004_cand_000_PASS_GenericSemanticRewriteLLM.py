# ============================================================
# Iteration: 4
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

from __future__ import annotations
import operator
from functools import partial
from typing import Callable, Tuple

EPSILON: float = 0.00001


def compare_float(x: float, y: float) -> bool:
    return abs(x - y) <= EPSILON


def clamp_number(number: float, minimum: float, maximum: float) -> float:
    if number < minimum:
        return minimum
    if number > maximum:
        return maximum
    return number


class Color:
    __slots__ = ('_components',)

    def __init__(self, red: float, green: float, blue: float) -> None:
        self._components: Tuple[float, float, float] = (red, green, blue)

    @property
    def red(self) -> float:
        return self._components[0]

    @property
    def green(self) -> float:
        return self._components[1]

    @property
    def blue(self) -> float:
        return self._components[2]

    def __map_element_wise(self, op: Callable[[float], float]) -> Color:
        return Color(*(op(x) for x in self._components))

    def __map_pair_wise(self, c: Color, op: Callable[[float, float], float]) -> Color:
        return Color(*(op(x, y) for x, y in zip(self._components, c._components)))

    def __add__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return self.__map_element_wise(partial(operator.add, c))
        return self.__map_pair_wise(c, operator.add)

    def __radd__(self, c: Color | float) -> Color:
        return self + c

    def __sub__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return self.__map_element_wise(lambda x: x - c)
        return self.__map_pair_wise(c, operator.sub)

    def __mul__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return self.__map_element_wise(partial(operator.mul, c))
        return self.__map_pair_wise(c, operator.mul)

    def __rmul__(self, c: float) -> Color:
        return self * c

    def __truediv__(self, c: float) -> Color:
        return self.__map_element_wise(lambda x: x / c)

    def __neg__(self) -> Color:
        return self.__map_element_wise(operator.neg)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return all(compare_float(x, y) for x, y in zip(self._components, other._components))

    def clamp(self, minimum: float, maximum: float) -> Color:
        return self.__map_element_wise(lambda x: clamp_number(x, minimum, maximum))

    def as_rgb_list(self) -> list:
        return [int(clamp_number(value * 255.0, 0, 255)) for value in self._components]


def hadamard_product(c1: Color, c2: Color) -> Color:
    return c1 * c2


def hadamard_product_entry(r1: float, g1: float, b1: float,
                            r2: float, g2: float, b2: float) -> tuple:
    return (r1 * r2, g1 * g2, b1 * b2)