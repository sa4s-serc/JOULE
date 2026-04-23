# ============================================================
# Iteration: 5
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

from __future__ import annotations
from typing import Tuple

EPSILON: float = 0.00001


def compare_float(x: float, y: float) -> bool:
    return abs(x - y) <= EPSILON


def clamp_number(number: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(number, maximum))


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

    def __add__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return Color(self._components[0] + c, self._components[1] + c, self._components[2] + c)
        return Color(self._components[0] + c._components[0],
                     self._components[1] + c._components[1],
                     self._components[2] + c._components[2])

    def __radd__(self, c: Color | float) -> Color:
        return self + c

    def __sub__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return Color(self._components[0] - c, self._components[1] - c, self._components[2] - c)
        return Color(self._components[0] - c._components[0],
                     self._components[1] - c._components[1],
                     self._components[2] - c._components[2])

    def __mul__(self, c: Color | float) -> Color:
        if isinstance(c, (int, float)):
            return Color(self._components[0] * c, self._components[1] * c, self._components[2] * c)
        return Color(self._components[0] * c._components[0],
                     self._components[1] * c._components[1],
                     self._components[2] * c._components[2])

    def __rmul__(self, c: float) -> Color:
        return self * c

    def __truediv__(self, c: float) -> Color:
        return Color(self._components[0] / c, self._components[1] / c, self._components[2] / c)

    def __neg__(self) -> Color:
        return Color(-self._components[0], -self._components[1], -self._components[2])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return compare_float(self._components[0], other._components[0]) and \
               compare_float(self._components[1], other._components[1]) and \
               compare_float(self._components[2], other._components[2])

    def clamp(self, minimum: float, maximum: float) -> Color:
        return Color(max(minimum, min(self._components[0], maximum)),
                     max(minimum, min(self._components[1], maximum)),
                     max(minimum, min(self._components[2], maximum)))

    def as_rgb_list(self) -> list:
        return [int(max(0, min(value * 255.0, 255))) for value in self._components]


def hadamard_product(c1: Color, c2: Color) -> Color:
    return c1 * c2


def hadamard_product_entry(r1: float, g1: float, b1: float,
                            r2: float, g2: float, b2: float) -> tuple:
    return (r1 * r2, g1 * g2, b1 * b2)