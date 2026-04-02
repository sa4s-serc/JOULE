# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('10',), ('10', '10', '10')),); expected=tuple((30.0, 30.0, 30.0)); actual=tuple((np.float64(50.0), np.float64(50.0), np.float64(50.0)))
# ============================================================

import numpy as np

def task_func(T1, max_value=100):
    total_nums = sum(int(s) for sub_tuple in T1 for s in sub_tuple)
    random_nums = np.random.randint(0, max_value + 1, size=total_nums)
    p25, p50, p75 = np.percentile(random_nums, [25, 50, 75])
    return p25, p50, p75