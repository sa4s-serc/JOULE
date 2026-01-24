"""
Test Suite for IR Validators

Tests schema and structural validation.
"""

import pytest

from src.domain.ir.schema import *
from src.domain.ir.validators import IRValidator


class TestIRValidator:
    """Test suite for IR validators."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = IRValidator()

    def test_valid_function(self):
        """Test validating a valid function."""
        ir = Module(
            body=Block(
                statements=[
                    FunctionDef(
                        name="test",
                        args=["x"],
                        body=Block(statements=[Return(value=Name(id="x", ctx="Load"))]),
                    )
                ]
            )
        )

        result = self.validator.validate(ir)
        assert result.valid == True
        assert len(result.errors) == 0

    def test_duplicate_function_names(self):
        """Test detection of duplicate function names."""
        ir = Module(
            body=Block(
                statements=[
                    FunctionDef(name="test", args=[], body=Block(statements=[])),
                    FunctionDef(name="test", args=[], body=Block(statements=[])),
                ]
            )
        )

        result = self.validator.validate(ir)
        assert result.valid == False
        assert any("Duplicate function name" in err for err in result.errors)

    def test_return_outside_function(self):
        """Test detection of return outside function."""
        ir = Module(body=Block(statements=[Return(value=Constant(value=1, kind="int"))]))

        result = self.validator.validate(ir)
        assert result.valid == False
        assert any("Return statement outside function" in err for err in result.errors)

    def test_break_outside_loop(self):
        """Test detection of break outside loop."""
        ir = Module(
            body=Block(
                statements=[FunctionDef(name="test", args=[], body=Block(statements=[Break()]))]
            )
        )

        result = self.validator.validate(ir)
        assert result.valid == False
        assert any("Break/Continue statement outside loop" in err for err in result.errors)

    def test_valid_break_in_loop(self):
        """Test that break in loop is valid."""
        ir = Module(
            body=Block(
                statements=[
                    FunctionDef(
                        name="test",
                        args=[],
                        body=Block(
                            statements=[
                                While(
                                    test=Constant(value=True, kind="bool"),
                                    body=Block(statements=[Break()]),
                                )
                            ]
                        ),
                    )
                ]
            )
        )

        result = self.validator.validate(ir)
        assert result.valid == True

    def test_valid_return_in_function(self):
        """Test that return in function is valid."""
        ir = Module(
            body=Block(
                statements=[
                    FunctionDef(
                        name="test",
                        args=[],
                        body=Block(statements=[Return(value=Constant(value=0, kind="int"))]),
                    )
                ]
            )
        )

        result = self.validator.validate(ir)
        assert result.valid == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
