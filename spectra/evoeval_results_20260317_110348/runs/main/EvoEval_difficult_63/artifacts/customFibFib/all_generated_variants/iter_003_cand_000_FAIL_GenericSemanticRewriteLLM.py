# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=(5, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19], 1000)
# ============================================================

def customFibFib(n: int, startSequence: list, p: int):
    if n < 3:
        return startSequence[n]

    f_n_minus_3 = startSequence[0]
    f_n_minus_2 = startSequence[1]
    f_n_minus_1 = startSequence[2]

    for _ in range(3, n + 1):
        current_val = f_n_minus_3 + f_n_minus_2 + f_n_minus_1
        if current_val > p:
            return 'Limit Exceeded'
        f_n_minus_3, f_n_minus_2, f_n_minus_1 = f_n_minus_2, f_n_minus_1, current_val
    
    return f_n_minus_1