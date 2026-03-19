# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import heapq

def next_smallest_and_largest(lst):
    unique_elements = list(set(lst))

    if len(unique_elements) < 2:
        return (None, None)

    smallest_two = heapq.nsmallest(2, unique_elements)
    largest_two = heapq.nlargest(2, unique_elements)

    return (smallest_two[1], largest_two[1])