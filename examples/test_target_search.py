
import pytest
import sys
import os

# Ensure current directory is in path so we can import the target
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target_search import search_element, contains_all

def test_search_basic():
    data = [1, 2, 3, 4, 5]
    assert search_element(data, 3) is True
    assert search_element(data, 6) is False

def test_contains_all():
    data = list(range(100))
    targets = [10, 50, 200]
    assert contains_all(data, targets) == [True, True, False]

def test_contains_all_large():
    # O(N*M)
    # N=20000, M=1000 -> 2*10^7 ops
    import random
    random.seed(42)
    data = list(range(20000))
    # Shuffle to ensure we don't hit best/worst case easily if logic changes,
    # though linear search average is N/2.
    random.shuffle(data)
    
    # 500 targets, half present
    present = data[:500] 
    missing = [x + 50000 for x in range(500)]
    targets = present + missing
    random.shuffle(targets)
    
    results = contains_all(data, targets)
    assert sum(results) == 500
