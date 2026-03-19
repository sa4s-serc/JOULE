# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def advancedDigitSum(s, t):
    s_sum = sum(ord(c) for c in s if 65 <= ord(c) <= 90)
    t_sum = sum(ord(c) for c in t if 97 <= ord(c) <= 122)
    return (s_sum, t_sum)