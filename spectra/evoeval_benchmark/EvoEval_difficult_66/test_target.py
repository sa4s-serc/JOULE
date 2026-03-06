"""
SPECTRA test data for EvoEval/66.

Converted from the EvoEval benchmark test suite.
"""

_RAW_TEST_INPUTS = [
        ("", "abc"),  # Test case 1
        ("abAB", "abc"),  # Test case 2
        ("abcCd", ""),  # Test case 3
        ("helloE", "abc"),  # Test case 4
        ("woArBld", "xyz"),  # Test case 5
        ("ZABCD", "zabcd"),  # Test case 6
        ("HELLO", "hello"),  # Test case 7
        ("WORLD", "world"),  # Test case 8
        ("Python", "python"),  # Test case 9
        ("Java", "java"),  # Test case 10
        ("JavaScript", "javascript"),  # Test case 11
        ("Csharp", "csharp"),  # Test case 12
        ("GOlang", "golang"),  # Test case 13
        ("Kotlin", "kotlin"),  # Test case 14
        ("RUBY", "ruby"),  # Test case 15
        ("Scala", "scala"),  # Test case 16
        ("LuA", "lua"),  # Test case 17
        ("Tcl", "tcl"),  # Test case 18
        ("SwifT", "swift"),  # Test case 19
        ("VbNet", "vbnet"),  # Test case 20
        ("Perl", "perl"),  # Test case 21
        ("PHP", "php"),  # Test case 22
        ("Rust", "rust"),  # Test case 23
        ("TypeScript", "typescript"),  # Test case 24
        ("Groovy", "groovy"),  # Test case 25
        ("!@#$$%^&*()", "abc123"),  # Test case 26
        ("ABCDEFG", "1234567"),  # Test case 27
        ("?!@#$%^&*", "abcdefghijklmnopqrstuvwxyz"),  # Test case 28
        ("NOupperCaseHere", "alllowercasehere"),  # Test case 29
        ("MIXEDcaseINPUT", "mixedCASEinput"),  # Test case 30
        ("~`!@#$%^&*()-_=+[]{}\|;:'\",<.>/?", "qwertyuiopasdfghjklzxcvbnm"),  # Test case 31
        ("a"*10000 + "A"*10000, "z"*10000 + "Z"*10000),  # Test case 32
        ("aaaaaAAAAA", "bbbbbBBBBB"),  # Test case 33
        ("1234567890", "!@#$%^&*()"),  # Test case 34
        ("", ""),  # Test case 35
        ("1234567890", "1234567890"),  # Test case 36
        ("AAAAAAA", "aaaaaaa"),  # Test case 37
        ("A"*100000, "a"*100000),  # Test case 38
        ("!@#$%^&*()", "!@#$%^&*()"),  # Test case 39
        ("ABCDEFGHIJKLM", "nopqrstuvwxyz"),  # Test case 40
        ("AbCdEfG", "HjKlMnO"),  # Test case 41
        ("Z", "z"),  # Test case 42
        ("Hello World", "HELLO WORLD"),  # Test case 43
        (" ", " "),  # Test case 44
        ("\t\n\r", "\t\n\r"),  # Test case 45
        ("aA", "Aa"),  # Test case 46
        ("ABCD", "abcd"),  # Test case 47
        ("", ""),  # Test case 48
        (" ", " "),  # Test case 49
        ("12345", "67890"),  # Test case 50
        ("AbCdEfG", "hIjKlMn"),  # Test case 51
        ("!@#$%^&*()", "_+=-"),  # Test case 52
        ("mixedCaseString", "MIXEDCASESTRING"),  # Test case 53
        ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"),  # Test case 54
        ("aaaaa", "BBBBB"),  # Test case 55
        ("", ""),  # Test case 56
        ("ABCD", "abcd"),  # Test case 57
        ("123", "456"),  # Test case 58
        ("abcd", "ABCD"),  # Test case 59
        ("!@#$%^&", "*&^%$#@"),  # Test case 60
        ("     ", "     "),  # Test case 61
        ("AaBbCc", "DdEeFf"),  # Test case 62
        ("XYZ", "xyz"),  # Test case 63
        ("HelloWorld", "helloworld"),  # Test case 64
        ("MixedCase123", "mixedcase123"),  # Test case 65
        ("NONALPHANUMERIC", "nonalphanumeric"),  # Test case 66
        ("UpperCaseOnly", "lowercaseonly"),  # Test case 67
        ("NoUpperCaseHere", "NOLOWERCASEHERE"),  # Test case 68
        ("SingleChar", "a"),  # Test case 69
        ("U", "l"),  # Test case 70
        ("VeryLongStringWithOnlyUpperCaseCharacters"*100, "VeryLongStringWithOnlyLowerCaseCharacters"*100),  # Test case 71
    ]

TEST_INPUTS = [
    item if isinstance(item, tuple) else (item,)
    for item in _RAW_TEST_INPUTS
]

TEST_CASES = []
