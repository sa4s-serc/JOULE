# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=([101, 102, 103], [104, 105, 106], -1)
# ============================================================

def add_elements(list1: list, list2: list, index: int):
    if index < 0 or index >= len(list1) or index >= len(list2):
        return (None, True)
    result = list1[index] + list2[index]
    return (result, False)