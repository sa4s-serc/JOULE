# Auto-generated test file for BigCodeBench/87
# Entry point: task_func  |  Libraries: ['pandas', 'random']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    ((['iPhone', 'iPad', 'Macbook', 'Airpods', 'Apple Watch'], [1, 2, 3, 4, 5], [0.05, 0.1, 0.2, 0.3, 0.35]), {'Product': ['Apple Watch', 'iPhone', 'Macbook', 'Airpods', 'iPad'], 'Rating': [5, 4, 3, 3, 1]}),
    ((['iPhone', 'iPad', 'Macbook', 'Airpods', 'Apple Watch'], [1, 2, 3, 4, 5], [0.05, 0.1, 0.2, 0.3, 0.35], 42), {'Product': ['Apple Watch', 'iPhone', 'Macbook', 'Airpods', 'iPad'], 'Rating': [5, 4, 3, 3, 1]}),
    ((['iPhone', 'iPad', 'Macbook', 'Airpods', 'Apple Watch'], [1, 2, 3, 4, 5], [0.05, 0.1, 0.2, 0.3, 0.35], 24), {'Product': ['iPhone', 'iPad', 'Airpods', 'Macbook', 'Apple Watch'], 'Rating': [5, 5, 5, 3, 3]}),
]
