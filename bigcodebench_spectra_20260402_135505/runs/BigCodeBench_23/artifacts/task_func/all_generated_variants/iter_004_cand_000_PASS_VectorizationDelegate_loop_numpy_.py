# ============================================================
# Iteration: 4
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from itertools import zip_longest

def task_func(l1, l2, THRESHOLD = 0.5):
    all_values_list = []
    for pair in zip_longest(l1, l2):
        for val in pair:
            if val is not None:
                all_values_list.append(val)

    if not all_values_list:
        raise ValueError("attempt to get argmin of an empty sequence")

    arr = np.array(all_values_list, dtype=float)

    diffs = np.abs(arr - THRESHOLD)

    min_diff_idx = np.argmin(diffs)

    closest_element = arr[min_diff_idx]

    return closest_element