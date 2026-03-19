# ============================================================
# Iteration: 2
# Operator:  MultipleAssignmentFusion
# Status:    PASS
# ============================================================

from typing import List, Tuple

def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    total_weight, sum_x_times_w = (0.0, 0.0)
    for x, w in numbers:
        if w <= 0:
            return 'Weights must be positive and sum to 1'
        total_weight += w
        sum_x_times_w += x * w
    if total_weight != 1.0:
        return 'Weights must be positive and sum to 1'
    weighted_mean = sum_x_times_w
    sum_w_abs_diff = 0.0
    for x, w in numbers:
        sum_w_abs_diff += w * abs(x - weighted_mean)
    return sum_w_abs_diff