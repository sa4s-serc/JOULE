"""
Generates pytest harness files for each wrapped snippet.

The test must:
1. Be discoverable by joule as a workload (importable, callable)
2. Call the target function so joule can measure it
3. Provide mock stdin for tiers A and B
4. Not assert correctness (joule's correctness gate handles this separately)
"""

from harness.stdin_mocker import (
    format_mock_stdin_as_python_list,
    generate_mock_stdin,
)


_TEST_TEMPLATE_CLEAN = '''\
"""Auto-generated joule workload test for snippet {unique_index}."""
import pytest
from target import {fn_name}


def test_{fn_name}():
    """Joule workload: exercise {fn_name} for energy/time measurement."""
    {fn_name}()
'''

_TEST_TEMPLATE_STDIN_A = '''\
"""Auto-generated joule workload test for snippet {unique_index} (tier A)."""
import pytest
from target import {fn_name}, _reset_mock_stdin


_MOCK_LINES = {mock_lines}


def test_{fn_name}():
    """Joule workload: exercise {fn_name} with mocked stdin."""
    _reset_mock_stdin(_MOCK_LINES)
    {fn_name}()
'''

_TEST_TEMPLATE_STDIN_B = '''\
"""Auto-generated joule workload test for snippet {unique_index} (tier B)."""
import pytest
from target import {fn_name}, _reset_mock_stdin


_MOCK_LINES = {mock_lines}


def test_{fn_name}():
    """Joule workload: exercise solution() with mocked stdin."""
    _reset_mock_stdin(_MOCK_LINES)
    {fn_name}()
'''


def generate_test_file(
    unique_index: int,
    fn_name: str,
    tier: str,
    target_code: str,
) -> str:
    """Returns the full content of tests/test_target.py."""
    if tier in ("C", "D"):
        return _TEST_TEMPLATE_CLEAN.format(
            unique_index=unique_index,
            fn_name=fn_name,
        )

    mock_lines = generate_mock_stdin(target_code, tier, seed=unique_index)
    mock_lines_repr = format_mock_stdin_as_python_list(mock_lines)

    if tier == "A":
        return _TEST_TEMPLATE_STDIN_A.format(
            unique_index=unique_index,
            fn_name=fn_name,
            mock_lines=mock_lines_repr,
        )

    # tier B
    return _TEST_TEMPLATE_STDIN_B.format(
        unique_index=unique_index,
        fn_name=fn_name,
        mock_lines=mock_lines_repr,
    )
