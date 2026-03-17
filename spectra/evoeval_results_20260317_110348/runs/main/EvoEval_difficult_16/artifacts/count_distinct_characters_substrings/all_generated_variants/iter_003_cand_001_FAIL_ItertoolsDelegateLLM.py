# ============================================================
# Iteration: 3
# Operator:  ItertoolsDelegateLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=('xyzXYZabc', 0)
# ============================================================

import itertools

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    if length > len(string):
        return {}

    result = {}
    
    string_iter = iter(string)
    
    current_window = list(itertools.islice(string_iter, length))
    
    substring = "".join(current_window)
    result[substring] = len(set(substring))

    for char in string_iter:
        current_window = current_window[1:] + [char]
        substring = "".join(current_window)
        result[substring] = len(set(substring))
            
    return result