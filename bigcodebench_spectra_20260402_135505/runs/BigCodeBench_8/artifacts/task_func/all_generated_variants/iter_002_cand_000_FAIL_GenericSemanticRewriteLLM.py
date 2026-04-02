# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1', '2', '3'),),); expected=dict({81: 1, 14: 1, 3: 1, 94: 1, 35: 1, 31: 1}); actual=Counter(Counter({95: 1, 54: 1, 70: 1, 18: 1, 36: 1, 65: 1}))
# ============================================================

from collections import Counter
import itertools
from random import randint

import random as _rng_seed; _rng_seed.seed(42)


def task_func(T1, RANGE=100):
    integer_stream = itertools.chain.from_iterable(map(int, inner_tuple) for inner_tuple in T1)
    total_nums = sum(integer_stream)

    random_nums = [randint(0, RANGE) for _ in range(total_nums)]
    counts = Counter(random_nums)

    return counts