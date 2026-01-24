
import pytest
from unittest.mock import MagicMock
from src.application.mutators.semantic_layer import AlgorithmicIntentMutator
from src.domain.ir import schema

class TestSemanticConstraints:
    
    def test_reject_new_external_imports(self):
        # Initial IR: just "pass"
        ir = schema.Module(body=schema.Block(statements=[schema.Pass()]))
        
        # Mock LLM returning code with numpy import
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "import numpy as np\nnp.array([1,2,3])"
        
        mutator = AlgorithmicIntentMutator(llm_client=mock_llm)
        mutator.codegen.generate = MagicMock(return_value="pass")
        mutator.parser.parse = MagicMock(return_value=schema.Module(body=schema.Block(statements=[
            schema.Import(names=[schema.Alias(name="numpy", asname="np")]),
            schema.ExprStmt(value=schema.Call(func=schema.Attribute(value=schema.Name(id="np"), attr="array"), args=[], keywords=[]))
        ])))
        
        variants = mutator.mutate(ir)
        
        # Should obtain 0 variants because import numpy is not allowed
        assert len(variants) == 0

    def test_allow_stdlib_imports(self):
        # Initial IR: "pass"
        ir = schema.Module(body=schema.Block(statements=[schema.Pass()]))
        
        # Mock LLM returning code with math import (stdlib)
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "import math\nx = math.sqrt(4)"
        
        mutator = AlgorithmicIntentMutator(llm_client=mock_llm)
        mutator.codegen.generate = MagicMock(return_value="pass")
        mutator.parser.parse = MagicMock(return_value=schema.Module(body=schema.Block(statements=[
            schema.Import(names=[schema.Alias(name="math")]),
            schema.Assign(targets=[schema.Name(id="x")], value=schema.Call(func=schema.Attribute(value=schema.Name(id="math"), attr="sqrt"), args=[schema.Constant(value=4, kind="int")]))
        ])))
        
        variants = mutator.mutate(ir)
        
        # Should accept because math is stdlib
        assert len(variants) > 0
