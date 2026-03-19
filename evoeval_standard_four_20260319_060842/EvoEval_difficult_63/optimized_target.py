def customFibFib(n: int, startSequence: list, p: int):
    if (n < 3):
        return startSequence[n]
    f0 = startSequence[0]
    f1 = startSequence[1]
    f2 = startSequence[2]
    for _ in range(3, (n + 1)):
        next_f = ((f0 + f1) + f2)
        if (next_f > p):
            return 'Limit Exceeded'
        f0 = f1
        f1 = f2
        f2 = next_f
    return f2