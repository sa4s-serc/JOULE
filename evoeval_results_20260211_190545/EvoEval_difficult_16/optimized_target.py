def count_distinct_characters_substrings(string: str, length: int) -> dict:
    n = len(string)
    if (length > n):
        return {}
    result = {}
    char_counts = {}
    distinct_count = 0
    for i in range(length):
        char = string[i]
        if (char not in char_counts):
            char_counts[char] = 0
            distinct_count += 1
        char_counts[char] += 1
    result[string[0:length]] = distinct_count
    for i in range(1, ((n - length) + 1)):
        left_char = string[(i - 1)]
        right_char = string[((i + length) - 1)]
        char_counts[left_char] -= 1
        if (char_counts[left_char] == 0):
            distinct_count -= 1
        if (char_counts.get(right_char, 0) == 0):
            distinct_count += 1
            char_counts[right_char] = 0
        char_counts[right_char] += 1
        result[string[i:(i + length)]] = distinct_count
    return result