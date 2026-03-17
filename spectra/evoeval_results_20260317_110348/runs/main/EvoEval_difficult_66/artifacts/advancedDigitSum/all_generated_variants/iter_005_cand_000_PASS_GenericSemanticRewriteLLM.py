# ============================================================
# Iteration: 5
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

import functools

@functools.lru_cache(maxsize=None)
def advancedDigitSum(s, t):
    _ord = ord
    _isupper = str.isupper
    _islower = str.islower

    s_sum = sum(_ord(c) for c in s if _isupper(c))
    t_sum = sum(_ord(c) for c in t if _islower(c))
    return (s_sum, t_sum)