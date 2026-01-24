"""
Comprehensive Test Suite for IR Schema

Tests the strict IR schema definition and all node types.
"""

import pytest

from src.domain.ir.schema import (Assign, BinaryOp, Block, Call, Compare,
                                  Constant, DictExpr, For, FunctionDef, If,
                                  ListExpr, Module, Name, Return)


class TestIRSchema:
    """Test suite for IR schema nodes."""

    def test_constant_creation(self):
        """Test creating constant nodes."""
        # Integer
        const_int = Constant(value=42, kind="int")
        assert const_int.value == 42
        assert const_int.kind == "int"

        # String
        const_str = Constant(value="hello", kind="str")
        assert const_str.value == "hello"
        assert const_str.kind == "str"

        # Boolean
        const_bool = Constant(value=True, kind="bool")
        assert const_bool.value == True
        assert const_bool.kind == "bool"

    def test_name_creation(self):
        """Test creating name nodes."""
        name = Name(id="variable", ctx="Load")
        assert name.id == "variable"
        assert name.ctx == "Load"

        name_store = Name(id="x", ctx="Store")
        assert name_store.ctx == "Store"

    def test_binary_op_creation(self):
        """Test creating binary operation nodes."""
        left = Constant(value=1, kind="int")
        right = Constant(value=2, kind="int")
        binop = BinaryOp(left=left, op="+", right=right)

        assert binop.op == "+"
        assert isinstance(binop.left, Constant)
        assert isinstance(binop.right, Constant)

    def test_function_def_creation(self):
        """Test creating function definition nodes."""
        func = FunctionDef(
            name="test_func",
            args=["a", "b"],
            body=Block(statements=[Return(value=Constant(value=None, kind="None"))]),
        )

        assert func.name == "test_func"
        assert len(func.args) == 2
        assert len(func.body.statements) == 1

    def test_assign_creation(self):
        """Test creating assignment nodes."""
        assign = Assign(targets=[Name(id="x", ctx="Store")], value=Constant(value=10, kind="int"))

        assert len(assign.targets) == 1
        assert isinstance(assign.value, Constant)

    def test_if_statement_creation(self):
        """Test creating if statement nodes."""
        if_stmt = If(
            test=Compare(
                left=Name(id="x", ctx="Load"),
                ops=[">"],
                comparators=[Constant(value=0, kind="int")],
            ),
            body=Block(statements=[Return(value=Constant(value=True, kind="bool"))]),
            orelse=Block(statements=[Return(value=Constant(value=False, kind="bool"))]),
        )

        assert isinstance(if_stmt.test, Compare)
        assert len(if_stmt.body.statements) == 1
        assert if_stmt.orelse is not None

    def test_for_loop_creation(self):
        """Test creating for loop nodes."""
        for_loop = For(
            target=Name(id="i", ctx="Store"),
            iter=Call(
                func=Name(id="range", ctx="Load"),
                args=[Constant(value=10, kind="int")],
                keywords=[],
            ),
            body=Block(statements=[]),
        )

        assert isinstance(for_loop.target, Name)
        assert isinstance(for_loop.iter, Call)

    def test_module_creation(self):
        """Test creating module nodes."""
        module = Module(
            body=Block(
                statements=[
                    FunctionDef(
                        name="main",
                        args=[],
                        body=Block(statements=[Return(value=Constant(value=0, kind="int"))]),
                    )
                ]
            )
        )

        assert len(module.body.statements) == 1
        assert isinstance(module.body.statements[0], FunctionDef)

    def test_nested_expressions(self):
        """Test nested expression structures."""
        # (1 + 2) * 3
        expr = BinaryOp(
            left=BinaryOp(
                left=Constant(value=1, kind="int"), op="+", right=Constant(value=2, kind="int")
            ),
            op="*",
            right=Constant(value=3, kind="int"),
        )

        assert isinstance(expr.left, BinaryOp)
        assert expr.op == "*"

    def test_list_expr_creation(self):
        """Test creating list expressions."""
        list_expr = ListExpr(
            elts=[
                Constant(value=1, kind="int"),
                Constant(value=2, kind="int"),
                Constant(value=3, kind="int"),
            ],
            ctx="Load",
        )

        assert len(list_expr.elts) == 3
        assert all(isinstance(e, Constant) for e in list_expr.elts)

    def test_dict_expr_creation(self):
        """Test creating dict expressions."""
        dict_expr = DictExpr(
            keys=[Constant(value="a", kind="str"), Constant(value="b", kind="str")],
            values=[Constant(value=1, kind="int"), Constant(value=2, kind="int")],
        )

        assert len(dict_expr.keys) == 2
        assert len(dict_expr.values) == 2

    def test_pydantic_validation(self):
        """Test that Pydantic validation works correctly."""
        # Valid node should not raise
        valid = Constant(value=1, kind="int")
        assert valid.value == 1

        # Invalid node should raise (testing runtime validation)
        with pytest.raises(Exception):
            # Missing required field
            invalid = BinaryOp(left=None, op="+")  # Missing 'right'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
