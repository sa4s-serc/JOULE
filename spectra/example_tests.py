"""
Example test file for SPECTRA.

Define TEST_INPUTS and/or TEST_CASES:
  - TEST_INPUTS: list of argument tuples fed to both the original and
    optimised function; outputs are compared for equivalence.
  - TEST_CASES: list of ((args...), expected_output) pairs that act as
    hard regression tests.

Both can coexist. SPECTRA also auto-generates ~40 fuzz inputs from
the types it sees in TEST_INPUTS, so you don't need to be exhaustive.
"""

# ── Inputs to measure and regression-test against ─────────────────────
TEST_INPUTS = [
    # Each entry is a tuple of arguments to pass to the function.
    (list(range(1_000)), list(range(500, 1_500))),   # large overlap
    (list(range(500)),   list(range(300, 800))),      # medium overlap
]

# ── Explicit expected-output test cases ───────────────────────────────
TEST_CASES = [
    # ((arg1, arg2, ...), expected_return_value)
    (([1, 2, 3, 4], [2, 4, 6]),        [2, 4]),
    (([],            [1, 2, 3]),        []),
    (([1, 1, 2, 2],  [1, 2]),           [1, 2]),
    (([5, 6, 7],     []),               []),  
]