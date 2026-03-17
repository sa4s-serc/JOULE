# ============================================================
# Iteration: 1
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

import functools

@functools.lru_cache(maxsize=None)
def _cached_isupper(c):
    return c.isupper()

@functools.lru_cache(maxsize=None)
def _cached_islower(c):
    return c.islower()

@functools.lru_cache(maxsize=None)
def _cached_ord(c):
    return ord(c)

def advancedDigitSum(s, t):
    s_sum = sum(_cached_ord(c) for c in s if _cached_isupper(c))
    t_sum = sum(_cached_ord(c) for c in t if _cached_islower(c))
    return (s_sum, t_sum)