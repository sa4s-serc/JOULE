# ============================================================
# Iteration: 3
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

from functools import lru_cache
from typing import List, Tuple

@lru_cache(maxsize=None)
def _cached_sum_of_weights(numbers_tuple: Tuple[Tuple[float, float]]) -> float:
    return sum(w for x, w in numbers_tuple)

def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    numbers_tuple = tuple(tuple(item) for item in numbers)

    weights = [w for x, w in numbers]
    sum_weights = _cached_sum_of_weights(numbers_tuple)

    if any(w <= 0 for w in weights) or sum_weights != 1:
        return "Weights must be positive and sum to 1"

    weighted_mean = sum(x * w for x, w in numbers)

    wmad = sum(w * abs(x - weighted_mean) for x, w in numbers) / sum_weights

    return wmad