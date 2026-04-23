# ============================================================
# Iteration: 2
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    FAIL
# Reason:    Test case mismatch: args=(9, 2, 100000); expected=tuple((1382, 27)); actual=tuple((8860, 25))
# ============================================================

import numpy as np
from math import factorial
from itertools import islice


def permutations(n, start, size):
    p = np.arange(n, dtype=np.uint8)
    count = np.zeros(n, dtype=np.uint8)

    remainder = start
    for v in range(n - 1, 0, -1):
        q, remainder = divmod(remainder, factorial(v))
        count[v] = q
        if count[v] > 0:
            p[0:v+1] = np.roll(p[0:v+1], -count[v])

    assert(count[1] == 0)
    assert(size < 2 or (size % 2 == 0))

    if size < 2:
        yield p.tolist()
    else:
        rotation_swaps = [None] * n
        for i in range(1, n):
            r = np.arange(n, dtype=np.uint8)
            for v in range(1, i + 1):
                r[0:v+1] = np.roll(r[0:v+1], -1)
            
            non_identity_indices = np.where(r != np.arange(n, dtype=np.uint8))[0]
            swaps = tuple((dst, r[dst]) for dst in non_identity_indices)
            rotation_swaps[i] = swaps

        while True:
            yield p.tolist()
            
            p[[0, 1]] = p[[1, 0]]
            yield p.tolist()
            
            i = 2
            while count[i] >= i:
                count[i] = 0
                i += 1
            else:
                count[i] += 1
                t = p.copy()
                
                if rotation_swaps[i]:
                    dst_indices, src_indices = zip(*rotation_swaps[i])
                    p[np.array(dst_indices)] = t[np.array(src_indices)]


def alternating_flips_generator(n, start, size):
    maximum_flips = 0
    alternating_factor = 1
    for perm_list in islice(permutations(n, start, size), size):
        permutation = np.array(perm_list, dtype=np.uint8)
        first = permutation[0]
        if first:
            flips_count = 1
            while True:
                permutation[0:first + 1] = permutation[first::-1]
                first = permutation[0]
                if not first:
                    break
                flips_count += 1
            if maximum_flips < flips_count:
                maximum_flips = flips_count
            yield flips_count * alternating_factor
        else:
            yield 0
        alternating_factor = -alternating_factor
    yield maximum_flips


def task(n, start, size):
    alternating_flips = alternating_flips_generator(n, start, size)
    return sum(islice(alternating_flips, size)), next(alternating_flips)