"""
Test Suite for Crossover Operations

Tests the genetic programming crossover implementations.
"""

import pytest

from src.application.engine.crossover import (CrossoverManager,
                                              SemanticCrossover,
                                              SubtreeCrossover,
                                              UniformCrossover)
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


class TestCrossoverOperations:
    """Test suite for crossover operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_subtree_crossover(self):
        """Test subtree crossover operation."""
        code1 = """
def func1(x):
    return x + 1
"""
        code2 = """
def func2(y):
    return y * 2
"""

        ir1 = self.parser.parse(code1)
        ir2 = self.parser.parse(code2)

        crossover = SubtreeCrossover()
        offspring = crossover.crossover(ir1, ir2)

        # Should produce offspring (may be empty if crossover fails)
        assert isinstance(offspring, list)

        # If offspring produced, they should be valid IR
        for child in offspring:
            generated_code = self.codegen.generate(child)
            assert generated_code is not None

    def test_uniform_crossover(self):
        """Test uniform crossover operation."""
        code1 = """
def func1():
    x = 1
    y = 2
    return x + y
"""
        code2 = """
def func2():
    a = 3
    b = 4
    return a * b
"""

        ir1 = self.parser.parse(code1)
        ir2 = self.parser.parse(code2)

        crossover = UniformCrossover(mix_probability=0.5)
        offspring = crossover.crossover(ir1, ir2)

        # Should produce two offspring
        assert len(offspring) == 2

        # Offspring should be valid
        for child in offspring:
            generated_code = self.codegen.generate(child)
            assert generated_code is not None

    def test_semantic_crossover(self):
        """Test semantic crossover operation."""
        code1 = """
def add(x, y):
    return x + y

def multiply(x, y):
    return x * y
"""
        code2 = """
def add(a, b):
    return a + b + 1

def divide(x, y):
    return x / y
"""

        ir1 = self.parser.parse(code1)
        ir2 = self.parser.parse(code2)

        crossover = SemanticCrossover()
        offspring = crossover.crossover(ir1, ir2)

        # Should produce offspring
        assert isinstance(offspring, list)

        # Offspring should be valid
        for child in offspring:
            generated_code = self.codegen.generate(child)
            assert generated_code is not None

    def test_crossover_manager(self):
        """Test crossover manager."""
        code1 = """
def test1():
    return 1
"""
        code2 = """
def test2():
    return 2
"""

        ir1 = self.parser.parse(code1)
        ir2 = self.parser.parse(code2)

        manager = CrossoverManager()
        offspring = manager.perform_crossover(ir1, ir2)

        # Should produce offspring using random operator
        assert isinstance(offspring, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
