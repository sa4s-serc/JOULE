from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# Insight generation thresholds
CRITICAL_HOTSPOT_THRESHOLD = 0.30  # 30% share for critical hotspot
HOTSPOT_THRESHOLD = 0.10  # 10% share for regular hotspot
LOOP_DOMINANT_THRESHOLD = 0.50  # 50% share for loop dominance
MEMORY_HOTSPOT_THRESHOLD = 0.30  # 30% share for memory hotspot
HIGH_ALLOCATION_THRESHOLD = 1000  # Allocation count for high allocation warning
MEMORY_INTENSIVE_THRESHOLD_MIB_PER_S = 100  # MiB/s for memory intensive
BYTES_PER_MIB = 1024 * 1024  # Bytes per MiB
DESCRIPTION_MAX_LEN = 40  # Max length for descriptions in messages


class ProfileLevel(Enum):
    """Profiling level for hotspot artifacts.

    Two levels:
    - BASIC: Function-level profiling with cProfile
    - GRANULAR: Deep line-level profiling with line_profiler
    """

    BASIC = "basic"  # Function-level hotspots
    GRANULAR = "granular"  # Deep line-level with structured insights


@dataclass
class SignalQuality:
    """Signal quality metrics for hotspot analysis."""

    total_cumulative_time_s: float = 0.0
    project_cumulative_time_s: float = 0.0
    target_cumulative_time_s: float = 0.0
    project_share: float = 0.0
    target_share: float = 0.0
    low_signal: bool = False
    low_signal_reasons: list[str] = field(default_factory=list)
    dominant_ownership_bucket: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cumulative_time_s": self.total_cumulative_time_s,
            "project_cumulative_time_s": self.project_cumulative_time_s,
            "target_cumulative_time_s": self.target_cumulative_time_s,
            "project_share": round(self.project_share, 4),
            "target_share": round(self.target_share, 4),
            "low_signal": self.low_signal,
            "low_signal_reasons": self.low_signal_reasons,
            "dominant_ownership_bucket": self.dominant_ownership_bucket,
        }


@dataclass
class LineMetrics:
    """Metrics for a single line of code."""

    line: int
    hits: int
    time_s: float
    time_per_hit_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "hits": self.hits,
            "time_s": round(self.time_s, 6),
            "time_per_hit_ms": round(self.time_per_hit_ms, 4),
        }


@dataclass
class MemoryMetrics:
    """Memory allocation metrics for code blocks.

    Tracks peak memory usage and allocation counts per block.
    """

    peak_memory_bytes: int = 0
    total_allocations: int = 0
    allocation_count: int = 0
    free_count: int = 0
    net_memory_bytes: int = 0  # allocations - frees

    # Per-workload aggregation
    memory_min_bytes: int = 0
    memory_max_bytes: int = 0
    workload_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_memory_bytes": self.peak_memory_bytes,
            "total_allocations": self.total_allocations,
            "allocation_count": self.allocation_count,
            "free_count": self.free_count,
            "net_memory_bytes": self.net_memory_bytes,
            "memory_min_bytes": self.memory_min_bytes,
            "memory_max_bytes": self.memory_max_bytes,
            "workload_count": self.workload_count,
        }


@dataclass
class BlockMetrics:
    """Metrics for a code block (loop, branch, etc.)."""

    block_id: str  # Stable block ID: "file:function:start-end:type"
    block_type: str
    line_range: tuple[int, int]
    description: str
    nesting_level: int = 0
    parent_block_id: str | None = None
    child_block_ids: list[str] = field(default_factory=list)

    # Timing metrics
    hits: int = 0
    time_s: float = 0.0
    time_per_hit_ms: float = 0.0
    share_of_function: float = 0.0

    # Aggregation metrics
    workload_count: int = 1
    time_min_s: float = 0.0
    time_max_s: float = 0.0

    # Memory metrics (optional, populated when memory profiling enabled)
    memory: MemoryMetrics | None = None

    # Line-level details
    lines_covered: int = 0
    line_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "block_id": self.block_id,
            "type": self.block_type,
            "line_range": [self.line_range[0], self.line_range[1]],
            "description": self.description,
            "nesting_level": self.nesting_level,
            "parent_block_id": self.parent_block_id,
            "child_block_ids": self.child_block_ids,
            "hits": self.hits,
            "time_s": round(self.time_s, 6),
            "time_per_hit_ms": round(self.time_per_hit_ms, 4),
            "share_of_function": round(self.share_of_function, 4),
            "workload_count": self.workload_count,
            "time_min_s": round(self.time_min_s, 6),
            "time_max_s": round(self.time_max_s, 6),
            "lines_covered": self.lines_covered,
        }
        if self.memory:
            result["memory"] = self.memory.to_dict()
        if self.line_details:
            result["line_details"] = self.line_details

        return result


@dataclass
class InsightRecord:
    """Structured insight record replacing emoji-heavy strings."""

    kind: str  # e.g., "critical_hotspot", "loop_dominant", "high_complexity"
    severity: str  # "critical", "warning", "info"
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    line_range: tuple[int, int] | None = None
    block_type: str | None = None
    block_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
        }
        if self.evidence:
            result["evidence"] = self.evidence
        if self.line_range:
            result["line_range"] = [self.line_range[0], self.line_range[1]]
        if self.block_type:
            result["block_type"] = self.block_type
        if self.block_id:
            result["block_id"] = self.block_id
        return result

    @classmethod
    def from_granular_data(
        cls,
        blocks: list[BlockMetrics],
        type_totals: dict[str, float],
        total_time: float,
    ) -> list[InsightRecord]:
        """Generate structured insights from granular analysis."""
        insights: list[InsightRecord] = []

        if not blocks:
            return insights

        # Top hotspot insight
        top_block = blocks[0]
        if top_block.share_of_function > CRITICAL_HOTSPOT_THRESHOLD:
            insights.append(
                cls(
                    kind="critical_hotspot",
                    severity="critical",
                    message=f"Critical hotspot: '{top_block.description[:DESCRIPTION_MAX_LEN]}' consumes {top_block.share_of_function*100:.1f}% of function time",
                    evidence={
                        "share_of_function": top_block.share_of_function,
                        "time_s": top_block.time_s,
                        "hits": top_block.hits,
                    },
                    line_range=top_block.line_range,
                    block_type=top_block.block_type,
                    block_id=top_block.block_id,
                )
            )
        elif top_block.share_of_function > HOTSPOT_THRESHOLD:
            insights.append(
                cls(
                    kind="hotspot",
                    severity="warning",
                    message=f"Hotspot: '{top_block.description[:DESCRIPTION_MAX_LEN]}' takes {top_block.share_of_function*100:.1f}% of function time",
                    evidence={
                        "share_of_function": top_block.share_of_function,
                        "time_s": top_block.time_s,
                        "hits": top_block.hits,
                    },
                    line_range=top_block.line_range,
                    block_type=top_block.block_type,
                    block_id=top_block.block_id,
                )
            )

        # Loop insights
        loop_time = type_totals.get("for_loop", 0.0) + type_totals.get("while_loop", 0.0)
        if total_time > 0 and loop_time / total_time > LOOP_DOMINANT_THRESHOLD:
            insights.append(
                cls(
                    kind="loop_dominant",
                    severity="info",
                    message=f"Loops dominate: {loop_time/total_time*100:.1f}% of time in loops",
                    evidence={
                        "loop_time_s": loop_time,
                        "total_time_s": total_time,
                        "loop_share": loop_time / total_time,
                    },
                )
            )

        # High complexity blocks (loops with high per-iteration cost)
        complex_blocks = [
            b for b in blocks
            if b.block_type in ("for_loop", "while_loop") and b.time_per_hit_ms > 1.0
        ]
        if complex_blocks:
            insights.append(
                cls(
                    kind="high_complexity",
                    severity="warning",
                    message=f"{len(complex_blocks)} loop(s) with high per-iteration cost detected",
                    evidence={
                        "count": len(complex_blocks),
                        "blocks": [
                            {
                                "block_id": b.block_id,
                                "description": b.description,
                                "time_per_hit_ms": b.time_per_hit_ms,
                            }
                            for b in complex_blocks[:3]
                        ],
                    },
                )
            )

        # Deep nesting warning
        deep_blocks = [b for b in blocks if b.nesting_level >= 3]
        if deep_blocks:
            insights.append(
                cls(
                    kind="deep_nesting",
                    severity="info",
                    message=f"Deep nesting: {len(deep_blocks)} block(s) at nesting level 3+",
                    evidence={
                        "count": len(deep_blocks),
                        "max_nesting": max(b.nesting_level for b in deep_blocks),
                    },
                )
            )

        # Comprehension usage
        comprehension_types = [
            "list_comprehension",
            "dict_comprehension",
            "set_comprehension",
            "generator_expression",
        ]
        comprehension_time = sum(type_totals.get(ct, 0.0) for ct in comprehension_types)
        if comprehension_time > 0 and total_time > 0:
            insights.append(
                cls(
                    kind="comprehension_usage",
                    severity="info",
                    message=f"Comprehensions contribute {comprehension_time/total_time*100:.1f}% of time",
                    evidence={
                        "comprehension_time_s": comprehension_time,
                        "total_time_s": total_time,
                        "share": comprehension_time / total_time,
                    },
                )
            )

        return insights

    @classmethod
    def from_memory_data(
        cls,
        blocks: list[BlockMetrics],
        total_memory_bytes: int,
        total_allocations: int,
    ) -> list[InsightRecord]:
        """Generate memory-specific insights from profiling data."""
        insights: list[InsightRecord] = []

        if not blocks or total_memory_bytes <= 0:
            return insights

        # Memory hotspot insight
        blocks_with_memory = [b for b in blocks if b.memory and b.memory.peak_memory_bytes > 0]
        if not blocks_with_memory:
            return insights

        # Sort by peak memory
        blocks_with_memory.sort(key=lambda b: b.memory.peak_memory_bytes if b.memory else 0, reverse=True)  # type: ignore
        top_memory = blocks_with_memory[0]
        mem = top_memory.memory

        if mem and mem.peak_memory_bytes > total_memory_bytes * MEMORY_HOTSPOT_THRESHOLD:
            insights.append(
                cls(
                    kind="memory_hotspot",
                    severity="critical",
                    message=f"Memory hotspot: '{top_memory.description[:DESCRIPTION_MAX_LEN]}' uses {mem.peak_memory_bytes / BYTES_PER_MIB:.2f} MiB",
                    evidence={
                        "peak_memory_bytes": mem.peak_memory_bytes,
                        "share_of_total": mem.peak_memory_bytes / total_memory_bytes,
                        "allocation_count": mem.allocation_count,
                    },
                    line_range=top_memory.line_range,
                    block_type=top_memory.block_type,
                    block_id=top_memory.block_id,
                )
            )

        # High allocation rate blocks
        high_alloc_blocks = [
            b for b in blocks_with_memory
            if b.memory and b.memory.allocation_count > HIGH_ALLOCATION_THRESHOLD  # type: ignore
        ]
        if high_alloc_blocks:
            insights.append(
                cls(
                    kind="high_allocation_rate",
                    severity="warning",
                    message=f"{len(high_alloc_blocks)} block(s) with high allocation count",
                    evidence={
                        "count": len(high_alloc_blocks),
                        "total_allocations": sum(
                            b.memory.allocation_count for b in high_alloc_blocks if b.memory  # type: ignore
                        ),
                        "blocks": [
                            {
                                "block_id": b.block_id,
                                "description": b.description,
                                "allocation_count": b.memory.allocation_count if b.memory else 0,  # type: ignore
                            }
                            for b in high_alloc_blocks[:3]
                        ],
                    },
                )
            )

        # Memory vs time correlation insight
        memory_heavy_blocks = [
            b for b in blocks_with_memory
            if b.memory and mem and b.time_s > 0 and (b.memory.peak_memory_bytes / BYTES_PER_MIB) / b.time_s > MEMORY_INTENSIVE_THRESHOLD_MIB_PER_S  # type: ignore
        ]
        if memory_heavy_blocks:
            insights.append(
                cls(
                    kind="memory_intensive",
                    severity="info",
                    message=f"{len(memory_heavy_blocks)} block(s) with high memory/time ratio",
                    evidence={
                        "count": len(memory_heavy_blocks),
                        "avg_memory_per_second_mib": sum(
                            (b.memory.peak_memory_bytes / BYTES_PER_MIB) / b.time_s  # type: ignore
                            for b in memory_heavy_blocks if b.memory
                        ) / len(memory_heavy_blocks),
                    },
                )
            )

        return insights


@dataclass
class GranularAnalysis:
    """Granular analysis results for a target function."""

    target_function: str
    file: str
    line_range: tuple[int, int]
    total_time_s: float
    total_hits: int
    workloads_profiled: int

    code_blocks: list[BlockMetrics]
    insights: list[InsightRecord]

    # Raw metrics for debugging
    raw_line_count: int = 0
    raw_line_metrics: list[dict[str, Any]] = field(default_factory=list)
    timer_unit_s: float = 0.0
    profiler: str = ""
    profiler_available: bool = True

    # Memory profiling data (optional)
    peak_memory_bytes: int = 0
    total_allocations: int = 0
    memory_profiler: str = ""  # e.g., "tracemalloc"
    memory_profiled: bool = False

    # Error tracking
    ast_error: str | None = None
    memory_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "target_function": self.target_function,
            "file": self.file,
            "line_range": [self.line_range[0], self.line_range[1]],
            "total_time_s": round(self.total_time_s, 6),
            "total_hits": self.total_hits,
            "workloads_profiled": self.workloads_profiled,
            "code_blocks": [b.to_dict() for b in self.code_blocks],
            "insights": [i.to_dict() for i in self.insights],
            "raw_line_count": self.raw_line_count,
            "timer_unit_s": self.timer_unit_s,
            "profiler": self.profiler,
            "profiler_available": self.profiler_available,
        }

        # Include memory data if profiled
        if self.memory_profiled:
            result["peak_memory_bytes"] = self.peak_memory_bytes
            result["total_allocations"] = self.total_allocations
            result["memory_profiler"] = self.memory_profiler
            result["memory_profiled"] = True

        if self.raw_line_metrics:
            result["raw_line_metrics"] = self.raw_line_metrics
        if self.ast_error:
            result["ast_error"] = self.ast_error
        if self.memory_error:
            result["memory_error"] = self.memory_error

        return result


@dataclass
class HarnessSummary:
    """Summary of harness/external code time."""

    total_time_s: float
    share: float
    top_calls: list[dict[str, Any]]
    total_external_functions: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_time_s": round(self.total_time_s, 4),
            "share": round(self.share, 4),
            "top_calls": self.top_calls,
            "total_external_functions": self.total_external_functions,
        }


@dataclass
class WorkloadSignal:
    """Per-workload signal metrics."""

    workload_id: str
    workload_kind: str
    workload_label: str
    workload_selector: str
    project_share: float
    target_share: float
    dominant_ownership_bucket: str
    total_cumulative_time_s: float
    low_signal: bool
    success: bool
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "workload_kind": self.workload_kind,
            "workload_label": self.workload_label,
            "workload_selector": self.workload_selector,
            "project_share": round(self.project_share, 4),
            "target_share": round(self.target_share, 4),
            "dominant_ownership_bucket": self.dominant_ownership_bucket,
            "total_cumulative_time_s": round(self.total_cumulative_time_s, 6),
            "low_signal": self.low_signal,
            "success": self.success,
            "stderr": self.stderr if self.stderr else None,
        }


@dataclass
class HotspotSchema:
    """Hardened hotspot schema with structured fields.

    Two modes:
    - BASIC: Function-level profiling only
    - GRANULAR: Deep line-level profiling with code block metrics
    """

    schema_version: int = 2  # Simplified: schema v2 for hardened format
    by_workload: list[WorkloadSignal] = field(default_factory=list)
    top_functions: list[dict[str, Any]] = field(default_factory=list)
    target_top_functions: list[dict[str, Any]] = field(default_factory=list)
    project_top_functions: list[dict[str, Any]] = field(default_factory=list)
    non_project_top_functions: list[dict[str, Any]] = field(default_factory=list)
    ownership: list[dict[str, Any]] = field(default_factory=list)
    workload_kind_counts: dict[str, int] = field(default_factory=dict)
    signal_quality: SignalQuality = field(default_factory=SignalQuality)
    insights: dict[str, Any] = field(default_factory=dict)
    harness_summary: HarnessSummary | None = None
    recommendations: list[str] = field(default_factory=list)
    granular_analysis: GranularAnalysis | None = None

    # Error/capability metadata
    profiler_capability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "by_workload": [w.to_dict() for w in self.by_workload],
            "top_functions": self.top_functions,
            "target_top_functions": self.target_top_functions,
            "project_top_functions": self.project_top_functions,
            "non_project_top_functions": self.non_project_top_functions,
            "ownership": self.ownership,
            "workload_kind_counts": self.workload_kind_counts,
            "signal_quality": self.signal_quality.to_dict(),
            "insights": self.insights,
            "recommendations": self.recommendations,
        }

        if self.harness_summary:
            result["harness_summary"] = self.harness_summary.to_dict()

        if self.granular_analysis:
            result["granular_analysis"] = self.granular_analysis.to_dict()

        if self.profiler_capability:
            result["profiler_capability"] = self.profiler_capability

        return result


def create_hotspot_summary(
    records: list[dict],
    *,
    limit: int = 12,
    target_file: Path | str | None = None,
    level: ProfileLevel = ProfileLevel.BASIC,
) -> dict[str, Any]:
    """Create a hotspot summary from profile records.

    Args:
        records: List of profile records from workloads
        limit: Maximum number of top functions to include
        target_file: Path to the target file for filtering
        level: Profiling level (BASIC or GRANULAR)

    Returns:
        Hotspot summary dictionary with hardened schema v2
    """
    from joule.profiling.summarize import (
        aggregate_function_hotspots,
        build_signal_quality,
        build_workload_signals,
        extract_granular_analysis,
        generate_recommendations,
        summarize_harness,
    )

    # Build workload signals
    by_workload = build_workload_signals(records, target_file=target_file)

    # Aggregate function hotspots
    (
        top_functions,
        target_top_functions,
        project_top_functions,
        non_project_top_functions,
        ownership,
        workload_kind_counts,
    ) = aggregate_function_hotspots(records, limit=limit, target_file=target_file)

    # Build signal quality
    signal_quality = build_signal_quality(
        records,
        target_file=target_file,
        ownership_totals={o["bucket"]: o["cumulative_time_s"] for o in ownership},
    )

    # Build insights
    strongest_workload = by_workload[0] if by_workload else None
    # When there's only 1 workload, it's both strongest and weakest
    weakest_workload = by_workload[-1] if by_workload else None

    insights = {
        "primary_target_hotspot": target_top_functions[0] if target_top_functions else None,
        "strongest_signal_workload": (
            {
                "workload_id": strongest_workload.workload_id,
                "workload_kind": strongest_workload.workload_kind,
                "project_share": strongest_workload.project_share,
                "target_share": strongest_workload.target_share,
            }
            if strongest_workload
            else None
        ),
        "weakest_signal_workload": (
            {
                "workload_id": weakest_workload.workload_id,
                "workload_kind": weakest_workload.workload_kind,
                "project_share": weakest_workload.project_share,
                "target_share": weakest_workload.target_share,
            }
            if weakest_workload
            else None
        ),
        "profiled_workload_count": len(by_workload),
    }

    # Summarize harness — pass project + non-project combined so non-project
    # functions excluded from the top_functions slice are still accounted for.
    all_profiled_functions = project_top_functions + non_project_top_functions
    harness_summary = summarize_harness(
        all_profiled_functions,
        {o["bucket"]: o["cumulative_time_s"] for o in ownership},
    )

    # Generate recommendations
    recommendations = generate_recommendations(
        signal_quality=signal_quality,
        target_top_functions=target_top_functions,
        by_workload=by_workload,
        workload_kind_counts=workload_kind_counts,
    )

    # Extract granular analysis if requested
    granular_analysis = None
    if level is ProfileLevel.GRANULAR:
        granular_analysis = extract_granular_analysis(records)

    # Build profiler capability metadata
    profiler_capability = {
        "function_level": True,
        "granular_level": level is ProfileLevel.GRANULAR and granular_analysis is not None,
        "line_profiler_available": _check_line_profiler(),
    }

    schema = HotspotSchema(
        by_workload=by_workload,
        top_functions=top_functions,
        target_top_functions=target_top_functions,
        project_top_functions=project_top_functions,
        non_project_top_functions=non_project_top_functions,
        ownership=ownership,
        workload_kind_counts=workload_kind_counts,
        signal_quality=signal_quality,
        insights=insights,
        harness_summary=harness_summary,
        recommendations=recommendations,
        granular_analysis=granular_analysis,
        profiler_capability=profiler_capability,
    )

    return schema.to_dict()


def _check_line_profiler() -> bool:
    """Check if line_profiler is available."""
    try:
        import line_profiler  # noqa: F401

        return True
    except ImportError:
        return False
