# ============================================================
# Iteration: 5
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

from itertools import zip_longest
import math
import numpy as np

def task_func(l1, l2, THRESHOLD = 0.5):
    all_values = [val for pair in zip_longest(l1, l2) for val in pair if val is not None]

    if not all_values:
        raise ValueError("attempt to get argmin of an empty sequence")

    np_values = np.array(all_values)
    diffs = np.abs(np_values - THRESHOLD)
    min_diff_idx = np.argmin(diffs)
    closest_element = np_values[min_diff_idx]

    return closest_element