# ============================================================
# Iteration: 3
# Operator:  ItertoolsDelegateLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=('', 0)
# ============================================================

import itertools

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    if length > len(string):
        return {}
    
    result = {}
    
    iterators = [itertools.islice(string, i, None) for i in range(length)]
    
    for window_tuple in zip(*iterators):
        substring = "".join(window_tuple)
        result[substring] = len(set(substring))
        
    return result