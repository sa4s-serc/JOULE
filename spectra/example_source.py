"""
Example source file for SPECTRA.
Run with:
  python spectra.py --source example_source.py --tests example_tests.py
"""

def find_common_elements(list_a, list_b):
    """Return elements present in both lists, preserving order from list_a."""
    result = []
    for item in list_a:
        if item in list_b:
            if item not in result:
                result.append(item)
    return result