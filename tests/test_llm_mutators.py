from unittest.mock import MagicMock

from src.application.mutators.advanced_performance import \
    VectorizationOptimizer
from src.application.mutators.semantic_layer import AlgorithmicIntentMutator
from src.application.mutators.syntactic_layer import CodePatternOptimizer
from src.domain.ir import schema


class TestLLMMutators:

    def test_syntactic_mutation(self):
        # Initial: loops
        ir = schema.Module(body=schema.Block(statements=[schema.Pass()]))

        # Mock LLM returning list compr
        mock_llm = MagicMock()
        mock_llm.model_name = "gemini-flash"
        code_resp = "x = [i for i in range(10)]"
        mock_llm.complete.return_value = f"```python\n{code_resp}\n```"

        mutator = CodePatternOptimizer(llm_client=mock_llm)
        mutator.codegen.generate = MagicMock(return_value="x = []\nfor i in range(10): x.append(i)")

        # Mock parsing:
        parsed_ir = schema.Module(
            body=schema.Block(
                statements=[
                    schema.Assign(
                        targets=[schema.Name(id="x")],
                        value=schema.ListComp(elt=schema.Name(id="i"), generators=[]),
                    )
                ]
            )
        )

        # Let's mock _safe_parse directly to return a valid IR
        mutator._safe_parse = MagicMock(return_value=parsed_ir)
        mutator._get_imports = MagicMock(return_value=set())  # No new imports

        variants = mutator.mutate(ir)
        assert len(variants) > 0
        # Check if any variant has the expected strategy prefix
        assert any("Pattern" in name for _, name in variants)

    def test_vectorization_optimization(self):
        """Test vectorization optimizer (now IR-based)."""
        ir = schema.Module(
            body=schema.Block(
                statements=[
                    schema.For(
                        target=schema.Name(id="i"),
                        iter=schema.Call(
                            func=schema.Name(id="range"),
                            args=[
                                schema.Call(func=schema.Name(id="len"), args=[schema.Name(id="A")])
                            ],
                        ),
                        body=schema.Block(
                            statements=[
                                schema.Assign(
                                    targets=[
                                        schema.Subscript(
                                            value=schema.Name(id="C"),
                                            slice=schema.Name(id="i"),
                                            ctx="Store",
                                        )
                                    ],
                                    value=schema.BinaryOp(
                                        left=schema.Subscript(
                                            value=schema.Name(id="A"),
                                            slice=schema.Name(id="i"),
                                            ctx="Load",
                                        ),
                                        op="+",
                                        right=schema.Subscript(
                                            value=schema.Name(id="B"),
                                            slice=schema.Name(id="i"),
                                            ctx="Load",
                                        ),
                                    ),
                                )
                            ]
                        ),
                    )
                ]
            )
        )

        mutator = VectorizationOptimizer()
        variants = mutator.mutate(ir)

        # Should be some variants (Numpy or Loop vectorization)
        assert len(variants) > 0

    def test_stdlib_mutation_rejects_numpy(self):
        ir = schema.Module(body=schema.Block(statements=[schema.Pass()]))
        mock_llm = MagicMock()
        mock_llm.model_name = "gemini-flash"
        mock_llm.complete.return_value = "import numpy as np"

        mutator = AlgorithmicIntentMutator(llm_client=mock_llm)
        mutator.codegen.generate = MagicMock(return_value="pass")

        # Mock parser returning IR with numpy import
        new_ir = schema.Module(
            body=schema.Block(
                statements=[schema.Import(names=[schema.Alias(name="numpy", asname="np")])]
            )
        )
        mutator._safe_parse = MagicMock(return_value=new_ir)

        # Should be REJECTED because AlgorithmicIntentMutator is StdLib only
        variants = mutator.mutate(ir)
        assert len(variants) == 0
