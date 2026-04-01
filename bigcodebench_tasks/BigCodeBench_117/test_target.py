# Auto-generated test file for BigCodeBench/117
# Entry point: task_func  |  Libraries: ['pandas', 'numpy', 'random']

import random
random.seed(42)
try:
    import numpy as np
    np.random.seed(42)
except ImportError:
    pass

TEST_CASES = [
    ((10,), {'Name': ['John', 'Sara', 'Mike', 'John', 'Nick', 'John', 'John', 'Mike', 'Nick', 'Nick'], 'Age': [21, 20, 22, 19, 20, 22, 20, 22, 21, 19], 'Gender': ['Male', 'Male', 'Male', 'Male', 'Female', 'Male', 'Male', 'Male', 'Male', 'Female'], 'Score': [78, 57, 70, 68, 60, 85, 71, 51, 79, 70]}),
    ((1,), {'Name': ['John'], 'Age': [18], 'Gender': ['Male'], 'Score': [78]}),
    ((2,), {'Name': ['Alex', 'Bob'], 'Age': [18, 17], 'Gender': ['Non-Binary', 'Non-Binary'], 'Score': [78, 57]}),
    ((5,), {'Name': ['John', 'Sara', 'Mike', 'John', 'Nick'], 'Age': [18, 17, 19, 16, 17], 'Gender': ['Male', 'Male', 'Male', 'Male', 'Female'], 'Score': [78, 57, 70, 68, 60]}),
    ((3,), {'Name': ['John', 'John', 'Sara'], 'Age': [20, 19, 16], 'Gender': ['Female', 'Female', 'Male'], 'Score': [52, 84, 69]}),
]
