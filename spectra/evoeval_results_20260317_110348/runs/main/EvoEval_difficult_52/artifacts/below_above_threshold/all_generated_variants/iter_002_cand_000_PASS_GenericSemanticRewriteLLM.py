# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def below_above_threshold(l: list, t1: int, t2: int, s: str):
    if s == 'below':
        return next((i for i, num in enumerate(l) if num >= t1), True)
    elif s == 'above':
        return next((i for i, num in enumerate(l) if num <= t2), True)
    else:
        return -1