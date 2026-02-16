def customFibFib(n: int, startSequence: list, p: int):
    if (n < 3):
        return startSequence[n]
    def _tribonacci_generator_internal(initial_values: list):
        yield initial_values[0]
        yield initial_values[1]
        yield initial_values[2]
        (a, b, c) = (initial_values[0], initial_values[1], initial_values[2])
        while True:
            next_val = ((a + b) + c)
            yield next_val
            (a, b, c) = (b, c, next_val)
    trib_gen = _tribonacci_generator_internal(startSequence)
    value = None
    for i in range((n + 1)):
        value = next(trib_gen)
        if (value > p):
            return 'Limit Exceeded'
    return value