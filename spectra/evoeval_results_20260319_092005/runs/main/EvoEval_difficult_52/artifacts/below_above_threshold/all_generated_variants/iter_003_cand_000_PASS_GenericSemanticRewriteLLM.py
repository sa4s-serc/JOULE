# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def below_above_threshold(l: list, t1: int, t2: int, s: str):
    if s == 'below':
        first_violation_idx = next((i for i, num in enumerate(l) if num >= t1), None)
        return first_violation_idx if first_violation_idx is not None else True
    elif s == 'above':
        first_violation_idx = next((i for i, num in enumerate(l) if num <= t2), None)
        return first_violation_idx if first_violation_idx is not None else True
    else:
        return -1