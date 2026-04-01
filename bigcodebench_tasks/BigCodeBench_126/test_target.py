# Auto-generated test file for BigCodeBench/126
# Entry point: task_func  |  Libraries: ['statistics', 'pandas', 'numpy', 'random']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    ((['Dog', 'Cat'],), {'Animal': ['Dog', 'Cat'], 'Mean': [42.0, 44.4], 'Median': [30.5, 41.5], 'Mode': [95, 12], 'Standard Deviation': [33.250563904992646, 34.1970758983864]}),
    ((), {'Animal': ['Lion', 'Elephant', 'Tiger', 'Giraffe', 'Panda'], 'Mean': [42.0, 44.4, 61.1, 51.8, 35.8], 'Median': [30.5, 41.5, 71.0, 54.5, 32.0], 'Mode': [95, 12, 30, 54, 44], 'Standard Deviation': [33.250563904992646, 34.1970758983864, 28.76264939118092, 29.208902752414375, 24.595934623429134]}),
]
