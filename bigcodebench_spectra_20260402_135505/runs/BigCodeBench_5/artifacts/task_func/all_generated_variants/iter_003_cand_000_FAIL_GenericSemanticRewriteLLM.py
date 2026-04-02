# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(['a'],); expected=dict({'a': 4.5}); actual=dict({'a': 45.5})
# ============================================================

import random
import math
import statistics

import random as _rng_seed; _rng_seed.seed(42)


def task_func(LETTERS=[chr(i) for i in range(97, 123)]):
    random_dict = {k: [random.randint(0, 100) for _ in range(random.randint(1, 10))] for k in LETTERS}
    sd_dict = {
        k: statistics.pstdev(v)
        for k, v in random_dict.items()
    }
    return sd_dict