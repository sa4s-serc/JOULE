"""
Comprehensive Test Suite for New IR-Only System

Tests error handling, edge cases, and end-to-end workflows.
"""

import pytest

from src.application.engine.evolution import EvolutionaryEngine
from src.application.mutators.syntactic_layer import PythonicIdiomOptimizer
from src.domain.ir.validators import IRValidator
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.execution.runner import GreenGymRunner
from src.infrastructure.parsing.python_parser import PythonParser


class TestEndToEndOptimization:
    """Test complete optimization workflows."""

    def test_basic_optimization(self):
        """Test basic optimization pipeline."""
        code = """
def add(a, b):
    return a + b
"""

        test_code = """
def test():
    assert candidate.add(2, 3) == 5
    assert candidate.add(0, 0) == 0
"""

        runner = GreenGymRunner(timeout_seconds=10)
        mutator = PythonicIdiomOptimizer()
        engine = EvolutionaryEngine(mutators=[mutator], runner=runner, config=None, llm_client=None)

        solutions = engine.optimize(code, test_code)

        # Should have at least baseline
        assert len(solutions) >= 1

        # All solutions should have IR and metrics
        for sol in solutions:
            assert sol.ir is not None
            assert sol.metrics is not None
            # metrics keys changed in some runners, check for any common metric
            assert any(
                k in sol.metrics for k in ["energy_joules", "duration_seconds", "time_seconds"]
            )

    def test_optimization_with_no_mutations(self):
        """Test when no mutations are possible."""
        code = """
def simple():
    x = 1
    y = 2
    return x + y
"""

        test_code = """
def test():
    assert candidate.simple() == 3
"""

        runner = GreenGymRunner(timeout_seconds=10)
        mutator = PythonicIdiomOptimizer()
        engine = EvolutionaryEngine(mutators=[mutator], runner=runner, config=None)

        solutions = engine.optimize(code, test_code)

        # Should at least have baseline
        assert len(solutions) >= 1


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_syntax(self):
        """Test handling of syntactically invalid code."""
        invalid_code = """
def broken_function(:
    return "syntax error"
"""

        test_code = """
def test():
    pass
"""

        runner = GreenGymRunner(timeout_seconds=5)
        mutator = PythonicIdiomOptimizer()
        engine = EvolutionaryEngine(mutators=[mutator], runner=runner, config=None)

        # Should return empty list, not crash
        solutions = engine.optimize(invalid_code, test_code)
        assert solutions == []

    def test_failing_baseline(self):
        """Test handling when baseline fails tests."""
        code = """
def buggy(x):
    return x + 1  # Wrong logic
"""

        test_code = """
def test():
    assert candidate.buggy(5) == 10  # Will fail
"""

        runner = GreenGymRunner(timeout_seconds=5)
        mutator = PythonicIdiomOptimizer()
        engine = EvolutionaryEngine(mutators=[mutator], runner=runner, config=None)

        solutions = engine.optimize(code, test_code)
        # Should return empty list as baseline fails
        assert solutions == []

    def test_timeout_handling(self):
        """Test handling of code that times out."""
        infinite_loop = """
def infinite():
    while True:
        pass
    return 1
"""

        test_code = """
def test():
    assert candidate.infinite() == 1
"""

        runner = GreenGymRunner(timeout_seconds=1)
        mutator = PythonicIdiomOptimizer()
        engine = EvolutionaryEngine(mutators=[mutator], runner=runner, config=None)

        solutions = engine.optimize(infinite_loop, test_code)
        # Should handle timeout gracefully
        assert solutions == []


class TestParserRobustness:
    """Test parser edge cases."""

    def setup_method(self):
        self.parser = PythonParser()

    def test_parse_whitespace_only(self):
        """Test parsing code with only whitespace."""
        code = """

        
"""
        ir = self.parser.parse(code)
        assert ir is not None
        assert len(ir.body.statements) == 0

    def test_parse_comments_only(self):
        """Test parsing code with only comments."""
        code = """
# This is a comment
# Another comment
"""
        ir = self.parser.parse(code)
        assert ir is not None
        assert len(ir.body.statements) == 0

    def test_parse_complex_expressions(self):
        """Test parsing complex nested expressions."""
        code = """
def complex_math(a, b, c):
    return (a + b) * c - (a ** 2) / (b + 1)
"""
        ir = self.parser.parse(code)
        assert ir is not None
        assert len(ir.body.statements) == 1

    def test_parse_list_comprehension(self):
        """Test parsing list comprehensions."""
        code = """
def squares(n):
    return [i * i for i in range(n) if i % 2 == 0]
"""
        ir = self.parser.parse(code)
        assert ir is not None


class TestCodeGeneratorRobustness:
    """Test code generator edge cases."""

    def setup_method(self):
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_round_trip_simple_function(self):
        """Test round-trip for simple function."""
        code = """
def test():
    x = 1
    return x
"""
        ir = self.parser.parse(code)
        generated = self.codegen.generate(ir)
        ir2 = self.parser.parse(generated)
        generated2 = self.codegen.generate(ir2)

        # Should be idempotent
        assert generated == generated2

    def test_round_trip_with_nested_structures(self):
        """Test round-trip with nested if/loops."""
        code = """
def nested(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                x = x - 1
    return x
"""
        ir = self.parser.parse(code)
        generated = self.codegen.generate(ir)

        # Should be valid Python
        self.parser.parse(generated)


class TestValidatorRobustness:
    """Test validator edge cases."""

    def setup_method(self):
        self.parser = PythonParser()
        self.validator = IRValidator()

    def test_validate_empty_module(self):
        """Test validating empty module."""
        code = "# Just a comment"
        ir = self.parser.parse(code)
        result = self.validator.validate(ir)
        assert result.valid

    def test_validate_multiple_functions(self):
        """Test validating multiple functions."""
        code = """
def func1():
    return 1

def func2():
    return 2

def func3():
    return 3
"""
        ir = self.parser.parse(code)
        result = self.validator.validate(ir)
        assert result.valid

    def test_detect_duplicate_functions(self):
        """Test detection of duplicate function names."""
        code = """
def test():
    return 1

def test():
    return 2
"""
        ir = self.parser.parse(code)
        result = self.validator.validate(ir)
        assert not result.valid
        assert any("Duplicate" in err for err in result.errors)


class TestMutatorRobustness:
    """Test mutator edge cases."""

    def setup_method(self):
        self.parser = PythonParser()
        self.mutator = PythonicIdiomOptimizer()

    def test_mutate_single_statement(self):
        """Test mutating function with single statement."""
        code = """
def simple():
    return 1
"""
        ir = self.parser.parse(code)
        variants = self.mutator.mutate(ir)

        # May or may not produce variants (single statement can't be reordered)
        assert isinstance(variants, list)

    def test_mutate_preserves_structure(self):
        """Test that mutations preserve valid structure."""
        code = """
def test(a, b):
    x = a + b
    y = x * 2
    return y
"""
        ir = self.parser.parse(code)
        variants = self.mutator.mutate(ir)

        # All variants should be valid
        codegen = PythonCodeGenerator()
        for variant_ir, name in variants:
            generated = codegen.generate(variant_ir)
            # Should be parseable
            self.parser.parse(generated)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
