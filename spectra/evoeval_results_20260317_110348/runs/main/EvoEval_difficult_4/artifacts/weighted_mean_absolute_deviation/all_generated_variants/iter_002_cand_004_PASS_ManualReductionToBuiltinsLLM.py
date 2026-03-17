# ============================================================
# Iteration: 2
# Operator:  ManualReductionToBuiltinsLLM
# Status:    PASS
# ============================================================

from typing import List, Tuple


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    if any(w <= 0 for _, w in numbers):
        return "Weights must be positive and sum to 1"

    total_weight = sum(w for _, w in numbers)
    weighted_sum = sum(x * w for x, w in numbers)

    if total_weight != 1:
        return "Weights must be positive and sum to 1"

    weighted_mean = weighted_sum 

    wmad = sum(w * abs(x - weighted_mean) for x, w in numbers)

    return wmad