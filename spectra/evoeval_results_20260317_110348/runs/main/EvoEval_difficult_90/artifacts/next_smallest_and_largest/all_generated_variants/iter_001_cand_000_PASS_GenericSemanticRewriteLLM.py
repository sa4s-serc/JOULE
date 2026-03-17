# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import heapq

def next_smallest_and_largest(lst):
    unique_elements = list(set(lst))

    n_unique = len(unique_elements)

    if n_unique < 2:
        return (None, None)

    second_smallest = heapq.nsmallest(2, unique_elements)[1]
    second_largest = heapq.nlargest(2, unique_elements)[1]

    return (second_smallest, second_largest)