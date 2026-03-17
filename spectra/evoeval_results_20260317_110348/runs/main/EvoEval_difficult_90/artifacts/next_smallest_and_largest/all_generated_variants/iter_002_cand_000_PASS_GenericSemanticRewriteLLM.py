# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import heapq

def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    unique_elements = list(set(lst))

    if len(unique_elements) < 2:
        return (None, None)

    smallest_two = heapq.nsmallest(2, unique_elements)
    largest_two = heapq.nlargest(2, unique_elements)

    second_smallest = smallest_two[1]
    second_largest = largest_two[1]

    return (second_smallest, second_largest)