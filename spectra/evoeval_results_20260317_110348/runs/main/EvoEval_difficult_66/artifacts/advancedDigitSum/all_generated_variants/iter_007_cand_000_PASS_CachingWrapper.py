# ============================================================
# Iteration: 7
# Operator:  CachingWrapper
# Status:    PASS
# ============================================================

from functools import lru_cache

@lru_cache(maxsize=None)
def _cached_isupper(char):
    return char.isupper()

@lru_cache(maxsize=None)
def _cached_islower(char):
    return char.islower()

@lru_cache(maxsize=None)
def _cached_ord(char):
    return ord(char)

def advancedDigitSum(s, t):
    s_sum = sum(map(_cached_ord, filter(_cached_isupper, s)))
    t_sum = sum(map(_cached_ord, filter(_cached_islower, t)))
    return (s_sum, t_sum)