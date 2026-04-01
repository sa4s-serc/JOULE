# Auto-generated test file for BigCodeBench/0
# Entry point: task_func  |  Libraries: ['random', 'itertools']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    (([1, 2, 3],), 2.8333333333333335),
    ((), 1.0),
    (([],), 0.0),
    (([2, 2, 2],), 0.0),
    (([1, 2, 3, 4, 5, 6, 7, 8, 9, 10],), 33.003481040564374),
    (([-10, 10, -5],), 27.5),
    (([-3, -2, -1],), 2.6666666666666665),
    (([1, 2, 4],), 3.6666666666666665),
    (([5],), 0.0),
]
