# Auto-generated test file for BigCodeBench/141
# Entry point: task_func  |  Libraries: ['statistics', 'pandas', 'numpy']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    ((10,), ({'A': [52, 83, 24, 30, 33, 91, 15, 55, 73, 14], 'B': [93, 87, 3, 38, 76, 59, 62, 64, 39, 9], 'C': [15, 75, 22, 2, 58, 42, 62, 3, 18, 90], 'D': [72, 75, 53, 64, 22, 92, 47, 51, 4, 53], 'E': [61, 88, 2, 60, 89, 60, 62, 7, 89, 2], 'F': [21, 100, 88, 21, 49, 80, 51, 21, 60, 84]}, {'A': {'mean': 47, 'median': 42.5}, 'B': {'mean': 53, 'median': 60.5}, 'C': {'mean': 38.7, 'median': 32.0}, 'D': {'mean': 53.3, 'median': 53.0}, 'E': {'mean': 52, 'median': 60.5}, 'F': {'mean': 57.5, 'median': 55.5}})),
]
