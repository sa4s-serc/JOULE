# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1', '2'), ('3', '4')),); expected=dict({28: 1, 17: 1, 94: 2, 13: 1, 86: 1, 69: 1, 11: 1, 75: 1, 54: 1}); actual=Counter(Counter({94: 2, 81: 1, 14: 1, 3: 1, 35: 1, 31: 1, 28: 1, 17: 1, 13: 1}))
# ============================================================

from collections import Counter
import itertools
from random import randint

import random as _rng_seed; _rng_seed.seed(42)


def task_func(T1, RANGE=100):
    total_nums = sum(itertools.chain.from_iterable(map(lambda x: map(int, x), T1)))
    counts = Counter(randint(0, RANGE) for _ in range(total_nums))
    return counts