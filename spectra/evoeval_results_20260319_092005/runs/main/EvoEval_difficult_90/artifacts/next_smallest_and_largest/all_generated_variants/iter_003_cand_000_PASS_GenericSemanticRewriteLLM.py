# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import math

def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    unique_elements = sorted(list(set(lst)))

    if len(unique_elements) < 2:
        return (None, None)
    
    second_smallest = unique_elements[1]
    second_largest = unique_elements[-2]

    return (second_smallest, second_largest)