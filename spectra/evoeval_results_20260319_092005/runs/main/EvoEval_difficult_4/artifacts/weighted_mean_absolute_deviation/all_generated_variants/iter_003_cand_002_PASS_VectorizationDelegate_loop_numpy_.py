# ============================================================
# Iteration: 3
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from typing import List, Tuple

def weighted_mean_absolute_deviation(numbers: List[Tuple[float, float]]) -> float:
    data = np.array(numbers, dtype=float).reshape(-1, 2)
    x = data[:, 0]
    w = data[:, 1]

    if (w <= 0).any():
        return 'Weights must be positive and sum to 1'

    total_weight = np.sum(w)
    if total_weight != 1.0:
        return 'Weights must be positive and sum to 1'

    weighted_mean = np.sum(x * w)
    
    sum_w_abs_diff = np.sum(w * np.abs(x - weighted_mean))
    return sum_w_abs_diff