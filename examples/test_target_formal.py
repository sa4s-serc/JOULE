
import pytest
import sys
import os

# Ensure current directory is in path so we can import the target
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target_formal import formal_calculation

def test_formal_small():
    # a = 600, b = 640
    # result = x + 0 = x
    # returns x + 640 + 0
    assert formal_calculation(10, 5) == 650
    assert formal_calculation(0, 100) == 640

def test_formal_negative():
    assert formal_calculation(-10, 5) == 630

def test_formal_throughput():
    # Calling this many times will show if constant folding happens or not
    # O(1) per call, but overhead matters
    # 1,000,000 calls
    total = 0
    for i in range(1000000):
        # x=i, y=i
        # result = i + 640
        total += formal_calculation(i, i)
    
    # Sum of (i + 640) for i in 0..999999
    # Sum(i) = n(n-1)/2 = 1000000*999999/2 = 500000 * 999999 = 499999500000
    # Sum(640) = 640 * 1000000 = 640000000
    # Total = 499999500000 + 640000000 = 500639500000
    assert total == 500639500000
