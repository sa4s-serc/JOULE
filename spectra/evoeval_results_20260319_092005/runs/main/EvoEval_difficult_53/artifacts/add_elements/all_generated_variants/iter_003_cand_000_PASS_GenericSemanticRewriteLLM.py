# ============================================================
# Iteration: 3
# Operator:  GenericSemanticRewriteLLM
# Status:    PASS
# ============================================================

def add_elements(list1: list, list2: list, index: int):
    len1 = len(list1)
    len2 = len(list2)
    if (index >= -len1 and index < len1) and \
       (index >= -len2 and index < len2):
        result = list1[index] + list2[index]
        return (result, False)
    else:
        return (None, True)