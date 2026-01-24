"""
Test to verify IR round-trip with parser and code generator.
This replaces the deprecated L2 enhancement tests.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


def test_ir_if_statement():
    """Test that If statements are properly parsed and generated."""
    code = """
def max_value(a, b):
    if a > b:
        result = a
    else:
        result = b
    return result
"""
    parser = PythonParser()
    ir = parser.parse(code)

    # Reconstruct and verify it's valid Python
    codegen = PythonCodeGenerator()
    reconstructed = codegen.generate(ir)

    # Should be valid Python code
    compile(reconstructed, "<string>", "exec")

    # Should contain if statement
    assert "if" in reconstructed.lower()
    assert "else" in reconstructed.lower()
    print("✅ If statement test passed")
    print(f"Reconstructed code:\n{reconstructed}")


def test_ir_while_statement():
    """Test that While statements are properly parsed and generated."""
    code = """
def count_down(n):
    while n > 0:
        n = n - 1
    return n
"""
    parser = PythonParser()
    ir = parser.parse(code)

    # Reconstruct
    codegen = PythonCodeGenerator()
    reconstructed = codegen.generate(ir)

    # Should be valid Python
    compile(reconstructed, "<string>", "exec")

    # Should contain while loop
    assert "while" in reconstructed.lower()
    print("✅ While statement test passed")
    print(f"Reconstructed code:\n{reconstructed}")


def test_ir_for_statement():
    """Test that For statements are properly parsed and generated."""
    code = """
def sum_list(numbers):
    total = 0
    for num in numbers:
        total = total + num
    return total
"""
    parser = PythonParser()
    ir = parser.parse(code)

    # Reconstruct
    codegen = PythonCodeGenerator()
    reconstructed = codegen.generate(ir)

    # Should be valid Python
    compile(reconstructed, "<string>", "exec")

    # Should contain for loop
    assert "for" in reconstructed.lower()
    print("✅ For statement test passed")
    print(f"Reconstructed code:\n{reconstructed}")


def test_ir_nested_control_flow():
    """Test nested control flow structures."""
    code = """
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
    return arr
"""
    parser = PythonParser()
    ir = parser.parse(code)

    # Reconstruct
    codegen = PythonCodeGenerator()
    reconstructed = codegen.generate(ir)

    # Should be valid Python
    compile(reconstructed, "<string>", "exec")

    # Should contain nested structures
    assert "for" in reconstructed.lower()
    assert "if" in reconstructed.lower()

    # Verify it's properly indented
    lines = reconstructed.split("\n")
    outer_for_indent = None
    inner_for_indent = None

    for i, line in enumerate(lines):
        if "for" in line.lower() and outer_for_indent is None:
            outer_for_indent = len(line) - len(line.lstrip())
        elif "for" in line.lower() and outer_for_indent is not None:
            inner_for_indent = len(line) - len(line.lstrip())
            break

    if outer_for_indent is not None and inner_for_indent is not None:
        assert inner_for_indent > outer_for_indent, "Inner for should be more indented"

    print("✅ Nested control flow test passed")
    print(f"Reconstructed code:\n{reconstructed}")


if __name__ == "__main__":
    print("Testing IR Round-Trip (Parser/Codegen)\n" + "=" * 50)
    test_ir_if_statement()
    print()
    test_ir_while_statement()
    print()
    test_ir_for_statement()
    print()
    test_ir_nested_control_flow()
    print("\n" + "=" * 50)
    print("✅ All IR round-trip tests passed!")
