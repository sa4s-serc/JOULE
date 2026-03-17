# ============================================================
# Iteration: 4
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def advancedDigitSum(s, t):
    s_sum = sum(ord(c) for c in s if c.isupper())
    t_sum = sum(ord(c) for c in t if c.islower())
    return (s_sum, t_sum)