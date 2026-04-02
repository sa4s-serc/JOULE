# ============================================================
# Iteration: 6
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from itertools import zip_longest
import math

def task_func(l1, l2, THRESHOLD = 0.5):
    all_elements = [val for sublist in zip_longest(l1, l2) for val in sublist if val is not None]

    if not all_elements:
        raise ValueError("attempt to get argmin of an empty sequence")

    np_elements = np.array(all_elements)
    diffs = np.abs(np_elements - THRESHOLD)
    min_diff_idx = np.argmin(diffs)
    closest_element = np_elements[min_diff_idx]

    return closest_element