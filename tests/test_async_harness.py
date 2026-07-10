"""Tests for AsyncHarnessWorkload execution."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from joule.models import TargetSpec, WorkloadKind, WorkloadSpec
from joule.profiling.core import execute_workload


async def dummy_async_target(limit: int) -> int:
    await asyncio.sleep(0.01)
    return sum(range(limit))


async def dummy_async_harness(target_fn) -> None:
    await target_fn(10)


def test_async_harness_workload_execution(tmp_path: Path):
    target = TargetSpec(
        project_root=tmp_path,
        module="tests.test_async_harness",
        file_path=tmp_path / "dummy.py",
        function_name="dummy_async_target",
        qualname="dummy_async_target",
        owner_path=[],
        line_start=1,
        line_end=5,
        source="",
        is_async=True,
    )
    # The selector format: module::object
    workload = WorkloadSpec(
        kind=WorkloadKind.ASYNC_HARNESS,
        identifier="async-harness-1",
        label="Async Harness",
        selector="tests.test_async_harness::dummy_async_harness",
    )

    # Execute the async harness workload with 3 repetitions
    payload = execute_workload(
        target=target,
        workload=workload,
        project_root=Path("."),
        inner_repetitions=3,
    )

    assert payload["success"] is True
    assert payload["logical_invocations"] == 3
