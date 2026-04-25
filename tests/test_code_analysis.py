from __future__ import annotations

import ast
import pytest
from typing import Any

from joule.utils.code_analysis import (
    CodeBlock,
    CodeBlockType,
    FunctionAnalyzer,
    LineProfilerMapper,
    analyze_function_ast,
    map_line_profiler_to_blocks,
    get_function_line_range,
)


def sample_function_simple(x: int) -> int:
    """A simple function for testing."""
    result = x * 2
    if x > 10:
        result = x * 3
    return result


def sample_function_with_loops(items: list[int]) -> list[int]:
    """A function with loops for testing."""
    results = []
    for item in items:
        if item > 5:
            results.append(item * 2)
        else:
            results.append(item)
    return results


def sample_function_nested(data: dict[str, list[int]]) -> dict[str, int]:
    """A function with nested loops."""
    totals = {}
    for key, values in data.items():
        total = 0
        for v in values:
            total += v
        totals[key] = total
    return totals


def sample_function_try_except() -> int:
    """A function with try/except."""
    try:
        result = 1 / 1
    except ZeroDivisionError:
        result = 0
    finally:
        cleanup = True
    return result


class TestCodeBlock:
    def test_contains_line(self) -> None:
        block = CodeBlock(
            block_type=CodeBlockType.FOR_LOOP,
            line_start=10,
            line_end=20,
            description="for x in y:",
        )
        assert block.contains_line(10)
        assert block.contains_line(15)
        assert block.contains_line(20)
        assert not block.contains_line(9)
        assert not block.contains_line(21)

    def test_add_child(self) -> None:
        parent = CodeBlock(
            block_type=CodeBlockType.FOR_LOOP,
            line_start=10,
            line_end=20,
            description="for x in y:",
            nesting_level=0,
        )
        child = CodeBlock(
            block_type=CodeBlockType.IF_BRANCH,
            line_start=12,
            line_end=15,
            description="if x > 0:",
            nesting_level=0,
        )
        parent.add_child(child)

        assert child.parent_block == parent
        assert child.nesting_level == 1
        assert len(parent.child_blocks) == 1


class TestFunctionAnalyzer:
    def test_analyze_simple_function(self) -> None:
        blocks = analyze_function_ast(sample_function_simple)

        # Should find assignment and if statement
        assert len(blocks) >= 2

        # Check for assignment
        assignments = [b for b in blocks if b.block_type == CodeBlockType.ASSIGNMENT]
        assert len(assignments) >= 1

        # Check for if statement
        if_blocks = [b for b in blocks if b.block_type == CodeBlockType.IF_BRANCH]
        assert len(if_blocks) == 1

    def test_analyze_function_with_loops(self) -> None:
        blocks = analyze_function_ast(sample_function_with_loops)

        # Should find for loop and if statement
        for_blocks = [b for b in blocks if b.block_type == CodeBlockType.FOR_LOOP]
        assert len(for_blocks) == 1
        assert "for item in items:" in for_blocks[0].description

        if_blocks = [b for b in blocks if b.block_type == CodeBlockType.IF_BRANCH]
        assert len(if_blocks) == 1

        # Check for else block
        else_blocks = [b for b in blocks if b.block_type == CodeBlockType.ELSE_BRANCH]
        assert len(else_blocks) == 1

    def test_analyze_nested_loops(self) -> None:
        blocks = analyze_function_ast(sample_function_nested)

        # Should find two for loops
        for_blocks = [b for b in blocks if b.block_type == CodeBlockType.FOR_LOOP]
        assert len(for_blocks) == 2

        # Check nesting levels
        outer_loop = for_blocks[0]
        inner_loop = for_blocks[1]
        assert outer_loop.nesting_level == 0
        assert inner_loop.nesting_level == 1

    def test_analyze_try_except(self) -> None:
        blocks = analyze_function_ast(sample_function_try_except)

        # Should find try block
        try_blocks = [b for b in blocks if b.block_type == CodeBlockType.TRY_BLOCK]
        assert len(try_blocks) == 1

        # Should find except block
        except_blocks = [b for b in blocks if b.block_type == CodeBlockType.EXCEPT_BLOCK]
        assert len(except_blocks) == 1

        # Should find finally block
        finally_blocks = [b for b in blocks if b.block_type == CodeBlockType.FINALLY_BLOCK]
        assert len(finally_blocks) == 1

    def test_get_function_line_range(self) -> None:
        start, end = get_function_line_range(sample_function_simple)

        # Should return valid line numbers
        assert start > 0
        assert end > start
        assert end - start < 100  # Function should be less than 100 lines


class TestLineProfilerMapper:
    def test_map_line_stats_basic(self) -> None:
        code_blocks = [
            CodeBlock(
                block_type=CodeBlockType.FOR_LOOP,
                line_start=10,
                line_end=15,
                description="for x in y:",
            ),
            CodeBlock(
                block_type=CodeBlockType.IF_BRANCH,
                line_start=12,
                line_end=14,
                description="if x > 0:",
            ),
        ]

        line_stats = {
            10: (100, 0.5),  # Loop start
            11: (100, 0.4),  # Loop body
            12: (50, 0.2),   # If statement
            13: (50, 0.1),   # If body
        }

        mapper = LineProfilerMapper(code_blocks)
        result = mapper.map_line_stats(line_stats)

        # Should have aggregated stats
        assert len(result) == 2

        # Loop should have higher time
        loop_result = [r for r in result if r["type"] == "for_loop"][0]
        assert loop_result["hits"] > 0
        assert loop_result["time_s"] > 0

    def test_map_line_stats_nested_preference(self) -> None:
        # Test that inner blocks take precedence over outer blocks
        code_blocks = [
            CodeBlock(
                block_type=CodeBlockType.FOR_LOOP,
                line_start=10,
                line_end=20,
                description="outer loop",
            ),
            CodeBlock(
                block_type=CodeBlockType.IF_BRANCH,
                line_start=12,
                line_end=15,
                description="inner if",
            ),
        ]

        line_stats = {
            12: (50, 0.3),  # Line in both blocks - should go to inner (smaller)
        }

        mapper = LineProfilerMapper(code_blocks)
        result = mapper.map_line_stats(line_stats)

        # The line should be assigned to the inner block
        if_result = [r for r in result if r["type"] == "if_branch"][0]
        assert if_result["hits"] == 50
        assert if_result["time_s"] == 0.3


class TestAnalyzeFunctionAst:
    def test_error_on_builtin(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            analyze_function_ast(len)  # Built-in function

    def test_error_on_lambda(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            analyze_function_ast(lambda x: x + 1)


class TestMapLineProfilerToBlocks:
    def test_integration(self) -> None:
        # Get real code blocks from a function
        blocks = analyze_function_ast(sample_function_simple)

        # Create sample line stats
        line_stats = {}
        for block in blocks:
            for line in range(block.line_start, block.line_end + 1):
                line_stats[line] = (10, 0.01)

        result = map_line_profiler_to_blocks(line_stats, blocks)

        # Should return enriched blocks
        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of result
        for item in result:
            assert "type" in item
            assert "line_range" in item
            assert "description" in item
            assert "hits" in item
            assert "time_s" in item


class TestBlockTypeCoverage:
    """Test that all block types can be properly identified."""

    def test_all_block_types_have_values(self) -> None:
        """Ensure all enum members have proper string values."""
        for block_type in CodeBlockType:
            assert isinstance(block_type.value, str)
            assert len(block_type.value) > 0

    def test_block_type_consistency(self) -> None:
        """Ensure block type values match expected patterns."""
        expected_patterns = {
            CodeBlockType.FOR_LOOP: "for_loop",
            CodeBlockType.WHILE_LOOP: "while_loop",
            CodeBlockType.IF_BRANCH: "if_branch",
            CodeBlockType.ELIF_BRANCH: "elif_branch",
            CodeBlockType.ELSE_BRANCH: "else_branch",
            CodeBlockType.ASSIGNMENT: "assignment",
            CodeBlockType.AUGMENTED_ASSIGNMENT: "augmented_assignment",
            CodeBlockType.CALL: "function_call",
        }

        for block_type, expected in expected_patterns.items():
            assert block_type.value == expected
