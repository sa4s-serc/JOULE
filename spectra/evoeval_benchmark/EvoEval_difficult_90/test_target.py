"""
SPECTRA test data for EvoEval/90.

Converted from the EvoEval benchmark test suite.
"""

_RAW_TEST_INPUTS = [
        ([-1, -2, -3, -4, -5]),  # Test case 1
        ([1, 1]),  # Test case 2
        ([]),  # Test case 3
        ([5, 1, 4, 3, 2]),  # Test case 4
        ([1, 2, 3, 4, 5]),  # Test case 5
        ([0]),  # Test case 6
        ([1]),  # Test case 7
        ([0, 0, 0, 0, 0]),  # Test case 8
        ([1, 1, 1, 1, 1]),  # Test case 9
        ([-1, -1, -1, -1, -1]),  # Test case 10
        ([1, 2]),  # Test case 11
        ([2, 1]),  # Test case 12
        ([-1, 1]),  # Test case 13
        ([1, -1]),  # Test case 14
        ([0, -1]),  # Test case 15
        ([-1, 0]),  # Test case 16
        ([1, 0]),  # Test case 17
        ([0, 1]),  # Test case 18
        ([-1, -2, -3, -3, -3]),  # Test case 19
        ([5, 5, 5, 4, 4]),  # Test case 20
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),  # Test case 21
        ([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]),  # Test case 22
        ([0, -1, -2, -3, -4, -5]),  # Test case 23
        ([-5, -4, -3, -2, -1, 0]),  # Test case 24
        ([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2]),  # Test case 25
        ([-1, 0, 0, 0, 0, 0, 1]),  # Test case 26
        ([5, 5, 5, 5, 5, -5, -5, -5, -5, -5]),  # Test case 27
        ([-1, -2, -2, -1, 0, 0, 1, 2, 2, 1]),  # Test case 28
        ([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]),  # Test case 29
        ([1000, 900, 800, 700, 600, 500, 400, 300, 200, 100]),  # Test case 30
        ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),  # Test case 31
        ([1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]),  # Test case 32
        ([-1, -2, -3, -1, -2, -3, -1, -2, -3, -1, -2, -3]),  # Test case 33
        ([999, -999, 1000, -1000, 999, -999, 1000, -1000, 999, -999, 1000, -1000, 999, -999, 1000, -1000]),  # Test case 34
        ([0, 0, 0, 0, 0]),  # Test case 35
        ([100, 200, 300, 400, 500, 600, 700]),  # Test case 36
        ([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]),  # Test case 37
        ([-100, -200, -300, -400, -500]),  # Test case 38
        ([1, 2, 2, 2, 2, 2, 3]),  # Test case 39
        ([5]),  # Test case 40
        ([7, 7, 7, 8, 8, 8]),  # Test case 41
        ([-5, -5, -2, -2, 0, 0, 1, 1, 3, 3, 4, 4]),  # Test case 42
        ([10]*100 + [20]*100),  # Test case 43
        (list(range(-1000, 0)) + list(range(1, 1000))),  # Test case 44
        ([10, 10, 10, 10, 10, 10, 10]),  # Test case 45
        ([-1, 0, 1]),  # Test case 46
        ([-1, -2, -2, -1]),  # Test case 47
        ([0]),  # Test case 48
        ([1, -1, 0]),  # Test case 49
        ([5, 5, 5, 4, 4, 4, 3, 2, 1]),  # Test case 50
        ([-5, -5, -5, -4, -4, -4, -3, -2, -1]),  # Test case 51
        ([0, 0, 0, 0, 0, 0, 0, 0, 0, -1]),  # Test case 52
        ([100, -100, 0, 50, -50, 25, -25, 75, -75]),  # Test case 53
        ([15, -15, 30, -30, 0, 45, -45, 60, -60, 75, -75]),  # Test case 54
    ]

TEST_INPUTS = [
    item if isinstance(item, tuple) else (item,)
    for item in _RAW_TEST_INPUTS
]

TEST_CASES = []
