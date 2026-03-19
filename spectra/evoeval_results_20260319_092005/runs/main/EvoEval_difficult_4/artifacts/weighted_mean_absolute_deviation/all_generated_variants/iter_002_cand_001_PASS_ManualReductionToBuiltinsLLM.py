# ============================================================
# Iteration: 2
# Operator:  ManualReductionToBuiltinsLLM
# Status:    PASS
# ============================================================

from typing import List, Tuple


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    if any(w <= 0 for x, w in numbers):
        return "Weights must be positive and sum to 1"

    total_weight = sum(w for x, w in numbers)
    sum_x_times_w = sum(x * w for x, w in numbers)

    if total_weight != 1.0:
        return "Weights must be positive and sum to 1"

    weighted_mean = sum_x_times_w

    sum_w_abs_diff = sum(w * abs(x - weighted_mean) for x, w in numbers)

    return sum_w_abs_diff