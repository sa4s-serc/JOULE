# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(['x', 'y', 'z'],); expected=dict({'x': 45.5, 'y': 29.4659125092029, 'z': 25.575354649194974}); actual=NoneType(None)
# ============================================================

import random
import math

import random as _rng_seed; _rng_seed.seed(42)


def task_func(LETTERS=[chr(i) for i in range(97, 123)]):
    random_dict = {k: [random.randint(0, 100) for _ in range(random.randint(1, 10))] for k in LETTERS}
    sd_dict = {
        k: (
            0.0 if (n := len(v)) == 1 else
            math.sqrt(
                sum((x - (mean_v := (sum_v := sum(v)) / n)) ** 2 for x in v) / n
            )
        )
        for k, v in random_dict.items()
    }
    return sd_dict