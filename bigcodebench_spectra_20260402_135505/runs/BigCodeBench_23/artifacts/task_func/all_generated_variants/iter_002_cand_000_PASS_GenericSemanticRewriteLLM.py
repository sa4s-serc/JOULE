# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import numpy as np
from itertools import zip_longest

def task_func(l1, l2,THRESHOLD = 0.5):
    combined_gen = (val for pair in zip_longest(l1, l2) for val in pair if val is not None)
    combined_arr = np.fromiter(combined_gen, dtype=float)
    differences = np.abs(combined_arr - THRESHOLD)
    closest_index = np.argmin(differences)
    return combined_arr[closest_index]