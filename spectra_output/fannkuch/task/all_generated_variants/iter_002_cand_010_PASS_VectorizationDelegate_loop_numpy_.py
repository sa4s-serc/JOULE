# ============================================================
# Iteration: 2
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    PASS
# ============================================================

import numpy as np
from math import factorial
from itertools import islice


def permutations(n, start, size):
    p = np.arange(n, dtype=np.uint8)
    count = np.zeros(n, dtype=np.uint8)

    remainder = start
    for v in range(n - 1, 0, -1):
        count[v], remainder = divmod(remainder, factorial(v))
        for _ in range(count[v]):
            p[:v+1] = np.concatenate((p[1:v+1], p[0:1]))
        if remainder == 0:
            break

    assert(count[1] == 0)
    assert(size < 2 or (size % 2 == 0))

    if size < 2:
        yield p.copy()
    else:
        rotation_swaps = [None] * n
        for i in range(1, n):
            r_np = np.arange(n, dtype=np.uint8)
            for v_np in range(1, i + 1):
                r_np[:v_np+1] = np.concatenate((r_np[1:v_np+1], r_np[0:1]))
            
            mask = (np.arange(n) != r_np)
            if np.any(mask):
                swaps_np = np.column_stack((np.arange(n)[mask], r_np[mask]))
                rotation_swaps[i] = tuple(map(tuple, swaps_np))
            else:
                rotation_swaps[i] = ()

        while True:
            yield p.copy()
            p[0], p[1] = p[1], p[0]
            yield p.copy()
            i = 2
            while count[i] >= i:
                count[i] = 0
                i += 1
            else:
                count[i] += 1
                t = p.copy()
                current_swaps = rotation_swaps[i]
                if current_swaps:
                    dst_indices, src_indices = zip(*current_swaps)
                    p[list(dst_indices)] = t[list(src_indices)]


def alternating_flips_generator(n, start, size):
    maximum_flips = 0
    alternating_factor = 1
    for permutation in islice(permutations(n, start, size), size):
        first = permutation[0]
        if first:
            flips_count = 1
            while True:
                permutation[:first + 1] = permutation[first::-1]
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