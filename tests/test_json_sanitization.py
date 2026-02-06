"""
Tests for JSON sanitization utility

Verifies that IR objects and other non-serializable types
are properly converted to JSON-safe formats.
"""

import json
from datetime import datetime

import pytest

from api.utils import (safe_json_dumps, sanitize_for_json,
                       validate_json_serializable)
from src.domain.ir.schema import BinaryOp, Constant, Name


class TestSanitizeForJson:
    """Test the sanitize_for_json function."""

    def test_basic_types(self):
        """Test that basic JSON-safe types pass through unchanged."""
        assert sanitize_for_json(None) is None
        assert sanitize_for_json(42) == 42
        assert sanitize_for_json(3.14) == 3.14
        assert sanitize_for_json("hello") == "hello"
        assert sanitize_for_json(True) is True
        assert sanitize_for_json(False) is False

    def test_datetime(self):
        """Test datetime conversion to ISO format."""
        dt = datetime(2024, 1, 15, 12, 30, 45)
        result = sanitize_for_json(dt)
        assert isinstance(result, str)
        assert "2024-01-15" in result

    def test_constant_ir_object(self):
        """Test Constant IR object serialization."""
        const = Constant(value=42, kind="int")
        result = sanitize_for_json(const)

        # Should be a dict with the constant's data
        assert isinstance(result, dict)
        assert result["value"] == 42
        assert result["kind"] == "int"

        # Should be JSON-serializable
        json_str = json.dumps(result)
        assert "42" in json_str

    def test_nested_ir_objects(self):
        """Test nested IR objects in dictionaries."""
        data = {
            "metrics": {
                "constant": Constant(value=100, kind="int"),
                "nested": {"value": Constant(value=3.14, kind="float")},
            }
        }

        result = sanitize_for_json(data)

        # Should be fully serializable
        json_str = json.dumps(result)
        assert "100" in json_str
        assert "3.14" in json_str

    def test_ir_objects_in_lists(self):
        """Test IR objects in lists."""
        data = {"values": [1, 2, Constant(value=3, kind="int"), Constant(value=4, kind="int")]}

        result = sanitize_for_json(data)

        # Should be serializable
        json_str = json.dumps(result)
        assert json_str is not None

    def test_complex_ir_expression(self):
        """Test complex IR expression (BinaryOp)."""
        expr = BinaryOp(left=Name(id="x"), op="+", right=Constant(value=10, kind="int"))

        result = sanitize_for_json(expr)

        # Should be a dict
        assert isinstance(result, dict)

        # Should be JSON-serializable
        json_str = json.dumps(result)
        assert json_str is not None

    def test_sets(self):
        """Test set conversion to list."""
        data = {"values": {1, 2, 3}}
        result = sanitize_for_json(data)

        # Set should be converted to list
        assert isinstance(result["values"], list)
        assert len(result["values"]) == 3

    def test_recursion_protection(self):
        """Test that deep recursion is handled."""
        # Create deeply nested structure
        data = {"level": 0}
        current = data
        for i in range(20):
            current["next"] = {"level": i + 1}
            current = current["next"]

        # Should not raise RecursionError
        result = sanitize_for_json(data, max_depth=10)
        assert result is not None

    def test_custom_object_with_dict(self):
        """Test custom object with __dict__."""

        class CustomObj:
            def __init__(self):
                self.value = 42
                self.name = "test"
                self._private = "hidden"

        obj = CustomObj()
        result = sanitize_for_json(obj)

        # Should extract public attributes
        assert isinstance(result, dict)
        assert result["value"] == 42
        assert result["name"] == "test"
        assert "_private" not in result

    def test_mixed_complex_structure(self):
        """Test complex mixed structure with various types."""
        data = {
            "timestamp": datetime.now(),
            "metrics": {
                "constant": Constant(value=42, kind="int"),
                "values": [1, 2, 3],
                "nested": {
                    "expr": BinaryOp(left=Name(id="x"), op="*", right=Constant(value=2, kind="int"))
                },
            },
            "tags": {"tag1", "tag2", "tag3"},
            "none_value": None,
            "bool_value": True,
        }

        result = sanitize_for_json(data)

        # Should be fully JSON-serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Verify structure is preserved
        assert isinstance(result["metrics"], dict)
        assert isinstance(result["tags"], list)
        assert result["none_value"] is None
        assert result["bool_value"] is True


class TestValidateJsonSerializable:
    """Test the validate_json_serializable function."""

    def test_valid_data(self):
        """Test that valid JSON data is recognized."""
        assert validate_json_serializable({"key": "value"})
        assert validate_json_serializable([1, 2, 3])
        assert validate_json_serializable("string")
        assert validate_json_serializable(42)

    def test_invalid_data(self):
        """Test that invalid JSON data is recognized."""
        const = Constant(value=42, kind="int")
        assert not validate_json_serializable(const)
        assert not validate_json_serializable({"const": const})


class TestSafeJsonDumps:
    """Test the safe_json_dumps function."""

    def test_valid_data(self):
        """Test that valid data is serialized directly."""
        data = {"key": "value", "number": 42}
        result = safe_json_dumps(data)
        assert isinstance(result, str)
        assert "value" in result

    def test_invalid_data_auto_sanitized(self):
        """Test that invalid data is automatically sanitized."""
        data = {"constant": Constant(value=42, kind="int"), "name": "test"}

        # Should not raise TypeError
        result = safe_json_dumps(data)
        assert isinstance(result, str)
        assert "42" in result
        assert "test" in result

    def test_with_indent(self):
        """Test that kwargs are passed through."""
        data = {"key": "value"}
        result = safe_json_dumps(data, indent=2)
        assert isinstance(result, str)
        assert "\n" in result  # Indented output has newlines


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
