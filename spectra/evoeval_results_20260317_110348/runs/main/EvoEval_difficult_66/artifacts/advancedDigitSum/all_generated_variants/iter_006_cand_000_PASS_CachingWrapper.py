# ============================================================
# Iteration: 6
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

from functools import lru_cache

@lru_cache(maxsize=None)
def advancedDigitSum(s, t):
    s_sum = sum(map(ord, filter(str.isupper, s)))
    t_sum = sum(map(ord, filter(str.islower, t)))
    return (s_sum, t_sum)