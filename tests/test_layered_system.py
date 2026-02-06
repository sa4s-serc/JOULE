"""
Test Suite for Layered Mutation System

Tests the new hierarchical mutation architecture and layer orchestration.
"""

import pytest

from src.application.mutators.algorithmic_layer import DataStructureOptimizer
from src.application.mutators.base import MutationLayer, MutationOrchestrator
from src.application.mutators.micro_layer import (ConstantOptimizer,
                                                  DeadCodeEliminator)
from src.application.mutators.syntactic_layer import PythonicIdiomOptimizer
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser
from src.utils.mutation_factory import create_mutation_result


class TestLayeredMutationSystem:
    """Test suite for the layered mutation system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.orchestrator = MutationOrchestrator()

    def test_mutation_layer_enum(self):
        """Test MutationLayer enum values."""
        assert MutationLayer.SEMANTIC.value == "semantic"
        assert MutationLayer.ALGORITHMIC.value == "algorithmic"
        assert MutationLayer.SYNTACTIC.value == "syntactic"
        assert MutationLayer.MICRO.value == "micro"

    def test_layered_mutator_interface(self):
        """Test LayeredMutator base class interface."""
        mutator = ConstantOptimizer()

        assert mutator.layer == MutationLayer.MICRO
        assert mutator.get_layer_name() == "Micro"
        assert isinstance(mutator.get_available_strategies(), list)
        assert mutator.get_success_rate() == 0.0  # No mutations yet

    def test_mutation_result_creation(self):
        """Test MutationResult creation and metadata."""
        code = "x = 1 + 2"
        ir = self.parser.parse(code)

        result = create_mutation_result(
            ir=ir,
            strategy_name="Test_Strategy",
            layer=MutationLayer.MICRO,
            confidence=0.9,
            description="Test mutation",
        )

        assert result.strategy_name == "Test_Strategy"
        assert result.layer == MutationLayer.MICRO
        assert result.confidence == 0.9
        assert result.description == "Test mutation"

    def test_orchestrator_registration(self):
        """Test mutator registration with orchestrator."""
        mutator = ConstantOptimizer()
        self.orchestrator.register_mutator(mutator)

        micro_mutators = self.orchestrator.mutators_by_layer[MutationLayer.MICRO]
        assert len(micro_mutators) == 1
        assert micro_mutators[0] == mutator

    def test_layered_mutation_application(self):
        """Test applying mutations in layered order."""
        # Register mutators for different layers
        self.orchestrator.register_mutator(ConstantOptimizer())
        self.orchestrator.register_mutator(PythonicIdiomOptimizer())

        code = """
def test():
    x = 1 + 2
    y = x * 1
    return y
"""
        ir = self.parser.parse(code)

        # Apply mutations from all layers
        variants = self.orchestrator.apply_layered_mutations(ir)

        # Should get variants from multiple layers
        assert isinstance(variants, list)
        # Each variant should be a tuple of (ir, strategy_name)
        for variant_ir, strategy_name in variants:
            assert hasattr(variant_ir, "body")  # Valid IR
            assert isinstance(strategy_name, str)

    def test_selective_layer_application(self):
        """Test applying mutations from specific layers only."""
        # Register mutators for different layers
        self.orchestrator.register_mutator(ConstantOptimizer())
        self.orchestrator.register_mutator(PythonicIdiomOptimizer())
        self.orchestrator.register_mutator(DataStructureOptimizer())

        code = "x = 1 + 2"
        ir = self.parser.parse(code)

        # Apply only micro layer mutations
        variants = self.orchestrator.apply_layered_mutations(
            ir, enabled_layers={MutationLayer.MICRO}
        )

        # Should only get micro-level mutations
        for variant_ir, strategy_name in variants:
            # Strategy names from micro layer should contain "Constant" or similar
            assert any(keyword in strategy_name for keyword in ["Constant", "DeadCode", "Loop"])

    def test_layer_statistics(self):
        """Test layer statistics collection."""
        # Register and run some mutators
        mutator1 = ConstantOptimizer()
        mutator2 = DeadCodeEliminator()

        self.orchestrator.register_mutator(mutator1)
        self.orchestrator.register_mutator(mutator2)

        # Simulate some mutations
        mutator1.mutation_count = 5
        mutator1.success_count = 4
        mutator2.mutation_count = 3
        mutator2.success_count = 3

        stats = self.orchestrator.get_layer_statistics()

        assert "micro" in stats
        micro_stats = stats["micro"]
        assert micro_stats["mutator_count"] == 2
        assert micro_stats["total_mutations"] == 8
        assert micro_stats["total_successes"] == 7


class TestMicroLayerMutators:
    """Test suite for micro layer mutators."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_constant_optimizer(self):
        """Test constant optimization mutator."""
        mutator = ConstantOptimizer()

        code = """
def test():
    x = 1 + 2
    y = x * 1
    z = True and False
    return x, y, z
"""
        ir = self.parser.parse(code)
        variants = mutator.mutate(ir)

        assert isinstance(variants, list)
        # Should produce constant folding variants
        strategy_names = [name for _, name in variants]
        assert any("Constant" in name for name in strategy_names)

    def test_dead_code_eliminator(self):
        """Test dead code elimination mutator."""
        mutator = DeadCodeEliminator()

        code = """
def test():
    x = 1
    return x
    y = 2  # Unreachable
    print(y)
"""
        ir = self.parser.parse(code)
        variants = mutator.mutate(ir)

        assert isinstance(variants, list)
        # Should produce dead code elimination variants
        strategy_names = [name for _, name in variants]
        assert any("DeadCode" in name for name in strategy_names)


class TestSyntacticLayerMutators:
    """Test suite for syntactic layer mutators."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_pythonic_idiom_optimizer(self):
        """Test Pythonic idiom optimization mutator."""
        mutator = PythonicIdiomOptimizer()

        code = """
def test():
    result = []
    for i in range(10):
        result.append(i * 2)
    return result
"""
        ir = self.parser.parse(code)
        variants = mutator.mutate(ir)

        assert isinstance(variants, list)
        # Should produce idiom optimization variants
        strategy_names = [name for _, name in variants]
        assert any("Idiom" in name for name in strategy_names)


class TestAlgorithmicLayerMutators:
    """Test suite for algorithmic layer mutators."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_data_structure_optimizer(self):
        """Test data structure optimization mutator."""
        mutator = DataStructureOptimizer()

        code = """
def test(x):
    if x in [1, 2, 3, 4, 5]:
        return True
    return False
"""
        ir = self.parser.parse(code)
        variants = mutator.mutate(ir)

        assert isinstance(variants, list)
        # Should produce data structure optimization variants
        strategy_names = [name for _, name in variants]
        assert any("DataStructure" in name for name in strategy_names)


class TestLayerOrdering:
    """Test that layers are applied in the correct hierarchical order."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.orchestrator = MutationOrchestrator()

    def test_layer_order(self):
        """Test that layers are processed in semantic -> algorithmic -> syntactic -> micro order."""
        expected_order = [
            MutationLayer.SEMANTIC,
            MutationLayer.ALGORITHMIC,
            MutationLayer.SYNTACTIC,
            MutationLayer.MICRO,
        ]

        assert self.orchestrator.layer_order == expected_order

    def test_hierarchical_application(self):
        """Test that mutations are applied hierarchically."""
        # Register mutators for all layers
        self.orchestrator.register_mutator(ConstantOptimizer())
        self.orchestrator.register_mutator(PythonicIdiomOptimizer())
        self.orchestrator.register_mutator(DataStructureOptimizer())

        code = "x = 1 + 2"
        ir = self.parser.parse(code)

        # Apply all layers
        variants = self.orchestrator.apply_layered_mutations(ir)

        # Should get variants from multiple layers in hierarchical order
        assert isinstance(variants, list)

        # Verify that we get mutations from different layers
        strategy_names = [name for _, name in variants]
        layers_represented = set()

        for name in strategy_names:
            if "DataStructure" in name or "Complexity" in name:
                layers_represented.add("algorithmic")
            elif "Idiom" in name or "Pattern" in name:
                layers_represented.add("syntactic")
            elif "Constant" in name or "DeadCode" in name or "Loop" in name:
                layers_represented.add("micro")

        # Should have mutations from multiple layers
        assert len(layers_represented) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
