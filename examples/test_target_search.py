
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
