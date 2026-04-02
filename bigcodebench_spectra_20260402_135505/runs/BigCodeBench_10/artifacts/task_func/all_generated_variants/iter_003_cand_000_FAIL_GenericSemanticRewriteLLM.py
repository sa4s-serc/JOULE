# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1',), ('2',), ('3',)),); expected=tuple((75.0, 75.0, 75)); actual=tuple((np.float64(50.0), np.float64(50.0), np.int64(50)))
# ============================================================

import numpy as np
import itertools
import random
import statistics


def task_func(T1, RANGE=100):
    total_nums = sum(int(s) for sub_tuple in T1 for s in sub_tuple)

    if total_nums == 0:
        raise statistics.StatisticsError

    random_nums_arr = np.random.randint(0, RANGE + 1, size=total_nums)

    mean = random_nums_arr.mean()
    median = np.median(random_nums_arr)

    counts = np.bincount(random_nums_arr)
    mode = np.argmax(counts)

    return mean, median, mode