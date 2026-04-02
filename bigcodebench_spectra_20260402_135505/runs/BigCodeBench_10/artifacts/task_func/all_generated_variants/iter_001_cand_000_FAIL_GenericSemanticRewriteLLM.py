# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1',), ('2',), ('3',)),); expected=tuple((75.0, 75.0, 75)); actual=tuple((50.0, 50.0, 50))
# ============================================================

import numpy as np
import itertools
import random
import statistics

import random as _rng_seed; _rng_seed.seed(42)


def task_func(T1, RANGE=100):
    if len(T1) <= 0:
        raise statistics.StatisticsError
    total_nums = sum(map(int, itertools.chain.from_iterable(T1)))
    if total_nums == 0:
        raise statistics.StatisticsError
    random_nums = [random.randint(0, RANGE) for _ in range(total_nums)]
    mean = np.mean(random_nums)
    median = np.median(random_nums)
    mode = statistics.mode(random_nums)
    return mean, median, mode