# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Exception: name 'seen_' is not defined
# ============================================================

import heapq

def next_smallest_and_largest(lst):
    if len(lst) < 2:
        return (None, None)

    # Use a max-heap of size 2 to find the two smallest distinct elements.
    # Store negative values to simulate a max-heap with heapq (which is a min-heap).
    # The heap will contain [-second_smallest, -smallest]
    smallest_heap = []
    seen_smallest = set()

    # Use a min-heap of size 2 to find the two largest distinct elements.
    # The heap will contain [second_largest, largest]
    largest_heap = []
    seen_largest = set()

    for num in lst:
        # Process for smallest
        if num not in seen_smallest:
            heapq.heappush(smallest_heap, -num)
            seen_smallest.add(num)
            if len(smallest_heap) > 2:
                popped_val = -heapq.heappop(smallest_heap)
                seen_smallest.remove(popped_val)

        # Process for largest
        if num not in seen_largest:
            heapq.heappush(largest_heap, num)
            seen_largest.add(num)
            if len(largest_heap) > 2:
                popped_val = heapq.heappop(largest_heap)
                seen_