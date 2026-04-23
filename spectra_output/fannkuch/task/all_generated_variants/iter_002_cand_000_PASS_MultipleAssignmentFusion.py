# ============================================================
# Iteration: 2
# Operator:  MultipleAssignmentFusion
# Status:    PASS
# ============================================================

from math import factorial
from itertools import islice

def permutations(n, start, size):
    _local_enumerate = enumerate
    _local_range = range
    p = bytearray(range(n))
    count = bytearray(n)
    remainder = start
    for v in _local_range(n - 1, 0, -1):
        (count[v], remainder) = divmod(remainder, factorial(v))
        for _ in _local_range(count[v]):
            (p[:v], p[v]) = (p[1:v + 1], p[0])
    assert count[1] == 0
    assert size < 2 or size % 2 == 0
    if size < 2:
        yield p[:]
    else:
        rotation_swaps = [None] * n
        for i in range(1, n):
            r = list(range(n))
            for v in range(1, i + 1):
                (r[:v], r[v]) = (r[1:v + 1], r[0])
            swaps = []
            for (dst, src) in enumerate(r):
                if dst != src:
                    swaps.append((dst, src))
            rotation_swaps[i] = tuple(swaps)
        while True:
            yield p[:]
            (p[0], p[1]) = (p[1], p[0])
            yield p[:]
            i = 2
            while count[i] >= i:
                count[i] = 0
                i += 1
            else:
                count[i] += 1
                t = p[:]
                for (dst, src) in rotation_swaps[i]:
                    p[dst] = t[src]

def alternating_flips_generator(n, start, size):
    (maximum_flips, alternating_factor) = (0, 1)
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
            yield (flips_count * alternating_factor)
        else:
            yield 0
        alternating_factor = -alternating_factor
    yield maximum_flips

def task(n, start, size):
    alternating_flips = alternating_flips_generator(n, start, size)
    return (sum(islice(alternating_flips, size)), next(alternating_flips))