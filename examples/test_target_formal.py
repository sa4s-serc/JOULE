
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
