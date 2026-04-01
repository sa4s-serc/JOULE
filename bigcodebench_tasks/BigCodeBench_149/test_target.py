# Auto-generated test file for BigCodeBench/149
# Entry point: task_func  |  Libraries: ['pandas', 'numpy']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    ((['hello'],), {'Element': ['hello'], 'Count': [5]}),
    ((['a', 'bc', 'def'],), {'Element': ['a', 'bc', 'def'], 'Count': [1, 2, 3]}),
    ((['zzz', 'zzz'],), {'Element': ['zzz', 'zzz'], 'Count': [3, 3]}),
    ((['hello world', 'open ai'],), {'Element': ['hello world', 'open ai'], 'Count': [11, 7]}),
    ((['hello', 'world'],), {'Index': [0, 1], 'Element': ['hello', 'world'], 'Count': [5, 5]}),
]
