# ============================================================
# Iteration: 4
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
        count[v], remainder = divmod(remainder, factorial(v))
        p[:v+1] = np.roll(p[:v+1], -count[v])
        if remainder == 0:
            break

    assert(count[1] == 0)
    assert(size < 2 or (size % 2 == 0))

    if size < 2:
        yield bytearray(p)
    else:
        rotation_swaps = [None] * n
        for i in range(1, n):
            r = np.arange(n, dtype=np.uint8)
            for v in range(1, i + 1):
                r[:v+1] = np.roll(r[:v+1], -1)
            swaps = []
            for dst, src in enumerate(r):
                if dst != src:
                    swaps.append((dst, src))
            rotation_swaps[i] = tuple(swaps)

        while True:
            yield bytearray(p)
            p[[0,1]] = p[[1,0]]
            yield bytearray(p)
            i = 2
            while count[i] >= i:
                count[i] = 0
                i += 1
            else:
                count[i] += 1
                t = p.copy()
                if rotation_swaps[i]:
                    dests, srcs = np.array(rotation_swaps[i]).T
                    p[dests] = t[srcs]


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