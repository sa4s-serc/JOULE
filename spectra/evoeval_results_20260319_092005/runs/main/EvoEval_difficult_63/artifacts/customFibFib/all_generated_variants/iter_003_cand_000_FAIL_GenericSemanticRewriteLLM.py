# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(5, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], 1000)
# ============================================================

def customFibFib(n: int, startSequence: list, p: int):
    if n == 0:
        return startSequence[0]
    if n == 1:
        return startSequence[1]
    if n == 2:
        return startSequence[2]

    f0, f1, f2 = startSequence[0], startSequence[1], startSequence[2]

    for _ in range(3, n + 1):
        f_next = f0 + f1 + f2
        if f_next > p:
            return 'Limit Exceeded'
        f0, f1, f2 = f1, f2, f_next

    return f2