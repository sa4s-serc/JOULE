# ============================================================
# Iteration: 1
# Operator:  SlotsDelegateLLM
# Status:    PASS
# ============================================================

from __future__ import annotations
import operator
from functools import partial
from typing import Callable

EPSILON: float = 0.00001


def compare_float(x: float, y: float) -> bool:
    return abs(x - y) <= EPSILON


def clamp_number(number: float, minimum: float, maximum: float) -> float:
    if number >= maximum:
        return maximum
    elif number <= minimum:
        return minimum
    else:
        return number


class Color:
    __slots__ = ('red', 'green', 'blue')

    def __init__(self, red: float, green: float, blue: float) -> None:
        self.red = red
        self.green = green
        self.blue = blue

    def __map_element_wise(self, op: Callable[[float], float]) -> Color:
        return Color(op(self.red), op(self.green), op(self.blue))

    def __map_pair_wise(self, c: Color, op: Callable[[float, float], float]) -> Color:
        return Color(op(self.red, c.red), op(self.green, c.green), op(self.blue, c.blue))

    def __add__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return self.__map_element_wise(partial(operator.add, c))
        return self.__map_pair_wise(c, operator.add)

    def __radd__(self, c: Color | float) -> Color:
        return self * c

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
        return Color(-self.red, -self.green, -self.blue)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return (
            compare_float(self.red, other.red)
            and compare_float(self.green, other.green)
            and compare_float(self.blue, other.blue)
        )

    def clamp(self, minimum: float, maximum: float) -> Color:
        return self.__map_element_wise(lambda x: clamp_number(x, minimum, maximum))

    def as_rgb_list(self) -> list:
        def expand_to_byte(value: float) -> int:
            return int(clamp_number(0, 255, value * 255.0))
        return [expand_to_byte(self.red), expand_to_byte(self.green), expand_to_byte(self.blue)]


def hadamard_product(c1: Color, c2: Color) -> Color:
    """Element-wise (Schur) product of two colors."""
    return c1 * c2


def hadamard_product_entry(r1: float, g1: float, b1: float,
                            r2: float, g2: float, b2: float) -> tuple:
    """Flat entry point: two (r,g,b) triples → (r,g,b) product tuple."""
    c1 = Color(r1, g1, b1)
    c2 = Color(r2, g2, b2)
    result = hadamard_product(c1, c2)
    return (result.red, result.green, result.blue)