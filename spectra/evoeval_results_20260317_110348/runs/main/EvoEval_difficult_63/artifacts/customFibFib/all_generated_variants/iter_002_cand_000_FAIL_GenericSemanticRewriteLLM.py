# ============================================================
# Iteration: 2
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(5, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], 1000)
# ============================================================

def customFibFib(n: int, startSequence: list, p: int):
    if n < 3:
        return startSequence[n]

    a, b, c = startSequence[0], startSequence[1], startSequence[2]

    for _ in range(3, n + 1):
        next_val = a + b + c
        if next_val > p:
            return 'Limit Exceeded'
        a, b, c = b, c, next_val

    return c