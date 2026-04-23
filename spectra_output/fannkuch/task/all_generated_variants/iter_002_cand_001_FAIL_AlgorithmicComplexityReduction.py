# ============================================================
# Iteration: 2
# Operator:  AlgorithmicComplexityReduction
# Status:    FAIL
# Reason:    Function not found in compiled source
# ============================================================

from math import factorial
from itertools import islice


def permutations(n, start, size):
    # Precompute factorials for efficiency
    factorials = [1] * n
    for i in range(1, n):
        factorials[i] = factorials[i-1] * i

    p = bytearray(range(n))
    count = bytearray(n)

    remainder = start
    for v in range(n - 1, 0, -1):
        # Use precomputed factorial
        fact_v = factorials[v]
        num_rotations, remainder = divmod(remainder, fact_v)

        # Apply num_rotations of the cyclic left shift on p[0...v]
        # This is equivalent to p[0...v] = p[num_rotations...v] + p[0...num_rotations-1]
        if num_rotations > 0:
            temp_slice = p[0:v+1]
            p[0:v+1] = temp_slice[num_rotations:] + temp_slice[0:num_rotations]
        if remainder == 0:
            break

    assert(count[1] == 0)
    assert(size < 2 or (size % 2 == 0))

    # Optimize rotation_swaps precomputation from O(N^3) to O(N^