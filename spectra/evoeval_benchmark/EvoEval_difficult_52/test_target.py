"""
SPECTRA test data for EvoEval/52.

Converted from the EvoEval benchmark test suite.
"""

_RAW_TEST_INPUTS = [
        ([1, 2, 4, 10], 100, 0, 'below'),  # Test case 1
        ([1, 20, 4, 10], 5, 0, 'below'),  # Test case 2
        ([1, 20, 4, 10], 5, 0, 'above'),  # Test case 3
        ([10, 20, 30, 40], 5, 15, 'above'),  # Test case 4
        ([1, 10, 100, 1000], 50, 0, 'below'),  # Test case 5
        ([-1, -20, -4, -10], -5, 0, 'below'),  # Test case 6
        ([-1, -20, -4, -10], -3, -50, 'above'),  # Test case 7
        ([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 15, 15, 'above'),  # Test case 8
        ([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 15, 15, 'below'),  # Test case 9
        ([100]*1000, 100, 0, 'below'),  # Test case 10
        ([100]*1000, 100, 0, 'above'),  # Test case 11
        ([i for i in range(1000)], 500, 0, 'below'),  # Test case 12
        ([i for i in range(1000)], 500, 0, 'above'),  # Test case 13
        ([-1000, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0, -1001, 'above'),  # Test case 14
        ([-1000, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0, -1001, 'below'),  # Test case 15
        ([100, 200, 300, 400, 500], 250, 150, 'above'),  # Test case 16
        ([100, 200, 300, 400, 500], 250, 150, 'below'),  # Test case 17
        ([i for i in range(-500, 500)], 0, -1, 'above'),  # Test case 18
        ([i for i in range(-500, 500)], 0, -1, 'below'),  # Test case 19
        ([1, 1, 1, 1, 1, 2], 2, 0, 'below'),  # Test case 20
        ([1, 1, 1, 1, 1, 2], 2, 0, 'above'),  # Test case 21
        ([1000, -1000, 0], 500, -500, 'below'),  # Test case 22
        ([1000, -1000, 0], 500, -500, 'above'),  # Test case 23
        ([1000, -1000, 0], 500, 500, 'below'),  # Test case 24
        ([1000, -1000, 0], 500, 500, 'above'),  # Test case 25
        ([1000, -1000, 0, 500], 500, 500, 'below'),  # Test case 26
        ([1000, -1000, 0, 500], 500, 500, 'above'),  # Test case 27
        ([1000, -1000, 0, -500], 500, -500, 'below'),  # Test case 28
        ([1000, -1000, 0, -500], 500, -500, 'above'),  # Test case 29
        ([], 1000, -1000, 'below'),  # Test case 30
        ([], 1000, -1000, 'above'),  # Test case 31
        ([1000], 1000, -1000, 'below'),  # Test case 32
        ([1000], 1000, -1000, 'above'),  # Test case 33
        ([1, 2, 3], 2, 1, 'test'),  # Test case 34
        ([1, -1, 0], 1, -1, 'below'),  # Test case 35
        ([1, -1, 0], 1, -1, 'above'),  # Test case 36
        ([-1000, 0, 1000], 1000, -1000, 'below'),  # Test case 37
        ([-1000, 0, 1000], 1000, -1000, 'above'),  # Test case 38
        ([], 1, 0, 'below'),  # Test case 39
        ([0], 0, 0, 'below'),  # Test case 40
        ([0], 0, 0, 'above'),  # Test case 41
        ([1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000], 1000, 0, 'below'),  # Test case 42
        ([-1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000], 0, -1000, 'above'),  # Test case 43
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5, 0, 'below'),  # Test case 44
        ([-1, -2, -3, -4, -5, -6, -7, -8, -9, -10], 0, -5, 'above'),  # Test case 45
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10, 1, 'below'),  # Test case 46
        ([-1, -2, -3, -4, -5, -6, -7, -8, -9, -10], -10, -1, 'above'),  # Test case 47
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5, 1, 'below'),  # Test case 48
        ([-1, -2, -3, -4, -5, -6, -7, -8, -9, -10], -5, -1, 'above'),  # Test case 49
        ([1], 2, 0, 'below'),  # Test case 50
        ([1], 0, 2, 'above'),  # Test case 51
        ([1, -2, 3, -4, 5], 0, -3, 'below'),  # Test case 52
        ([-1, -2, -3, -4, -5], -3, -1, 'below'),  # Test case 53
        ([-1, -2, -3, -4, -5], -6, -1, 'above'),  # Test case 54
        ([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], 500, 1000, 'above'),  # Test case 55
        ([100, 200, 300, 400, 500, 600, 700, 800, 900, 1000], 100, 500, 'below'),  # Test case 56
        ([100, -200, 300, -400, 500, -600, 700, -800, 900, -1000], 500, -500, 'below'),  # Test case 57
        ([-100, 200, -300, 400, -500, 600, -700, 800, -900, 1000], -500, 0, 'above'),  # Test case 58
        ([], 5, -5, 'below'),  # Test case 59
        ([], 5, -5, 'above'),  # Test case 60
        ([-1, -2, -3, -4, -5], -3, -1, 'middle'),  # Test case 61
        ([1, 2, 3, 4, 5], 3, 1, 'middle'),  # Test case 62
    ]

TEST_INPUTS = [
    item if isinstance(item, tuple) else (item,)
    for item in _RAW_TEST_INPUTS
]

TEST_CASES = []
