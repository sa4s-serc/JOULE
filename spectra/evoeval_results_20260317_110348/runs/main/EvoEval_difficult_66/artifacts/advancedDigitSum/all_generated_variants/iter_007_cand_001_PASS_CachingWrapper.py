# ============================================================
# Iteration: 7
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

import functools

@functools.lru_cache(maxsize=128)
def _cached_sum_upper(s_str):
    return sum(ord(c) for c in s_str if c.isupper())

@functools.lru_cache(maxsize=128)
def _cached_sum_lower(t_str):
    return sum(ord(c) for c in t_str if c.islower())

def advancedDigitSum(s, t):
    s_sum = _cached_sum_upper(s)
    t_sum = _cached_sum_lower(t)
    return (s_sum, t_sum)