import random

# We use a fixed seed so the data is identical across all isolated processes
random.seed(42)
TEST_LOGS = [random.randint(1, 1000) for _ in range(1500)]
TEST_BLACKLIST = [random.randint(1, 1000) for _ in range(300)]

# The main stress-test input
TEST_INPUTS = [
    (TEST_LOGS, TEST_BLACKLIST)
]

# A small, edge-case test to ensure the LLM doesn't hallucinate the math
TEST_CASES = [
    ( ([3, 1, 2, 1, 3], [2, 4]), 3 ) 
    # Explanation of case:
    # unique = [3, 1, 2]
    # safe = [3, 1]
    # sorted = [1, 3]
    # total = (0 * 1) + (1 * 3) = 3
]