# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def advancedDigitSum(s, t):
    s_sum = sum(map(ord, filter(str.isupper, s)))
    t_sum = sum(map(ord, filter(str.islower, t)))
    return (s_sum, t_sum)