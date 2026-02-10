
import sys
import os

# Ensure current directory is in path so we can import the target
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target_fib import fib

def test_fib_small():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(5) == 5
    assert fib(10) == 55
    assert fib(32) == 2178309
