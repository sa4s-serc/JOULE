# Auto-generated test file for BigCodeBench/23
# Entry point: task_func  |  Libraries: ['numpy', 'itertools']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    (([0, 0.5, 2, 3, 4], [10, 11, 12, 13, 14]), 0.5),
    (([0, 0.4, 0.6, 3, 4, 5], [10, 11, 12]), 0.4),
    (([0, 0.51], [10, 11, 12, 13]), 0.51),
    (([], [10, 11, 12, 13]), 10),
    (([-10, -5, 0, 5, 10], [-1, 0, 1]), 0),
]
