# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

from __future__ import annotations
import math
import operator
from functools import partial
from typing import Callable

EPSILON: float = 0.00001


def compare_float(x: float, y: float) -> bool:
    return abs(x - y) <= EPSILON


class Vector:
    __slots__ = ('i', 'j', 'k')

    def __init__(self, i: float, j: float, k: float) -> None:
        self.i = i
        self.j = j
        self.k = k

    def __map_element_wise(self, op: Callable[[float], float]) -> Vector:
        return Vector(op(self.i), op(self.j), op(self.k))

    def __map_pair_wise(self, v: Vector, op: Callable[[float, float], float]) -> Vector:
        return Vector(op(self.i, v.i), op(self.j, v.j), op(self.k, v.k))

    def __add__(self, v: Vector | float) -> Vector:
        if isinstance(v, (int, float)):
            return self.__map_element_wise(partial(operator.add, v))
        return self.__map_pair_wise(v, operator.add)

    def __sub__(self, v: Vector | float) -> Vector:
        if isinstance(v, (int, float)):
            return self.__map_element_wise(lambda x: x - v)
        return self.__map_pair_wise(v, operator.sub)

    def __mul__(self, v: Vector | float) -> Vector:
        if isinstance(v, (int, float)):
            return self.__map_element_wise(partial(operator.mul, v))
        return self.__map_pair_wise(v, operator.mul)

    def __rmul__(self, v: float) -> Vector:
        return self * v

    def __truediv__(self, c: float) -> Vector:
        return self.__map_element_wise(lambda x: x / c)

    def __neg__(self) -> Vector:
        return Vector(-self.i, -self.j, -self.k)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return (
            compare_float(self.i, other.i)
            and compare_float(self.j, other.j)
            and compare_float(self.k, other.k)
        )

    @property
    def sum(self) -> float:
        return self.i + self.j + self.k

    @property
    def norm(self) -> float:
        return math.sqrt(dot_product(self, self))

    def normalize(self) -> Vector:
        return self / self.norm


def dot_product(u: Vector, v: Vector) -> float:
    return (u * v).sum


def reflect(vector: Vector, normal: Vector) -> Vector:
    """Reflect vector across the normal vector."""
    return vector - 2 * dot_product(vector, normal) * normal


def reflect_entry(vi: float, vj: float, vk: float,
                  ni: float, nj: float, nk: float) -> tuple:
    """Flat entry point: (vector i,j,k) and (normal i,j,k) → reflected (i, j, k)."""
    dp_val = vi * ni + vj * nj + vk * nk
    scalar_factor = 2 * dp_val
    ri = vi - scalar_factor * ni
    rj = vj - scalar_factor * nj
    rk = vk - scalar_factor * nk
    return (ri, rj, rk)