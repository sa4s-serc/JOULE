# ============================================================
# Iteration: 4
# Operator:  VectorizationDelegate[loop→numpy]
# Status:    FAIL
# Reason:    Exception: negative dimensions are not allowed
# ============================================================

import numpy as np
from functools import lru_cache

@lru_cache(maxsize=None)
def _get_distinct_char_count(s: str) -> int:
    return len(set(s))

def count_distinct_characters_substrings(string: str, length: int) -> dict:
    n = len(string)
    if length > n:
        return {}
    
    if length == 0:
        return {"": 0} if n >= 0 else {}

    char_codes = np.array([ord(c) for c in string], dtype=np.int32)
    
    num_windows = n - length + 1
    
    # Use as_strided to create a view of all sliding windows of character codes
    # This avoids creating many intermediate arrays for each window
    windows = np.lib.stride_tricks.as_strided(
        char_codes,
        shape=(num_windows, length),
        strides=(char_codes.itemsize, char_codes.itemsize)
    )
    
    # Calculate distinct character counts for each window
    # np.unique is applied to each row (window)
    # This part still involves an implicit Python loop or a C-level loop for each unique call
    # but it operates on NumPy arrays for efficiency.
    counts = np.array([np.unique(window).size for window in windows])
    
    # Generate the actual string substrings (keys for the dictionary)
    # String slicing and dictionary creation are not directly vectorized by NumPy
    substrings = [string[i : i + length] for i in range(num_windows)]
    
    # Combine substrings and counts into the result dictionary
    return dict(zip(substrings, counts))