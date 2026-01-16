"""
HEDGE Utilities

Common utilities for:
- Code hashing
- Dictionary operations
- Metrics formatting
- JSON serialization
- Performance timing
- Logging configuration
"""
from src.utils.common import (
    compute_code_hash,
    compute_content_hash,
    deep_merge_dicts,
    format_metrics,
    safe_json_dump,
    timed,
    Timer,
    chunk_list,
    first_or_none,
    flatten,
)
from src.utils.logging_config import setup_logging

__all__ = [
    # Hashing
    "compute_code_hash",
    "compute_content_hash",
    # Dict utilities
    "deep_merge_dicts",
    # Formatting
    "format_metrics",
    "safe_json_dump",
    # Timing
    "timed",
    "Timer",
    # List utilities
    "chunk_list",
    "first_or_none",
    "flatten",
    # Logging
    "setup_logging",
]
