# ============================================================
# Iteration: 1
# Operator:  GenericSemanticRewriteLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=([101, 102, 103], [104, 105, 106], -1)
# ============================================================

def add_elements(list1: list, list2: list, index: int):
    if 0 <= index < len(list1) and 0 <= index < len(list2):
        return (list1[index] + list2[index], False)
    return (None, True)