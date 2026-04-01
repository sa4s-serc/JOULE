# Auto-generated test file for BigCodeBench/33
# Entry point: task_func  |  Libraries: ['numpy', 'functools']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    (([('Fruits', 5), ('Vegetables', 9), ('Dairy', -1), ('Bakery', -2), ('Meat', 4)],), [360]),
    (([('A', 2), ('B', 3), ('C', 4)],), [24]),
    (([('A', -2), ('B', -3), ('C', -4)],), [-24]),
    (([('A', 10)],), [10]),
    (([('A', 0), ('B', 5), ('C', 10)],), [0]),
]
