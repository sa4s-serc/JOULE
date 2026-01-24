"""
Test Suite for Python Parser

Tests the AST to IR conversion.
"""

import pytest

from src.domain.ir.schema import (Assign, BinaryOp, Call, Constant, For,
                                  FunctionDef, If, Module, Name, While)
from src.infrastructure.parsing.python_parser import PythonParser


class TestPythonParser:
    """Test suite for Python parser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()

    def test_parse_simple_function(self):
        """Test parsing a simple function."""
        code = """
def add(a, b):
    return a + b
"""
        ir = self.parser.parse(code)

        assert isinstance(ir, Module)
        assert len(ir.body.statements) == 1

        func = ir.body.statements[0]
        assert isinstance(func, FunctionDef)
        assert func.name == "add"
        # Check args using Arguments schema
        assert len(func.args.args) == 2
        assert func.args.args[0].arg == "a"
        assert func.args.args[1].arg == "b"

    def test_parse_assignment(self):
        """Test parsing assignments."""
        code = "x = 10"
        ir = self.parser.parse(code)

        assert len(ir.body.statements) == 1
        stmt = ir.body.statements[0]
        assert isinstance(stmt, Assign)
        assert isinstance(stmt.value, Constant)
        assert stmt.value.value == 10

    def test_parse_if_statement(self):
        """Test parsing if statements."""
        code = """
if x > 0:
    y = 1
else:
    y = 0
"""
        ir = self.parser.parse(code)

        stmt = ir.body.statements[0]
        assert isinstance(stmt, If)
        assert stmt.orelse is not None
        assert len(stmt.body.statements) == 1
        assert len(stmt.orelse.statements) == 1

    def test_parse_for_loop(self):
        """Test parsing for loops."""
        code = """
for i in range(10):
    x = i
"""
        ir = self.parser.parse(code)

        stmt = ir.body.statements[0]
        assert isinstance(stmt, For)
        assert isinstance(stmt.target, Name)
        assert isinstance(stmt.iter, Call)

    def test_parse_while_loop(self):
        """Test parsing while loops."""
        code = """
while x > 0:
    x = x - 1
"""
        ir = self.parser.parse(code)

        stmt = ir.body.statements[0]
        assert isinstance(stmt, While)
        assert len(stmt.body.statements) == 1

    def test_parse_binary_operations(self):
        """Test parsing binary operations."""
        code = "result = a + b * c"
        ir = self.parser.parse(code)

        assign = ir.body.statements[0]
        assert isinstance(assign.value, BinaryOp)
        assert assign.value.op == "+"

    def test_parse_function_call(self):
        """Test parsing function calls."""
        code = "result = func(1, 2, key=3)"
        ir = self.parser.parse(code)

        assign = ir.body.statements[0]
        assert isinstance(assign.value, Call)
        assert len(assign.value.args) == 2
        assert len(assign.value.keywords) == 1

    def test_parse_list_comprehension(self):
        """Test parsing list comprehensions."""
        code = "squares = [x * x for x in range(10)]"
        ir = self.parser.parse(code)

        # List comprehensions should be parsed
        assert len(ir.body.statements) == 1

    def test_parse_complex_function(self):
        """Test parsing a complex function."""
        code = """
def factorial(n):
    if n <= 1:
        return 1
    else:
        return n * factorial(n - 1)
"""
        ir = self.parser.parse(code)

        func = ir.body.statements[0]
        assert isinstance(func, FunctionDef)
        assert func.name == "factorial"
        assert len(func.body.statements) == 1
        assert isinstance(func.body.statements[0], If)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
