from src.application.mutators.advanced_performance import (
    CacheLocalityTransformer, InPlaceOperationsTransformer,
    LoopVectorizationTransformer, MemoryOptimizer,
    NumpyOptimizationTransformer)
from src.domain.ir import schema


class TestAdvancedPerformanceMutators:

    def test_numpy_optimization(self):
        # C[i] = A[i] + B[i] inside a for loop
        loop = schema.For(
            target=schema.Name(id="i"),
            iter=schema.Call(
                func=schema.Name(id="range"), args=[schema.Constant(value=10, kind="int")]
            ),
            body=schema.Block(
                statements=[
                    schema.Assign(
                        targets=[
                            schema.Subscript(value=schema.Name(id="C"), slice=schema.Name(id="i"))
                        ],
                        value=schema.BinaryOp(
                            left=schema.Subscript(
                                value=schema.Name(id="A"), slice=schema.Name(id="i")
                            ),
                            op="+",
                            right=schema.Subscript(
                                value=schema.Name(id="B"), slice=schema.Name(id="i")
                            ),
                        ),
                    )
                ]
            ),
            orelse=schema.Block(statements=[]),
        )

        transformer = NumpyOptimizationTransformer()
        new_node = transformer.visit(loop)

        assert isinstance(new_node, schema.Assign)
        assert isinstance(new_node.value, schema.Call)
        assert new_node.value.func.attr == "add"
        assert new_node.value.func.value.id == "numpy"

    def test_in_place_optimization(self):
        # a = a + 1 -> a += 1
        assign = schema.Assign(
            targets=[schema.Name(id="a")],
            value=schema.BinaryOp(
                left=schema.Name(id="a"), op="+", right=schema.Constant(value=1, kind="int")
            ),
        )

        transformer = InPlaceOperationsTransformer()
        new_node = transformer.visit(assign)

        assert isinstance(new_node, schema.AugAssign)
        assert new_node.op == "+"
        assert new_node.value.value == 1

    def test_loop_vectorization_list_comp(self):
        # for i in range(10): res.append(A[i]) -> res = [A[i] for i in range(10)]
        loop = schema.For(
            target=schema.Name(id="i"),
            iter=schema.Call(
                func=schema.Name(id="range"), args=[schema.Constant(value=10, kind="int")]
            ),
            body=schema.Block(
                statements=[
                    schema.ExprStmt(
                        value=schema.Call(
                            func=schema.Attribute(value=schema.Name(id="res"), attr="append"),
                            args=[
                                schema.Subscript(
                                    value=schema.Name(id="A"), slice=schema.Name(id="i")
                                )
                            ],
                        )
                    )
                ]
            ),
            orelse=schema.Block(statements=[]),
        )

        transformer = LoopVectorizationTransformer()
        new_node = transformer.visit(loop)

        assert isinstance(new_node, schema.Assign)
        assert isinstance(new_node.value, schema.ListComp)
        assert new_node.targets[0].id == "res"

    def test_cache_locality_swap(self):
        # Simplified nested loop check
        # for i in range(N):
        #   for j in range(M):
        #     A[j][i] = 1
        inner_loop = schema.For(
            target=schema.Name(id="j"),
            iter=schema.Call(func=schema.Name(id="range"), args=[schema.Name(id="M")]),
            body=schema.Block(
                statements=[
                    schema.Assign(
                        targets=[
                            schema.Subscript(
                                value=schema.Subscript(
                                    value=schema.Name(id="A"), slice=schema.Name(id="j")
                                ),
                                slice=schema.Name(id="i"),
                            )
                        ],
                        value=schema.Constant(value=1, kind="int"),
                    )
                ]
            ),
            orelse=schema.Block(statements=[]),
        )

        outer_loop = schema.For(
            target=schema.Name(id="i"),
            iter=schema.Call(func=schema.Name(id="range"), args=[schema.Name(id="N")]),
            body=schema.Block(statements=[inner_loop]),
            orelse=schema.Block(statements=[]),
        )

        transformer = CacheLocalityTransformer()
        new_node = transformer.visit(outer_loop)

        # Should swap loops
        assert new_node.target.id == "j"
        assert isinstance(new_node.body.statements[0], schema.For)
        assert new_node.body.statements[0].target.id == "i"

    def test_mutator_integration(self):
        # Test that mutators return results
        ir = schema.Module(
            body=schema.Block(
                statements=[
                    schema.Assign(
                        targets=[schema.Name(id="a")],
                        value=schema.BinaryOp(
                            left=schema.Name(id="a"),
                            op="+",
                            right=schema.Constant(value=1, kind="int"),
                        ),
                    )
                ]
            )
        )

        mutator = MemoryOptimizer(enabled_strategies={"Memory_InPlaceOperations"})
        results = mutator._apply_ir_mutations(ir)
        assert len(results) > 0
        assert results[0].strategy_name == "Memory_InPlaceOperations"
