"""
SPECTRA test data for EvoEval/16.

Converted from the EvoEval benchmark test suite.
"""

_RAW_TEST_INPUTS = [
        ('xyzXYZabc', 3),  # Test case 1
        ('Jerry', 2),  # Test case 2
        ('Jerry', 6),  # Test case 3
        ('', 0),  # Test case 4
        ('a', 1),  # Test case 5
        ('aa', 1),  # Test case 6
        ('aaa', 2),  # Test case 7
        ('a'*100, 100),  # Test case 8
        ('abc'*33+'a', 100),  # Test case 9
        ('abcdefghijklmnopqrstuvwxyz', 25),  # Test case 10
        ('abcdefghijklmnopqrstuvwxyz', 26),  # Test case 11
        ('abcdefghijklmnopqrstuvwxyz', 27),  # Test case 12
        ('a'*1000+'b'*1000, 2000),  # Test case 13
        ('z'*1000+'y'*1000, 1),  # Test case 14
        ('abcdefghijklmnopqrstuvwxyz', 5),  # Test case 15
        ('abcdefghijklmnopqrstuvwxyZabcdefghijklmnopqrstuvwxyZ', 10),  # Test case 16
        ('1234567890', 4),  # Test case 17
        ('Hello World!', 4),  # Test case 18
        ('AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRSSTTUUVVWWXXYYZZ', 8),  # Test case 19
        ('abcde'*100, 50),  # Test case 20
        ('a'*100 + 'b'*100, 150),  # Test case 21
        ('Python Python Python', 6),  # Test case 22
        ('1234567890'*10, 1),  # Test case 23
        ('The quick brown fox', 3),  # Test case 24
        ('jumped over the lazy dog', 5),  # Test case 25
        ('Python is a great language for data analysis', 10),  # Test case 26
        ('I love Machine Learning and Artificial Intelligence', 15),  # Test case 27
        ('Java, C++, Ruby, Rust, Go, Perl', 4),  # Test case 28
        ('JavaScript is also a great language for web development', 7),  # Test case 29
        ('', 3),  # Test case 30
        ('a', 1),  # Test case 31
        ('abcde', 5),  # Test case 32
        ('aaaaa', 3),  # Test case 33
        ('abcabcabc', 3),  # Test case 34
        ('1234567890', 10),  # Test case 35
        ('a'*100, 50),  # Test case 36
        ('abc'*33+'a', 100),  # Test case 37
        ('xyz'*34, 101),  # Test case 38
        ('uniquecharactersonly', 20),  # Test case 39
        ('with spaces and symbols $#@!', 5),  # Test case 40
        ('UPPERCASE', 2),  # Test case 41
        ('lowercase', 9),  # Test case 42
        ('MiXedCaSe', 4),  # Test case 43
        ('SpecialCharacters #$%&*', 5),  # Test case 44
        ('nonasciicharactersĀāĒē', 6),  # Test case 45
        ('with\nnewlines', 4),  # Test case 46
        ('aaabbbccc', 3),  # Test case 47
        ('1234567890', 5),  # Test case 48
        ('!@#$%^', 2),  # Test case 49
        ('abcdefghijklmnopqrstuvwxyz', 26),  # Test case 50
        ('abcdefghijklmnopqrstuvwxyz', 27),  # Test case 51
        ('a'*10000 + 'b'*10000, 15000),  # Test case 52
        ('This is a sentence with many distinct characters', 10),  # Test case 53
        ('##@@!!%%^^&&', 4),  # Test case 54
        ('ABCabc123', 1),  # Test case 55
        ('AaBbCcDdEeFfGgHhIiJj', 2),  # Test case 56
        ('abcdefghijklmnopqrstuvwxyz', 5),  # Test case 57
        ('1234567890', 3),  # Test case 58
        ('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 4),  # Test case 59
        ('!@#$%^&*()_+-=', 2),  # Test case 60
        ('Lorem Ipsum Dolor Sit Amet', 6),  # Test case 61
        ('The quick brown fox jumps over the lazy dog', 7),  # Test case 62
        ('Pneumonoultramicroscopicsilicovolcanoconiosis', 8),  # Test case 63
        ('Supercalifragilisticexpialidocious', 9),  # Test case 64
        ('Two driven jocks help fax my big quiz', 10),  # Test case 65
        ('Bright vixens jump; dozy fowl quack', 11),  # Test case 66
        ('Jackdaws love my big sphinx of quartz', 12),  # Test case 67
        ('Mr. Jock, TV quiz PhD, bags few lynx', 13),  # Test case 68
        ('!@#$%^&*()_+-=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', 14),  # Test case 69
    ]

TEST_INPUTS = [
    item if isinstance(item, tuple) else (item,)
    for item in _RAW_TEST_INPUTS
]

TEST_CASES = []
