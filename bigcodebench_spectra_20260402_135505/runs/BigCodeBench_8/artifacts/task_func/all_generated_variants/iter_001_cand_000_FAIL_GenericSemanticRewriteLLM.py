# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1', '2', '3'),),); expected=dict({81: 1, 14: 1, 3: 1, 94: 1, 35: 1, 31: 1}); actual=Counter(Counter({58: 2, 18: 1, 98: 1, 22: 1, 90: 1}))
# ============================================================

from collections import Counter
from random import randint

import random as _rng_seed; _rng_seed.seed(42)


def task_func(T1, RANGE=100):
    total_nums = sum(int(s) for inner_tuple in T1 for s in inner_tuple)
    counts = Counter(randint(0, RANGE) for _ in range(total_nums))
    return counts