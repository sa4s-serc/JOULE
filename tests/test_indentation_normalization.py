"""
Tests for indentation normalization in LLMMutatorBase.

These tests verify that the indentation normalization handles all common
issues that can occur with LLM-generated code.
"""

import pytest

from src.application.mutators.semantic_base import LLMMutatorBase
from src.infrastructure.parsing.python_parser import PythonParser


class MockLLM:
    """Mock LLM client for testing."""

    def complete(self, prompt, stop=None):
        return ""


class TestMutator(LLMMutatorBase):
    """Test mutator to access protected methods."""

    def mutate(self, ir):
        pass


class TestIndentationNormalization:
    """Test suite for indentation normalization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mutator = TestMutator(MockLLM())
        self.parser = PythonParser()

    def test_tabs_to_spaces(self):
        """Test that tabs are converted to 4 spaces."""
        code = "def example():\n\tif True:\n\t\treturn 1"
        normalized = self.mutator._normalize_indentation(code)

        assert "\t" not in normalized
        assert "    if True:" in normalized
        assert "        return 1" in normalized

    def test_inconsistent_indentation(self):
        """Test that inconsistent indentation is normalized."""
        code = """def example():
    if True:
        return 1
    else:
        return 0"""

        normalized = self.mutator._normalize_indentation(code)

        # Should be parseable (which is the main goal)
        ir = self.parser.parse(normalized)
        assert ir is not None

    def test_invalid_unindent_level(self):
        """Test that invalid unindent levels are snapped to valid levels."""
        code = """def example():
    if True:
        x = 1
      y = 2"""  # 6 spaces - invalid

        normalized = self.mutator._normalize_indentation(code)
        lines = normalized.split("\n")

        # Should snap to 4 spaces (the valid level)
        assert lines[3].startswith("    y")

    def test_else_statement_alignment(self):
        """Test that else statements align with their if statements."""
        code = """def example():
    if True:
        return 1
    else:
        return 0"""

        normalized = self.mutator._normalize_indentation(code)

        # Should be parseable
        ir = self.parser.parse(normalized)
        assert ir is not None

    def test_elif_statement_alignment(self):
        """Test that elif statements align with their if statements."""
        code = """def example(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    else:
        return 0"""

        normalized = self.mutator._normalize_indentation(code)

        # Should be parseable
        ir = self.parser.parse(normalized)
        assert ir is not None

    def test_try_except_alignment(self):
        """Test that except/finally align with try."""
        code = """def example():
    try:
        x = 1
    except:
        pass
    finally:
        pass"""

        normalized = self.mutator._normalize_indentation(code)

        # Should be parseable
        ir = self.parser.parse(normalized)
        assert ir is not None

    def test_empty_lines_preserved(self):
        """Test that empty lines are preserved."""
        code = """def example():
    x = 1

    y = 2"""

        normalized = self.mutator._normalize_indentation(code)
        lines = normalized.split("\n")

        assert lines[2] == ""  # Empty line preserved

    def test_fix_empty_blocks(self):
        """Test that empty blocks get pass statements."""
        code = """def example():
    if True:
    else:
        return 0"""

        fixed = self.mutator._fix_common_syntax_errors(code)

        assert "pass" in fixed

    def test_clean_code_with_markdown(self):
        """Test that markdown code blocks are extracted and normalized."""
        response = """```python
def example():
\tif True:
\t\treturn 1
```"""

        cleaned = self.mutator._clean_code(response)

        # Should extract code and normalize indentation
        assert "```" not in cleaned
        assert "\t" not in cleaned
        assert "    if True:" in cleaned

    def test_safe_parse_with_bad_indentation(self):
        """Test that safe_parse can handle and fix bad indentation."""
        code = """def example():
  if True:
      return 1"""

        ir = self.mutator._safe_parse(code)

        # Should successfully parse after normalization
        assert ir is not None

    def test_complex_nested_structure(self):
        """Test normalization of complex nested structures."""
        code = """def example():
    for i in range(10):
        if i % 2 == 0:
            try:
                x = i / 2
            except:
                pass
        else:
            continue"""

        normalized = self.mutator._normalize_indentation(code)

        # Should be parseable
        ir = self.parser.parse(normalized)
        assert ir is not None

    def test_mixed_tabs_and_spaces(self):
        """Test handling of mixed tabs and spaces."""
        code = "def example():\n\tif True:\n    \treturn 1"  # Tab, then spaces+tab

        normalized = self.mutator._normalize_indentation(code)

        assert "\t" not in normalized
        # Should be parseable
        ir = self.parser.parse(normalized)
        assert ir is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
