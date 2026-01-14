
import pytest
import sys
import os

# Ensure current directory is in path so we can import the target
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target_fib import run_fib

def test_fib_small():
    assert run_fib(0) == 0
    assert run_fib(1) == 1
    assert run_fib(5) == 5
    assert run_fib(10) == 55

def test_fib_timing():
    # This is just to ensure it works, HEDGE will measure the speedup
    assert run_fib(15) == 610
