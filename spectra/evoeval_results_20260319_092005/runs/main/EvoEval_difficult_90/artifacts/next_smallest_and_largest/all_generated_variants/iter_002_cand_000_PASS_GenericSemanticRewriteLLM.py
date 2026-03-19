# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import math

def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    smallest = math.inf
    second_smallest = math.inf
    largest = -math.inf
    second_largest = -math.inf

    for num in lst:
        # Process for smallest and second smallest
        if num < smallest:
            second_smallest = smallest
            smallest = num
        elif num < second_smallest and num != smallest:
            second_smallest = num
        
        # Process for largest and second largest
        if num > largest:
            second_largest = largest
            largest = num
        elif num > second_largest and num != largest:
            second_largest = num

    # Final check for sentinel values
    if second_smallest == math.inf:
        second_smallest = None
    if second_largest == -math.inf:
        second_largest = None

    return (second_smallest, second_largest)