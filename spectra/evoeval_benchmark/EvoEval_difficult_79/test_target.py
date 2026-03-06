"""
SPECTRA test data for EvoEval/79.

Converted from the EvoEval benchmark test suite.
"""

_RAW_TEST_INPUTS = [
        (15, 5),  # Test case 1
        (32, 5),  # Test case 2
        (32, 10),  # Test case 3
        (0, 5),  # Test case 4
        (1, 1),  # Test case 5
        (255, 8),  # Test case 6
        (1024, 5),  # Test case 7
        (500, 10),  # Test case 8
        (1023, 10),  # Test case 9
        (-10, 2),  # Test case 10
        (10, -2),  # Test case 11
        (10, 0),  # Test case 12
        ("string", 5),  # Test case 13
        (10, "string"),  # Test case 14
        (0.5, 1),  # Test case 15
        (True, 1),  # Test case 16
        (10, True),  # Test case 17
        (1, 1),  # Test case 18
        (2, 2),  # Test case 19
        (7, 3),  # Test case 20
        (100, 7),  # Test case 21
        (255, 8),  # Test case 22
        (1023, 10),  # Test case 23
        (2047, 11),  # Test case 24
        (0, 1),  # Test case 25
        (31, 1),  # Test case 26
        (200, 4),  # Test case 27
        (999, 20),  # Test case 28
        (-5, 10),  # Test case 29
        (10, -5),  # Test case 30
        ("abc", 10),  # Test case 31
        (10, "def"),  # Test case 32
        (None, 10),  # Test case 33
        (10, None),  # Test case 34
        ([], 10),  # Test case 35
        (10, []),  # Test case 36
        ({}, 10),  # Test case 37
        (10, {}),  # Test case 38
        (0, 5),  # Test case 39
        (1, 1),  # Test case 40
        (2, 1),  # Test case 41
        (32, 6),  # Test case 42
        (128, 8),  # Test case 43
        (255, 8),  # Test case 44
        (500, 10),  # Test case 45
        (-1, 5),  # Test case 46
        (15, -1),  # Test case 47
        ("15", 5),  # Test case 48
        (15, "5"),  # Test case 49
        (None, 5),  # Test case 50
        (15, None),  # Test case 51
        (0, 5),  # Test case 52
        (1, 5),  # Test case 53
        (255, 8),  # Test case 54
        (1023, 10),  # Test case 55
        (1000, 20),  # Test case 56
        (150, 12),  # Test case 57
        (-5, 5),  # Test case 58
        (15, -5),  # Test case 59
        ("15", 5),  # Test case 60
        (15, "5"),  # Test case 61
        ([], 5),  # Test case 62
        (15, []),  # Test case 63
        (0, 5),  # Test case 64
        (1, 2),  # Test case 65
        (2, 2),  # Test case 66
        (10, 2),  # Test case 67
        (10, 5),  # Test case 68
        (255, 10),  # Test case 69
        (255, 15),  # Test case 70
        (1024, 20),  # Test case 71
        (123456, 20),  # Test case 72
        (-1, 5),  # Test case 73
        (15, -1),  # Test case 74
        (15, 0),  # Test case 75
        ('15', 5),  # Test case 76
        (15, '5'),  # Test case 77
        (True, 5),  # Test case 78
        (None, 5),  # Test case 79
        (5.5, 5),  # Test case 80
        (5, 5.5),  # Test case 81
        ([15], 5),  # Test case 82
        (15, [5]),  # Test case 83
    ]

TEST_INPUTS = [
    item if isinstance(item, tuple) else (item,)
    for item in _RAW_TEST_INPUTS
]

TEST_CASES = []
