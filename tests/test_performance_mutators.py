import pytest
import copy
from src.domain.ir import schema
from src.application.mutators.micro_layer import (
    ConstantOptimizer, 
    DeadCodeEliminator,
    LoopMicroOptimizer,
    LoopStrengthReducer
)
from src.application.mutators.algorithmic_layer import (
    MembershipOptimizationTransformer
)

class TestPerformanceMutators:
    
    def test_constant_folding(self):
        # 2 + 3 -> 5
        ir = schema.Module(body=schema.Block(statements=[
            schema.ExprStmt(value=schema.BinaryOp(
                left=schema.Constant(value=2, kind="int"),
                op="+",
                right=schema.Constant(value=3, kind="int")
            ))
        ]))
        
        mutator = ConstantOptimizer()
        variants = mutator.mutate(ir)
        assert len(variants) >= 1
        new_ir = variants[0][0]  # Unpack tuple (ir, metadata)
        expr = new_ir.body.statements[0].value
        assert isinstance(expr, schema.Constant)
        assert expr.value == 5
        
    def test_dead_code_elimination(self):
        # return; a = 1
        ir = schema.Module(body=schema.Block(statements=[
            schema.Return(value=None),
            schema.Assign(targets=[schema.Name(id="a")], value=schema.Constant(value=1, kind="int"))
        ]))
        
        mutator = DeadCodeEliminator()
        variants = mutator.mutate(ir)
        assert len(variants) >= 1
        new_ir = variants[0][0]  # Unpack tuple (ir, metadata)
        assert len(new_ir.body.statements) == 1
        assert isinstance(new_ir.body.statements[0], schema.Return)

    def test_strength_reduction_transformer(self):
        # x ** 2 -> x * x
        binop = schema.BinaryOp(
            left=schema.Name(id="x"),
            op="**",
            right=schema.Constant(value=2, kind="int")
        )
        
        transformer = LoopStrengthReducer()
        new_node = transformer.visit_BinaryOp(binop)
        
        assert new_node.op == "*"
        # LoopStrengthReducer returns x * x, check structure
        assert isinstance(new_node, schema.BinaryOp)
        assert isinstance(new_node.left, schema.Name) and new_node.left.id == "x"
        assert isinstance(new_node.right, schema.Name) and new_node.right.id == "x"

    def test_fast_membership_transformer(self):
        # x in [1, 2] -> x in {1, 2}
        compare = schema.Compare(
            left=schema.Name(id="x"),
            ops=["in"],
            comparators=[schema.ListExpr(elts=[
                schema.Constant(value=1, kind="int"),
                schema.Constant(value=2, kind="int")
            ])]
        )
        
        transformer = MembershipOptimizationTransformer()
        new_node = transformer.generic_visit(compare) # Membership uses generic_visit or specific visitor?
        # Check source: MembershipOptimizationTransformer usually visits Compare
        # If I need to call specific visitor, I can use visit(compare)
        new_node = transformer.visit(compare)
        
        assert isinstance(new_node.comparators[0], schema.SetExpr)
