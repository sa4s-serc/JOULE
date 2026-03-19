# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def below_above_threshold(l: list, t1: int, t2: int, s: str):
    if s == 'below':
        try:
            return next(i for i, num in enumerate(l) if num >= t1)
        except StopIteration:
            return True
    elif s == 'above':
        try:
            return next(i for i, num in enumerate(l) if num <= t2)
        except StopIteration:
            return True
    else:
        return -1