# ============================================================
# Iteration: 6
# Operator:  ItertoolsDelegateLLM
# Status:    PASS
# ============================================================

import itertools
from itertools import zip_longest
import math

def task_func(l1, l2, THRESHOLD = 0.5):
    min_diff = math.inf
    closest_element = None
    found_element = False

    for val in itertools.chain.from_iterable(zip_longest(l1, l2)):
        if val is not None:
            current_diff = abs(val - THRESHOLD)
            if current_diff < min_diff:
                min_diff = current_diff
                closest_element = val
            found_element = True

    if not found_element:
        raise ValueError("attempt to get argmin of an empty sequence")

    return closest_element