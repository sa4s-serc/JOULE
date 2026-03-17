# ============================================================
# Iteration: 6
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

from functools import lru_cache

@lru_cache(maxsize=256)
def _cached_ord(c):
    return ord(c)

@lru_cache(maxsize=256)
def _cached_isupper(c):
    return c.isupper()

@lru_cache(maxsize=256)
def _cached_islower(c):
    return c.islower()

def advancedDigitSum(s, t):
    s_sum = sum(_cached_ord(c) for c in s if _cached_isupper(c))
    t_sum = sum(_cached_ord(c) for c in t if _cached_islower(c))
    return (s_sum, t_sum)