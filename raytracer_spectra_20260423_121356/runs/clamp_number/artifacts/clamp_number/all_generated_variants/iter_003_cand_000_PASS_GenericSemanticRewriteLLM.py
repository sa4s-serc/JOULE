# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def clamp_number(number: float, minimum: float, maximum: float) -> float:
    if number > maximum:
        return maximum
    elif number < minimum:
        return minimum
    else:
        return number