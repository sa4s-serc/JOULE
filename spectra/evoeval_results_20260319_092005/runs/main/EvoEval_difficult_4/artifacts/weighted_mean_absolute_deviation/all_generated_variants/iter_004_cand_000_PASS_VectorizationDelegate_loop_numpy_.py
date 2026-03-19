# ============================================================
# Iteration: 4
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from typing import List, Tuple


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    if not numbers:
        return "Weights must be positive and sum to 1"

    data = np.array(numbers, dtype=float)
    x_values = data[:, 0]
    w_values = data[:, 1]

    if np.any(w_values <= 0):
        return "Weights must be positive and sum to 1"

    total_weight = np.sum(w_values)
    sum_x_times_w = np.sum(x_values * w_values)

    if total_weight != 1.0:
        return "Weights must be positive and sum to 1"

    weighted_mean = sum_x_times_w

    sum_w_abs_diff = np.sum(w_values * np.abs(x_values - weighted_mean))

    return sum_w_abs_diff