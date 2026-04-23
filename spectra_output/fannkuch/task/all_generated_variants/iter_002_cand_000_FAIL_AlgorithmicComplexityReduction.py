# ============================================================
# Iteration: 2
# Operator:  AlgorithmicComplexityReduction
# Status:    FAIL
# Reason:    Function not found in compiled source
# ============================================================

from math import factorial
from itertools import islice


def permutations(n, start, size):
    factorials = [1] * (n + 1)
    for i in range(1, n + 1):
        factorials[i] = factorials[i - 1] * i

    p = bytearray(n)
    elements = list(range(n))
    remainder = start

    # O(N^2) initial permutation generation
    for v in range(n - 1, -1, -1):
        fact_v = factorials[v]
        idx, remainder = divmod(remainder, fact_v)
        p[n - 1 - v] = elements.pop(idx)

    count = bytearray(n) # count[i] stores the number of rotations applied to p[0...i]
                         # relative to the state where p[0...i] is sorted.
                         # This is effectively the Lehmer code digit for position i.

    # Initialize count based on the generated permutation
    # This part is tricky. The original code's `count` array is not a standard Lehmer code.
    # It's used in a specific way for the permutation generation algorithm.
    # The initial `count` values are derived from `start`.
    remainder = start
    for v in range(n - 1, 0, -1):
        count[v], remainder