def customFibFib(n: int, startSequence: list, p: int):
    if (n < 3):
        return startSequence[n]
    a = startSequence[0]
    b = startSequence[1]
    c = startSequence[2]
    for _ in range((n - 2)):
        next_value = ((a + b) + c)
        if (next_value > p):
            return 'Limit Exceeded'
        (a, b, c) = (b, c, next_value)
    return c