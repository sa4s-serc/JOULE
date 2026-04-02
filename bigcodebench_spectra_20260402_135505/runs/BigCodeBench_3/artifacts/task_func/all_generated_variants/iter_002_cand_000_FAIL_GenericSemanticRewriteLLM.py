# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'],); expected=dict({'a': 48.5, 'b': 36.6, 'c': 30.88888888888889, 'd': 56.9, 'e': 41.9, 'f': 28.833333333333332, 'g': 43.7, 'h': 49.4, 'i': 20.5, 'j': 47.42857142857143, 'k': 7...); actual=dict({'a': np.float64(55.714285714285715), 'b': np.float64(54.285714285714285), 'c': np.float64(31.0), 'd': np.float64(54.6), 'e': np.float64(90.0), 'f': np.float...)
# ============================================================

import random
import numpy as np

import random as _rng_seed; _rng_seed.seed(42)


def task_func(LETTERS):
    return {k: (lambda num_elements: sum(random.randint(0, 100) for _ in range(num_elements)) / num_elements)(random.randint(1, 10)) for k in LETTERS}