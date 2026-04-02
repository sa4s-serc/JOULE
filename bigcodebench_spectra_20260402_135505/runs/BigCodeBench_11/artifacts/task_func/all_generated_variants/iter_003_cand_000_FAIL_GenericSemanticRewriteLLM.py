# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('13', '17', '18', '21', '32'), ('07', '11', '13', '14', '28'), ('01', '05', '06', '08', '15', '16')),); expected=tuple((50.0, 50.0, 50.0)); actual=tuple((np.float64(25.0), np.float64(49.0), np.float64(74.0)))
# ============================================================

def task_func(T1, max_value=100):
    total_nums = sum(int(s) for sub_tup in T1 for s in sub_tup)

    random_nums = np.random.randint(0, max_value + 1, size=total_nums)

    p25, p50, p75 = np.percentile(random_nums, [25, 50, 75])

    return p25, p50, p75