# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=((('13', '17', '18', '21', '32'), ('07', '11', '13', '14', '28'), ('01', '05', '06', '08', '15', '16')),); expected=tuple((50.0, 50.0, 50.0)); actual=tuple((np.float64(25.0), np.float64(47.0), np.float64(72.0)))
# ============================================================

def task_func(T1, max_value=100):
    total_nums = sum(int(s) for sub_tuple in T1 for s in sub_tuple)
    random_nums_array = np.random.randint(0, max_value + 1, size=total_nums)
    percentiles = np.percentile(random_nums_array, [25, 50, 75])
    return percentiles[0], percentiles[1], percentiles[2]