
def fib(n):
    """
    Inefficient recursive Fibonacci implementation.
    O(2^n) complexity.
    HEDGE should optimize this (e.g., iterative or memoized).
    """
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

def run_fib(n):
    # Some redundant work
    x = 10 * 20
    y = x + 30
    result = fib(n)
    return result
