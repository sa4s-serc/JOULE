"""
Test IR Serialization

Ensures that IR snapshots are properly serialized with complete type information
and can be saved/loaded correctly.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.domain.ir.serialization import IRSerializer
from src.infrastructure.parsing.python_parser import PythonParser


def test_ir_serialization_not_empty():
    """Test that IR serialization produces non-empty output with type information."""
    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)

    # Should not be empty or minimal
    assert len(serialized) > 100, "Serialized IR is too small, likely empty"

    # Should contain type information
    assert '"__type__"' in serialized, "Missing __type__ discriminator"

    # Parse JSON to verify structure
    data = json.loads(serialized)
    assert data["__type__"] == "Module", "Missing Module type"
    assert "body" in data, "Missing body"
    assert data["body"]["__type__"] == "Block", "Missing Block type"
    assert len(data["body"]["statements"]) > 0, "No statements in serialized IR"


def test_ir_serialization_preserves_nested_types():
    """Test that nested IR nodes maintain type information."""
    code = """
def test(x):
    if x > 0:
        return x * 2
    return 0
"""
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)
    data = json.loads(serialized)

    # Check nested statement types
    statements = data["body"]["statements"]
    assert len(statements) > 0, "No statements found"

    # First statement should be a FunctionDef
    func_def = statements[0]
    assert func_def["__type__"] == "FunctionDef", "Function not properly typed"
    assert "name" in func_def, "Missing function name"
    assert func_def["name"] == "test", "Function name not preserved"

    # Check function body
    func_body = func_def["body"]
    assert func_body["__type__"] == "Block", "Function body not properly typed"
    assert len(func_body["statements"]) > 0, "Empty function body"

    # First statement in body should be If
    if_stmt = func_body["statements"][0]
    assert if_stmt["__type__"] == "If", "If statement not properly typed"
    assert "test" in if_stmt, "Missing if test condition"
    assert if_stmt["test"]["__type__"] == "Compare", "Compare not properly typed"


def test_ir_serialization_expressions():
    """Test that expressions are properly serialized with types."""
    code = "x = 1 + 2 * 3"
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)
    data = json.loads(serialized)

    # Get the assignment
    assign = data["body"]["statements"][0]
    assert assign["__type__"] == "Assign", "Assignment not properly typed"

    # Check the value is a BinaryOp
    value = assign["value"]
    assert value["__type__"] == "BinaryOp", "BinaryOp not properly typed"
    assert "left" in value, "Missing left operand"
    assert "right" in value, "Missing right operand"

    # Left should be a Constant
    left = value["left"]
    assert left["__type__"] == "Constant", "Constant not properly typed"
    assert left["value"] == 1, "Constant value not preserved"
    assert left["kind"] == "int", "Constant kind not preserved"


def test_ir_save_and_load():
    """Test that IR can be saved to file and loaded back."""
    code = """
def greet(name):
    return "Hello, " + name
"""
    parser = PythonParser()
    ir = parser.parse(code)

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test_ir.json"

        # Save
        IRSerializer.save(ir, filepath)

        # Verify file exists and is not empty
        assert filepath.exists(), "IR file not created"
        assert filepath.stat().st_size > 100, "IR file is too small"

        # Load and verify content
        with open(filepath) as f:
            content = f.read()
            data = json.loads(content)

            assert data["__type__"] == "Module", "Loaded IR missing type"
            assert len(data["body"]["statements"]) > 0, "Loaded IR missing statements"


def test_ir_serialization_all_node_types():
    """Test that various IR node types are all properly serialized."""
    code = """
def complex_func(x, y):
    # Various statement types
    result = 0
    
    # If statement
    if x > 0:
        result = x + y
    
    # While loop
    while y > 0:
        y -= 1
        result += 1
    
    # For loop
    for i in range(10):
        result += i
    
    # Return
    return result
"""
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)
    data = json.loads(serialized)

    # Verify we have multiple statement types with proper typing
    func_body = data["body"]["statements"][0]["body"]["statements"]

    statement_types = {stmt["__type__"] for stmt in func_body}

    # Should have various statement types
    assert "Assign" in statement_types, "Missing Assign type"
    assert "If" in statement_types, "Missing If type"
    assert "While" in statement_types, "Missing While type"
    assert "For" in statement_types, "Missing For type"
    assert "Return" in statement_types, "Missing Return type"


def test_ir_serialization_list_of_nodes():
    """Test that lists of IR nodes are properly serialized."""
    code = """
def multi_assign():
    a, b, c = 1, 2, 3
    return a + b + c
"""
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)
    data = json.loads(serialized)

    # Get the function body
    func_body = data["body"]["statements"][0]["body"]["statements"]

    # First statement should be Assign with multiple targets
    assign = func_body[0]
    assert assign["__type__"] == "Assign", "Assign not properly typed"

    # Targets should be a list with type information preserved
    targets = assign["targets"]
    assert isinstance(targets, list), "Targets not a list"

    if len(targets) > 0:
        # Each target should have __type__
        for target in targets:
            if isinstance(target, dict):
                assert "__type__" in target, "Target missing type information"


def test_ir_serialization_no_empty_dicts():
    """Test that serialization doesn't produce empty dictionaries."""
    code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
"""
    parser = PythonParser()
    ir = parser.parse(code)

    serialized = IRSerializer.serialize(ir)

    # Count occurrences of empty dicts or near-empty structures
    # This was the bug: statements were serialized as [{}]
    assert serialized.count("{}") == 0, "Found empty dictionaries in serialization"

    # Verify we have substantial content
    data = json.loads(serialized)

    def count_type_fields(obj, count=0):
        """Recursively count __type__ fields."""
        if isinstance(obj, dict):
            if "__type__" in obj:
                count += 1
            for value in obj.values():
                count = count_type_fields(value, count)
        elif isinstance(obj, list):
            for item in obj:
                count = count_type_fields(item, count)
        return count

    type_count = count_type_fields(data)
    # Should have many __type__ fields for all the IR nodes
    assert type_count >= 10, f"Too few typed nodes ({type_count}), serialization incomplete"


if __name__ == "__main__":
    # Run all tests
    test_ir_serialization_not_empty()
    test_ir_serialization_preserves_nested_types()
    test_ir_serialization_expressions()
    test_ir_save_and_load()
    test_ir_serialization_all_node_types()
    test_ir_serialization_list_of_nodes()
    test_ir_serialization_no_empty_dicts()
    print("✓ All IR serialization tests passed!")
