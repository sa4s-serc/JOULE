# ============================================================
# Iteration: 2
# Operator:  LoopGlobalToLocalHoisting
# Status:    PASS
# ============================================================

from functools import lru_cache

@lru_cache(maxsize=None)
def _get_distinct_char_count(s: str) -> int:
    return len(set(s))

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    _local_len = len
    _local_range = range
    if length > len(string):
        return {}
    else:
        result = {}
        for i in range(len(string) - length + 1):
            substring = string[i:i + length]
            result[substring] = _get_distinct_char_count(substring)
        return result