"""
Test Suite for Code Generator

Tests IR to Python code generation.
"""

import pytest

from src.domain.ir.schema import *
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


class TestCodeGenerator:
    """Test suite for code generator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.codegen = PythonCodeGenerator()
        self.parser = PythonParser()

    def test_generate_simple_function(self):
        """Test generating a simple function."""
        ir = Module(
            body=Block(
                statements=[
                    FunctionDef(
                        name="add",
                        args=Arguments(
                            posonlyargs=[],
                            args=[Arg(arg="a"), Arg(arg="b")],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=Block(
                            statements=[
                                Return(
                                    value=BinaryOp(
                                        left=Name(id="a", ctx="Load"),
                                        op="+",
                                        right=Name(id="b", ctx="Load"),
                                    )
                                )
                            ]
                        ),
                    )
                ]
            )
        )

        code = self.codegen.generate(ir)
        assert "def add(a, b):" in code
        assert "return" in code

    def test_generate_assignment(self):
        """Test generating assignments."""
        ir = Module(
            body=Block(
                statements=[
                    Assign(
                        targets=[Name(id="x", ctx="Store")], value=Constant(value=10, kind="int")
                    )
                ]
            )
        )

        code = self.codegen.generate(ir)
        assert "x = 10" in code

    def test_generate_if_statement(self):
        """Test generating if statements."""
        ir = Module(
            body=Block(
                statements=[
                    If(
                        test=Compare(
                            left=Name(id="x", ctx="Load"),
                            ops=[">"],
                            comparators=[Constant(value=0, kind="int")],
                        ),
                        body=Block(statements=[Return(value=Constant(value=True, kind="bool"))]),
                        orelse=Block(statements=[Return(value=Constant(value=False, kind="bool"))]),
                    )
                ]
            )
        )

        code = self.codegen.generate(ir)
        assert "if" in code
        assert "else:" in code

    def test_generate_for_loop(self):
        """Test generating for loops."""
        ir = Module(
            body=Block(
                statements=[
                    For(
                        target=Name(id="i", ctx="Store"),
                        iter=Call(
                            func=Name(id="range", ctx="Load"),
                            args=[Constant(value=10, kind="int")],
                            keywords=[],
                        ),
                        body=Block(statements=[Pass()]),
                    )
                ]
            )
        )

        code = self.codegen.generate(ir)
        assert "for i in range(10):" in code

    def test_round_trip_preservation(self):
        """Test that parse -> generate -> parse produces same IR structure."""
        original_code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        # Parse
        ir1 = self.parser.parse(original_code)

        # Generate
        generated_code = self.codegen.generate(ir1)

        # Parse again
        ir2 = self.parser.parse(generated_code)

        # Generate again
        generated_code2 = self.codegen.generate(ir2)

        # Should be idempotent
        assert generated_code == generated_code2

    def test_generate_binary_operations(self):
        """Test generating binary operations."""
        ir = Module(
            body=Block(
                statements=[
                    Assign(
                        targets=[Name(id="result", ctx="Store")],
                        value=BinaryOp(
                            left=Constant(value=1, kind="int"),
                            op="+",
                            right=BinaryOp(
                                left=Constant(value=2, kind="int"),
                                op="*",
                                right=Constant(value=3, kind="int"),
                            ),
                        ),
                    )
                ]
            )
        )

        code = self.codegen.generate(ir)
        assert "result" in code
        assert "+" in code
        assert "*" in code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
