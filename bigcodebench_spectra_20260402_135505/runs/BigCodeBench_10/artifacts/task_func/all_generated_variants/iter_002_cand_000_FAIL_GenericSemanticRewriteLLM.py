# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('1',), ('2',), ('3',)),); expected=tuple((75.0, 75.0, 75)); actual=tuple((np.float64(50.0), np.float64(50.0), np.int64(50)))
# ============================================================

import numpy as np
import statistics


def task_func(T1, RANGE=100):
    if len(T1) <= 0:
        raise statistics.StatisticsError

    total_nums = sum(int(s) for t in T1 for s in t)

    if total_nums == 0:
        raise statistics.StatisticsError

    random_nums_array = np.random.randint(0, RANGE + 1, size=total_nums)

    mean = np.mean(random_nums_array)
    median = np.median(random_nums_array)

    counts = np.bincount(random_nums_array)
    mode = np.argmax(counts)

    return mean, median, mode