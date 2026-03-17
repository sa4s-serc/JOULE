# ============================================================
# Iteration: 2
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

from typing import List, Tuple
from functools import lru_cache


@lru_cache(maxsize=None)
def _cached_sum_weights(weights_tuple: Tuple[float, ...]) -> float:
    return sum(weights_tuple)


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    weights = [w for x, w in numbers]
    
    weights_tuple = tuple(weights)
    
    total_weight = _cached_sum_weights(weights_tuple)

    if any(w <= 0 for w in weights) or total_weight != 1:
        return "Weights must be positive and sum to 1"

    weighted_mean = sum(x * w for x, w in numbers)

    wmad = sum(w * abs(x - weighted_mean) for x, w in numbers) / total_weight

    return wmad