from __future__ import annotations

from joule.profiling.core import ProfileMode, ProfilingError
from joule.profiling.granular import execute_granular_profiling, LINE_PROFILER_AVAILABLE
from joule.profiling.hotspots import execute_hotspot_profiling
from joule.profiling.memory import MemoryProfiler, create_memory_metrics
from joule.profiling.schema import (
    BlockMetrics,
    GranularAnalysis,
    HotspotSchema,
    InsightRecord,
    LineMetrics,
    MemoryMetrics,
    ProfileLevel,
    SignalQuality,
    create_hotspot_summary,
)

# Backward compatibility: tracemalloc is always available in Python 3.4+
TRACEMALLOC_AVAILABLE = True

__all__ = [
    "ProfileMode",
    "ProfileLevel",
    "ProfilingError",
    "execute_granular_profiling",
    "execute_hotspot_profiling",
    "LINE_PROFILER_AVAILABLE",
    "TRACEMALLOC_AVAILABLE",
    "MemoryProfiler",
    "create_memory_metrics",
    "BlockMetrics",
    "GranularAnalysis",
    "HotspotSchema",
    "InsightRecord",
    "LineMetrics",
    "MemoryMetrics",
    "ProfileLevel",
    "SignalQuality",
    "create_hotspot_summary",
]
