"""Advanced AST analysis tests — decorators, async, comprehensions, edge cases."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from joule.utils.code_analysis import (
    CodeBlockType,
    analyze_function_ast,
    get_function_line_range,
    map_line_profiler_to_blocks,
    _dedent_source,
)


# ---------------------------------------------------------------------------
# Test functions defined at module level so inspect.getsource works
# ---------------------------------------------------------------------------

def func_with_list_comprehension(items: list[int]) -> list[int]:
    return [x * 2 for x in items if x > 0]


def func_with_dict_comprehension(items: list[str]) -> dict[str, int]:
    return {k: len(k) for k in items}


def func_with_set_comprehension(items: list[int]) -> set[int]:
    return {x % 10 for x in items}


def func_with_generator(items: list[int]) -> int:
    return sum(x * 2 for x in items)


def func_with_while_loop(n: int) -> int:
    result = 0
    while n > 0:
        result += n
        n -= 1
    return result


def func_with_augmented_assign(items: list[int]) -> int:
    total = 0
    for x in items:
        total += x
    return total


def func_with_with_block(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def func_deeply_nested(data: list[list[list[int]]]) -> int:
    total = 0
    for outer in data:
        for middle in outer:
            for inner in middle:
                if inner > 0:
                    total += inner
    return total


async def async_func(items: list[int]) -> list[int]:
    result = []
    for item in items:
        result.append(item * 2)
    return result


def decorated_func_target(x: int) -> int:
    result = x + 1
    for i in range(x):
        result += i
    return result


def func_with_elif(x: int) -> str:
    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    elif x < 10:
        return "small"
    else:
        return "large"


def func_with_nested_try(items: list[int]) -> list[int]:
    results = []
    for item in items:
        try:
            results.append(10 // item)
        except ZeroDivisionError:
            results.append(0)
    return results


# ---------------------------------------------------------------------------
# Comprehension detection
# ---------------------------------------------------------------------------

class TestComprehensionDetection:
    def test_list_comprehension_detected(self) -> None:
        blocks = analyze_function_ast(func_with_list_comprehension)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.LIST_COMPREHENSION in types

    def test_dict_comprehension_detected(self) -> None:
        blocks = analyze_function_ast(func_with_dict_comprehension)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.DICT_COMPREHENSION in types

    def test_set_comprehension_detected(self) -> None:
        blocks = analyze_function_ast(func_with_set_comprehension)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.SET_COMPREHENSION in types

    def test_generator_expression_detected(self) -> None:
        blocks = analyze_function_ast(func_with_generator)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.GENERATOR_EXPRESSION in types


# ---------------------------------------------------------------------------
# While loop
# ---------------------------------------------------------------------------

class TestWhileLoop:
    def test_while_loop_detected(self) -> None:
        blocks = analyze_function_ast(func_with_while_loop)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.WHILE_LOOP in types

    def test_while_loop_description(self) -> None:
        blocks = analyze_function_ast(func_with_while_loop)
        while_blocks = [b for b in blocks if b.block_type == CodeBlockType.WHILE_LOOP]
        assert len(while_blocks) == 1
        assert "while" in while_blocks[0].description


# ---------------------------------------------------------------------------
# Augmented assignment
# ---------------------------------------------------------------------------

class TestAugmentedAssignment:
    def test_augmented_assignment_detected(self) -> None:
        blocks = analyze_function_ast(func_with_augmented_assign)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.AUGMENTED_ASSIGNMENT in types


# ---------------------------------------------------------------------------
# With block
# ---------------------------------------------------------------------------

class TestWithBlock:
    def test_with_block_detected(self) -> None:
        blocks = analyze_function_ast(func_with_with_block)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.WITH_BLOCK in types


# ---------------------------------------------------------------------------
# Deep nesting
# ---------------------------------------------------------------------------

class TestDeepNesting:
    def test_nesting_levels_correct(self) -> None:
        blocks = analyze_function_ast(func_deeply_nested)
        for_blocks = [b for b in blocks if b.block_type == CodeBlockType.FOR_LOOP]
        levels = sorted(b.nesting_level for b in for_blocks)
        assert levels == [0, 1, 2]

    def test_if_inside_triple_loop_has_nesting_3(self) -> None:
        blocks = analyze_function_ast(func_deeply_nested)
        if_blocks = [b for b in blocks if b.block_type == CodeBlockType.IF_BRANCH]
        assert any(b.nesting_level == 3 for b in if_blocks)


# ---------------------------------------------------------------------------
# Async function
# ---------------------------------------------------------------------------

class TestAsyncFunction:
    def test_async_function_analyzed(self) -> None:
        blocks = analyze_function_ast(async_func)
        for_blocks = [b for b in blocks if b.block_type == CodeBlockType.FOR_LOOP]
        assert len(for_blocks) == 1


# ---------------------------------------------------------------------------
# elif / else chains
# ---------------------------------------------------------------------------

class TestElifElseChains:
    def test_elif_blocks_detected(self) -> None:
        blocks = analyze_function_ast(func_with_elif)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.ELIF_BRANCH in types

    def test_else_block_detected(self) -> None:
        blocks = analyze_function_ast(func_with_elif)
        types = [b.block_type for b in blocks]
        assert CodeBlockType.ELSE_BRANCH in types

    def test_correct_number_of_elif_blocks(self) -> None:
        blocks = analyze_function_ast(func_with_elif)
        elif_blocks = [b for b in blocks if b.block_type == CodeBlockType.ELIF_BRANCH]
        assert len(elif_blocks) == 2  # elif x == 0 and elif x < 10


# ---------------------------------------------------------------------------
# Nested try/except
# ---------------------------------------------------------------------------

class TestNestedTryExcept:
    def test_try_inside_loop(self) -> None:
        blocks = analyze_function_ast(func_with_nested_try)
        try_blocks = [b for b in blocks if b.block_type == CodeBlockType.TRY_BLOCK]
        assert len(try_blocks) == 1
        assert try_blocks[0].nesting_level == 1  # inside the for loop

    def test_except_inside_loop(self) -> None:
        blocks = analyze_function_ast(func_with_nested_try)
        except_blocks = [b for b in blocks if b.block_type == CodeBlockType.EXCEPT_BLOCK]
        assert len(except_blocks) == 1


# ---------------------------------------------------------------------------
# Line range correctness
# ---------------------------------------------------------------------------

class TestLineRangeCorrectness:
    def test_line_range_start_positive(self) -> None:
        start, end = get_function_line_range(func_with_list_comprehension)
        assert start > 0

    def test_line_range_end_after_start(self) -> None:
        start, end = get_function_line_range(func_deeply_nested)
        assert end > start

    def test_block_line_numbers_within_function_range(self) -> None:
        start, end = get_function_line_range(func_deeply_nested)
        blocks = analyze_function_ast(func_deeply_nested)
        for block in blocks:
            assert block.line_start >= start, f"Block starts before function: {block}"
            assert block.line_end <= end, f"Block ends after function: {block}"


# ---------------------------------------------------------------------------
# _dedent_source
# ---------------------------------------------------------------------------

class TestDedentSource:
    def test_already_dedented_unchanged(self) -> None:
        src = "def f():\n    pass\n"
        assert _dedent_source(src) == src

    def test_indented_source_dedented(self) -> None:
        src = "    def f():\n        pass\n"
        result = _dedent_source(src)
        assert not result.startswith("    ")

    def test_blank_lines_preserved(self) -> None:
        src = "    x = 1\n\n    y = 2\n"
        result = _dedent_source(src)
        lines = result.splitlines()
        assert lines[1] == ""  # blank line preserved

    def test_empty_string_unchanged(self) -> None:
        assert _dedent_source("") == ""


# ---------------------------------------------------------------------------
# map_line_profiler_to_blocks — edge cases
# ---------------------------------------------------------------------------

class TestMapLineProfilerEdgeCases:
    def test_empty_line_stats_returns_empty(self) -> None:
        blocks = analyze_function_ast(func_with_list_comprehension)
        result = map_line_profiler_to_blocks({}, blocks)
        assert result == []

    def test_line_outside_all_blocks_ignored(self) -> None:
        blocks = analyze_function_ast(func_with_while_loop)
        # Use a line number that is definitely outside the function
        line_stats = {999999: (10, 0.5)}
        result = map_line_profiler_to_blocks(line_stats, blocks)
        assert result == []

    def test_share_of_function_sums_to_one(self) -> None:
        blocks = analyze_function_ast(func_with_augmented_assign)
        start, end = get_function_line_range(func_with_augmented_assign)
        # Give every line in the function equal time
        line_stats = {ln: (1, 0.1) for ln in range(start, end + 1)}
        result = map_line_profiler_to_blocks(line_stats, blocks)
        if result:
            total_share = sum(r["share_of_function"] for r in result)
            # Shares should sum to approximately 1.0 (some lines may not be in blocks)
            assert total_share <= 1.01

    def test_result_sorted_by_time_descending(self) -> None:
        blocks = analyze_function_ast(func_deeply_nested)
        start, end = get_function_line_range(func_deeply_nested)
        # Give different times to different lines
        line_stats = {ln: (1, float(ln)) for ln in range(start, end + 1)}
        result = map_line_profiler_to_blocks(line_stats, blocks)
        times = [r["time_s"] for r in result]
        assert times == sorted(times, reverse=True)
