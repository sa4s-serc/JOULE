# ============================================================
# Iteration: 2
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from typing import List, Tuple


def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    data = np.array(numbers)

    if data.size == 0:
        return "Weights must be positive and sum to 1"

    x_values = data[:, 0]
    weights = data[:, 1]

    if np.any(weights <= 0):
        return "Weights must be positive and sum to 1"

    total_weight = np.sum(weights)
    weighted_sum = np.sum(x_values * weights)

    if total_weight != 1:
        return "Weights must be positive and sum to 1"

    weighted_mean = weighted_sum

    wmad = np.sum(weights * np.abs(x_values - weighted_mean))

    return wmad