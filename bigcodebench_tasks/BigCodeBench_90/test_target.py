# Auto-generated test file for BigCodeBench/90
# Entry point: task_func  |  Libraries: ['math', 'numpy']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    (({'Latitude': [14, 1, 7, 10], 'Longitude': [25, 22, 8, 15]}, [10, 15], 1), [[10, 15]]),
    (({'Latitude': [14, 1, 7, 10], 'Longitude': [25, 22, 8, 15]}, [10, 15], 2), [[10, 15], [7, 8]]),
    (({'Latitude': [14, 1, 7, 10], 'Longitude': [25, 22, 8, 15]}, [10, 15], 100), [[10, 15], [7, 8], [14, 25], [1, 22]]),
    (({'Latitude': [14, 1, 7, 10], 'Longitude': [25, 22, 8, 15]}, [10, 15], 0), []),
]
