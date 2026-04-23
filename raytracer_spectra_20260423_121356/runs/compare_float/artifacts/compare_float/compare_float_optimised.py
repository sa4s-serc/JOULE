"""Ray Tracer Challenge - Float comparison utility
Source: ray_tracer_challenge/utilities.py
"""
from typing import Final

EPSILON: Final[float] = 0.00001


def compare_float(x: float, y: float) -> bool:
    """Compare two floats within epsilon tolerance."""
    return abs(x - y) <= EPSILON