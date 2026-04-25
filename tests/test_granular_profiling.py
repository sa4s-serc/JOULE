"""Integration tests for granular hotspot profiling."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from typing import Any

from joule.utils.analysis import (
    summarize_hotspots,
    _extract_granular_analysis,
    _summarize_harness,
)


def test_summarize_hotspots_without_granular() -> None:
    """Test that standard hotspot analysis works without granular data."""
    records = [
        {
            "workload_id": "test-1",
            "workload_kind": "pytest",
            "workload_label": "test_basic",
            "profile": {
                "functions": [
                    {
                        "file": "/path/to/module.py",
                        "line": 10,
                        "function": "target_func",
                        "ownership": "project",
                        "cumulative_time_s": 1.5,
                        "total_time_s": 0.8,
                        "total_calls": 100,
                    },
                    {
                        "file": "/usr/lib/python/os.py",
                        "line": 50,
                        "function": "path_join",
                        "ownership": "stdlib-or-site",
                        "cumulative_time_s": 0.5,
                        "total_time_s": 0.5,
                        "total_calls": 200,
                    },
                ],
                "ownership": [
                    {"bucket": "project", "cumulative_time_s": 1.5},
                    {"bucket": "stdlib-or-site", "cumulative_time_s": 0.5},
                ],
            },
            "success": True,
            "return_code": 0,
            "stderr": "",
        }
    ]

    result = summarize_hotspots(records, limit=12, target_file="/path/to/module.py", granular=False)

    # Check basic structure
    assert result["schema_version"] == 3
    assert "by_workload" in result
    assert "top_functions" in result
    assert "harness_summary" in result
    assert "granular_analysis" not in result  # Should not be present when granular=False

    # Check harness summary
    harness = result["harness_summary"]
    assert "total_time_s" in harness
    assert "share" in harness
    assert "top_calls" in harness


def test_summarize_hotspots_with_granular() -> None:
    """Test that granular hotspot analysis works when data is present."""
    records = [
        {
            "workload_id": "test-1",
            "workload_kind": "pytest",
            "workload_label": "test_basic",
            "profile": {
                "functions": [
                    {
                        "file": "/path/to/module.py",
                        "line": 10,
                        "function": "target_func",
                        "ownership": "project",
                        "cumulative_time_s": 2.0,
                        "total_time_s": 1.0,
                        "total_calls": 100,
                    },
                ],
                "ownership": [
                    {"bucket": "project", "cumulative_time_s": 2.0},
                ],
                "granular": {
                    "function_name": "target_func",
                    "file": "/path/to/module.py",
                    "line_range": [10, 50],
                    "total_time_s": 1.5,
                    "total_hits": 1000,
                    "code_blocks": [
                        {
                            "type": "for_loop",
                            "line_range": [15, 25],
                            "description": "for item in items:",
                            "hits": 500,
                            "time_s": 0.8,
                        },
                        {
                            "type": "if_branch",
                            "line_range": [20, 22],
                            "description": "if item > 5:",
                            "hits": 200,
                            "time_s": 0.3,
                        },
                    ],
                },
            },
            "success": True,
            "return_code": 0,
            "stderr": "",
        }
    ]

    result = summarize_hotspots(records, limit=12, target_file="/path/to/module.py", granular=True)

    # Check granular analysis is present
    assert "granular_analysis" in result
    granular = result["granular_analysis"]
    assert granular["target_function"] == "target_func"
    assert granular["total_time_s"] == 1.5
    assert len(granular["code_blocks"]) == 2

    # Check code block structure
    first_block = granular["code_blocks"][0]
    assert "type" in first_block
    assert "line_range" in first_block
    assert "description" in first_block
    assert "hits" in first_block
    assert "time_s" in first_block
    assert "share_of_function" in first_block

    # Check hotspot summary
    assert "hotspot_summary" in granular
    summary = granular["hotspot_summary"]
    assert "hottest_block" in summary
    assert "loop_time_total_s" in summary
    assert "branch_time_total_s" in summary


def test_extract_granular_analysis_empty() -> None:
    """Test handling of empty records."""
    result = _extract_granular_analysis([])
    assert result is None


def test_extract_granular_analysis_no_granular() -> None:
    """Test handling of records without granular data."""
    records = [
        {
            "workload_id": "test-1",
            "profile": {
                "functions": [],
                "ownership": [],
            }
        }
    ]
    result = _extract_granular_analysis(records)
    assert result is None


def test_extract_granular_analysis_with_errors() -> None:
    """Test handling of records with granular errors."""
    records = [
        {
            "workload_id": "test-1",
            "profile": {
                "granular": {"error": "line_profiler not available"}
            }
        }
    ]
    result = _extract_granular_analysis(records)
    assert result is None


def test_extract_granular_analysis_aggregation() -> None:
    """Test that granular data is properly aggregated across workloads."""
    records = [
        {
            "workload_id": "test-1",
            "profile": {
                "granular": {
                    "function_name": "target_func",
                    "file": "/path/to/module.py",
                    "line_range": [10, 50],
                    "total_time_s": 1.0,
                    "total_hits": 500,
                    "code_blocks": [
                        {
                            "type": "for_loop",
                            "line_range": [15, 25],
                            "description": "for item in items:",
                            "hits": 100,
                            "time_s": 0.5,
                        },
                    ],
                }
            }
        },
        {
            "workload_id": "test-2",
            "profile": {
                "granular": {
                    "function_name": "target_func",
                    "file": "/path/to/module.py",
                    "line_range": [10, 50],
                    "total_time_s": 1.2,
                    "total_hits": 600,
                    "code_blocks": [
                        {
                            "type": "for_loop",
                            "line_range": [15, 25],
                            "description": "for item in items:",
                            "hits": 120,
                            "time_s": 0.6,
                        },
                    ],
                }
            }
        }
    ]

    result = _extract_granular_analysis(records)
    assert result is not None

    # Check averaging
    assert result["total_time_s"] == 1.1  # Average of 1.0 and 1.2
    assert result["workloads_profiled"] == 2

    # Check block aggregation
    blocks = result["code_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["hits"] == 110  # Average of 100 and 120 (integer division)
    assert blocks[0]["time_s"] == 0.55  # Average of 0.5 and 0.6


def test_summarize_harness() -> None:
    """Test harness summary generation."""
    all_functions = [
        {
            "file": "/path/to/module.py",
            "function": "target_func",
            "ownership": "project",
            "cumulative_time_s": 1.5,
            "total_calls": 100,
        },
        {
            "file": "/usr/lib/python/os.py",
            "function": "path_join",
            "ownership": "stdlib-or-site",
            "cumulative_time_s": 0.5,
            "total_calls": 50,
        },
        {
            "file": "/home/user/.venv/lib/external.py",
            "function": "external_func",
            "ownership": "external",
            "cumulative_time_s": 0.3,
            "total_calls": 30,
        },
    ]

    ownership_totals = {
        "project": 1.5,
        "stdlib-or-site": 0.5,
        "external": 0.3,
    }

    project_like = {"project", "candidate-overlay"}

    result = _summarize_harness(all_functions, ownership_totals, project_like, limit=5)

    assert result["total_time_s"] == 0.8  # 0.5 + 0.3
    # Share is non-project / total: (0.5 + 0.3) / (1.5 + 0.5 + 0.3) = 0.8 / 2.3 = 0.3478
    assert round(result["share"], 2) == 0.35
    assert len(result["top_calls"]) <= 5
    assert result["total_external_functions"] == 2


def test_hotspot_recommendations_with_granular() -> None:
    """Test that recommendations are generated with granular insights."""
    records = [
        {
            "workload_id": "test-1",
            "workload_kind": "pytest",
            "profile": {
                "functions": [
                    {
                        "file": "/path/to/module.py",
                        "line": 10,
                        "function": "target_func",
                        "ownership": "project",
                        "cumulative_time_s": 2.0,
                        "total_time_s": 1.0,
                        "total_calls": 6000,  # High call count for function-level detection
                    },
                ],
                "ownership": [
                    {"bucket": "project", "cumulative_time_s": 2.0},
                ],
                "granular": {
                    "function_name": "target_func",
                    "file": "/path/to/module.py",
                    "line_range": [10, 50],
                    "total_time_s": 1.5,
                    "total_hits": 10000,  # High hit count
                    "code_blocks": [
                        {
                            "type": "for_loop",
                            "line_range": [15, 25],
                            "description": "for item in items:",
                            "hits": 5000,  # Very high hit count
                            "time_s": 0.8,
                        },
                    ],
                },
            },
            "success": True,
            "return_code": 0,
            "stderr": "",
        }
    ]

    result = summarize_hotspots(records, limit=12, target_file="/path/to/module.py", granular=True)

    # Should have recommendations
    assert "recommendations" in result
    assert len(result["recommendations"]) > 0

    # Check for high call count warning in recommendations
    high_call_rec = [r for r in result["recommendations"] if "6000 calls" in r]
    assert len(high_call_rec) == 1
