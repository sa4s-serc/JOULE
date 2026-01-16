
import pytest
import sys
import os

# Ensure current directory is in path so we can import the target
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from target_complex import process_data

def test_process_data_small():
    data = [5, 2, 9, 1, 5, 6]
    # Sorted: 1, 2, 5, 5, 6, 9
    # Evens: 2, 6
    # Processed (x*3): 6, 18
    # Total: 24
    # Mean: 12
    # Variance term: (6-12)^2 + (18-12)^2 = 36 + 36 = 72
    
    total, var = process_data(data)
    assert total == 24
    assert var == 72

def test_process_data_empty():
    total, var = process_data([])
    assert total == 0
    assert var == 0


def test_process_data_large():
    # Only odds
    # logic in target: 
    # 1. Sort (Bubble sort O(N^2))
    # 2. Filter evens (leaves 0 items if all odds)
    # 3. Sum (0)
    # 4. Variance (0)
    
    # If we pass all odds, the sorting takes O(N^2) but the rest is fast.
    # We want to exercise the other parts too.
    import random
    random.seed(42)
    # N=6000 -> Bubble sort ~3.6*10^7 comparisons. 
    # This should definitely take >2s.
    data = [random.randint(1, 1000) for _ in range(6000)]
    
    # Calculate expected
    # Filter evens (roughly half)
    evens = sorted([x for x in data if x % 2 == 0])
    processed = [x * 3 for x in evens]
    if not processed:
        expected_total = 0
        expected_var = 0
    else:
        expected_total = sum(processed)
        mean = expected_total / len(processed)
        expected_var = int(sum((x - mean) ** 2 for x in processed))

    total, var = process_data(data)
    assert total == expected_total
    assert var == expected_var

