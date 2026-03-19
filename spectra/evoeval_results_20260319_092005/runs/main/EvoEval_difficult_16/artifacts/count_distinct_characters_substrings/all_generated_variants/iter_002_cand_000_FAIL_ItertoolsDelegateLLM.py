# ============================================================
# Iteration: 2
# Operator:  ItertoolsDelegateLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=('', 0)
# ============================================================

import itertools

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    if length > len(string):
        return {}
    else:
        iterables = [itertools.islice(string, i, None) for i in range(length)]
        substrings = (''.join(t) for t in zip(*iterables))
        
        result = {}
        for substring in substrings:
            result[substring] = len(set(substring))
        return result