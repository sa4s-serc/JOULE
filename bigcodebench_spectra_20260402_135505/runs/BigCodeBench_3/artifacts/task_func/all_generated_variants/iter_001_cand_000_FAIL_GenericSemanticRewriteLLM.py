# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],); expected=dict({'a': 48.5, 'b': 36.6, 'c': 30.88888888888889, 'd': 56.9, 'e': 41.9, 'f': 28.833333333333332, 'g': 43.7, 'h': 49.4, 'i': 20.5, 'j': 47.42857142857143, 'k': 7...); actual=dict({'a': np.float64(52.285714285714285), 'b': np.float64(54.2), 'c': np.float64(49.666666666666664), 'd': np.float64(55.5), 'e': np.float64(51.888888888888886),...)
# ============================================================

import random
import numpy as np

import random as _rng_seed; _rng_seed.seed(42)


def task_func(LETTERS):
    random_lists = {k: [random.randint(0, 100) for _ in range(random.randint(1, 10))] for k in LETTERS}
    mean_dict = {k: sum(v) / len(v) for k, v in random_lists.items()}
    return mean_dict