# ============================================================
# Iteration: 3
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

import functools

@functools.lru_cache(maxsize=None)
def advancedDigitSum(s, t):
    s_sum = sum(map(ord, filter(str.isupper, s)))
    t_sum = sum(map(ord, filter(str.islower, t)))
    return (s_sum, t_sum)