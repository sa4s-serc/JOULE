# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import math
from functools import reduce

def _update_min_max_state(acc, num):
    smallest, second_smallest, largest, second_largest = acc

    if num < smallest:
        second_smallest = smallest
        smallest = num
    elif num < second_smallest and num != smallest:
        second_smallest = num

    if num > largest:
        second_largest = largest
        largest = num
    elif num > second_largest and num != largest:
        second_largest = num

    return (smallest, second_smallest, largest, second_largest)

def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    initial_state = (math.inf, math.inf, -math.inf, -math.inf)
    
    final_state = reduce(_update_min_max_state, lst, initial_state)
    
    second_smallest_val = final_state[1]
    second_largest_val = final_state[3]

    if second_smallest_val == math.inf:
        second_smallest_val = None
    if second_largest_val == -math.inf:
        second_largest_val = None

    return (second_smallest_val, second_largest_val)