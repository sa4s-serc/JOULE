# ============================================================
# Iteration: 1
# Operator:  ItertoolsDelegateLLM
# Status:    FAIL
# Reason:    Test case mismatch: args=('xyzXYZabc', -1)
# ============================================================

import itertools

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    if length > len(string):
        return {}
    
    if length == 0:
        # As per problem description "positive integer 'length'", so length >= 1.
        # If length could be 0, the original code would produce {'': 0} if len(string) >= 0.
        # The itertools approach below would yield an empty zip object if length is 0,
        # resulting in an empty dictionary, which is different from {'': 0}.
        # Given "positive integer 'length'", this branch should not be hit.
        return {'': 0} if len(string) >= 0 else {}

    iters = [itertools.islice(string, i, None) for i in range(length)]
    
    result = {}
    for window_chars in zip(*iters):
        substring = "".join(window_chars)
        result[substring] = len(set(substring))
    return result