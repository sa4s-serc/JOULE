from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from joule.profiling.schema import (
    BlockMetrics,
    GranularAnalysis,
    HarnessSummary,
    InsightRecord,
    SignalQuality,
    WorkloadSignal,
)


# Project-like buckets for ownership classification
PROJECT_LIKE_BUCKETS = {"project", "candidate-overlay"}

# Analysis thresholds and limits
LOW_SIGNAL_THRESHOLD = 0.20  # 20% threshold for low signal warning
DEFAULT_TOP_FUNCTIONS_LIMIT = 12  # Default number of top functions to include
HIGH_CALL_COUNT_THRESHOLD = 5000  # Threshold for high call count warning
MS_PER_SECOND = 1000.0  # Milliseconds per second conversion
TIME_EPSILON = 0.0001  # Small value to avoid division by zero
BLOCK_HASH_LENGTH = 12  # Length of block ID hash digest
LINE_DETAILS_LIMIT = 20  # Maximum line details to include per block
TOP_BLOCKS_LIMIT = 20  # Maximum code blocks to include in analysis


def _normalized_profile_path(path_value: str) -> str:
    """Normalize a path for profile comparison."""
    value = str(path_value or "")
    if not value or value.startswith("~"):
        return value
    try:
        return str(Path(value).resolve())
    except (OSError, RuntimeError, ValueError):
        return value


def _enrich_hotspot_function(entry: dict[str, Any], *, total_cumulative: float) -> dict[str, Any]:
    """Enrich a function entry with calculated metrics."""
    cumulative_time = float(entry.get("cumulative_time_s", 0.0))
    total_time = float(entry.get("total_time_s", 0.0))
    total_calls = max(0, int(entry.get("total_calls", 0)))
    avg_cost_us = (cumulative_time / total_calls * 1_000_000.0) if total_calls > 0 else 0.0
    avg_self_cost_us = (total_time / total_calls * 1_000_000.0) if total_calls > 0 else 0.0
    share = cumulative_time / total_cumulative if total_cumulative > 0 else 0.0
    self_share = total_time / total_cumulative if total_cumulative > 0 else 0.0

    return {
        **entry,
        "share": round(share, 4),
        "self_share": round(self_share, 4),
        "avg_cost_us": round(avg_cost_us, 2),
        "avg_self_cost_us": round(avg_self_cost_us, 2),
    }


def build_workload_signals(
    records: list[dict],
    target_file: Path | str | None = None,
) -> list[WorkloadSignal]:
    """Build per-workload signal metrics."""
    signals: list[WorkloadSignal] = []
    normalized_target_file = _normalized_profile_path(str(target_file)) if target_file else ""

    for item in records:
        profile = item.get("profile", {})
        functions = list(profile.get("functions", []))
        ownership = list(profile.get("ownership", []))
        workload_kind = str(item.get("workload_kind", "unknown"))

        workload_total_time = sum(float(fn.get("cumulative_time_s", 0.0)) for fn in functions)
        workload_project_time = sum(
            float(fn.get("cumulative_time_s", 0.0))
            for fn in functions
            if str(fn.get("ownership", "")) in PROJECT_LIKE_BUCKETS
        )

        workload_target_time = 0.0
        if normalized_target_file:
            workload_target_time = sum(
                float(fn.get("cumulative_time_s", 0.0))
                for fn in functions
                if _normalized_profile_path(str(fn.get("file", ""))) == normalized_target_file
            )

        sorted_ownership = sorted(
            ownership,
            key=lambda owner: float(owner.get("cumulative_time_s", 0.0)),
            reverse=True,
        )
        dominant_bucket = str(sorted_ownership[0].get("bucket", "unknown")) if sorted_ownership else "unknown"

        workload_project_share = workload_project_time / workload_total_time if workload_total_time > 0 else 0.0
        workload_target_share = workload_target_time / workload_total_time if workload_total_time > 0 else 0.0

        signals.append(
            WorkloadSignal(
                workload_id=item.get("workload_id", "unknown"),
                workload_kind=workload_kind,
                workload_label=str(item.get("workload_label", "")),
                workload_selector=str(item.get("workload_selector", "")),
                project_share=workload_project_share,
                target_share=workload_target_share,
                dominant_ownership_bucket=dominant_bucket,
                total_cumulative_time_s=workload_total_time,
                low_signal=workload_total_time > 0 and workload_project_share < LOW_SIGNAL_THRESHOLD,
                success=item.get("success", False),
                stderr=str(item.get("stderr", "")),
            )
        )

    # Sort by project share (descending)
    signals.sort(key=lambda s: s.project_share, reverse=True)
    return signals


def aggregate_function_hotspots(
    records: list[dict],
    limit: int = DEFAULT_TOP_FUNCTIONS_LIMIT,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
]:
    """Aggregate function hotspots across all workloads.

    Returns:
        Tuple of (top_functions, target_top_functions, project_top_functions,
                  non_project_top_functions, ownership, workload_kind_counts)
    """
    aggregate_functions: defaultdict[tuple[str, int, str, str], dict] = defaultdict(
        lambda: {
            "file": "",
            "line": 0,
            "function": "",
            "ownership": "",
            "cumulative_time_s": 0.0,
            "total_time_s": 0.0,
            "total_calls": 0,
        }
    )
    ownership_totals: defaultdict[str, float] = defaultdict(float)
    workload_kind_counts: Counter[str] = Counter()

    for item in records:
        profile = item.get("profile", {})
        functions = list(profile.get("functions", []))
        ownership = list(profile.get("ownership", []))
        workload_kind = str(item.get("workload_kind", "unknown"))
        workload_kind_counts[workload_kind] += 1

        for fn in functions:
            key = (fn["file"], int(fn["line"]), fn["function"], fn["ownership"])
            agg = aggregate_functions[key]
            agg["file"] = fn["file"]
            agg["line"] = int(fn["line"])
            agg["function"] = fn["function"]
            agg["ownership"] = fn["ownership"]
            agg["cumulative_time_s"] += float(fn.get("cumulative_time_s", 0.0))
            agg["total_time_s"] += float(fn.get("total_time_s", 0.0))
            agg["total_calls"] += int(fn.get("total_calls", 0))

        for owner in ownership:
            ownership_totals[str(owner["bucket"])] += float(owner["cumulative_time_s"])

    all_functions_raw = sorted(
        aggregate_functions.values(), key=lambda item: item["cumulative_time_s"], reverse=True
    )

    merged_ownership = [
        {"bucket": bucket, "cumulative_time_s": total}
        for bucket, total in sorted(ownership_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    total_cumulative = sum(float(item["cumulative_time_s"]) for item in all_functions_raw)
    all_functions = [_enrich_hotspot_function(item, total_cumulative=total_cumulative) for item in all_functions_raw]

    # Split into project and non-project
    project_merged = [fn for fn in all_functions if str(fn.get("ownership", "")) in PROJECT_LIKE_BUCKETS]
    non_project_merged = [fn for fn in all_functions if str(fn.get("ownership", "")) not in PROJECT_LIKE_BUCKETS]

    # Top functions prioritizing project code
    merged_functions = (project_merged + non_project_merged)[:limit]

    # Target functions
    target_functions = [
        fn
        for fn in all_functions
        if str(fn.get("ownership", "")) in PROJECT_LIKE_BUCKETS
    ][:limit]

    return (
        merged_functions,
        target_functions,
        project_merged[:limit],
        non_project_merged[:limit],
        merged_ownership,
        dict(workload_kind_counts.most_common()),
    )


def build_signal_quality(
    records: list[dict],
    target_file: Path | str | None = None,
    ownership_totals: dict[str, float] | None = None,
) -> SignalQuality:
    """Build aggregate signal quality metrics."""
    ownership_totals = ownership_totals or {}

    total_cumulative = sum(ownership_totals.values())
    project_cumulative = sum(
        total for bucket, total in ownership_totals.items() if bucket in PROJECT_LIKE_BUCKETS
    )

    # Calculate target cumulative
    target_cumulative = 0.0
    if target_file:
        normalized_target_file = _normalized_profile_path(str(target_file))
        for item in records:
            profile = item.get("profile", {})
            functions = list(profile.get("functions", []))
            for fn in functions:
                if _normalized_profile_path(str(fn.get("file", ""))) == normalized_target_file:
                    target_cumulative += float(fn.get("cumulative_time_s", 0.0))

    project_share = project_cumulative / total_cumulative if total_cumulative > 0 else 0.0
    target_share = target_cumulative / total_cumulative if total_cumulative > 0 else 0.0

    # Determine dominant bucket
    aggregate_dominant_bucket: str | None = None
    if ownership_totals:
        aggregate_dominant_bucket = max(ownership_totals.items(), key=lambda x: x[1])[0]

    # Build low signal reasons
    low_signal_reasons: list[str] = []
    if total_cumulative <= 0:
        low_signal_reasons.append("no_profile_samples")
    if target_file and target_share < LOW_SIGNAL_THRESHOLD:
        low_signal_reasons.append("target_file_under_20pct")
    if aggregate_dominant_bucket and aggregate_dominant_bucket not in PROJECT_LIKE_BUCKETS:
        low_signal_reasons.append("non_project_dominant")

    return SignalQuality(
        total_cumulative_time_s=total_cumulative,
        project_cumulative_time_s=project_cumulative,
        target_cumulative_time_s=target_cumulative,
        project_share=project_share,
        target_share=target_share,
        low_signal=bool(low_signal_reasons),
        low_signal_reasons=low_signal_reasons,
        dominant_ownership_bucket=aggregate_dominant_bucket,
    )


def summarize_harness(
    all_functions: list[dict[str, Any]],
    ownership_totals: dict[str, float],
    limit: int = 5,
) -> HarnessSummary:
    """Create a condensed summary of harness/external code."""
    non_project = [
        fn for fn in all_functions if str(fn.get("ownership", "")) not in PROJECT_LIKE_BUCKETS
    ]

    harness_total = sum(
        total for bucket, total in ownership_totals.items() if bucket not in PROJECT_LIKE_BUCKETS
    )
    total_all = sum(ownership_totals.values())

    top_calls = [
        {
            "function": fn.get("function", "unknown"),
            "file": Path(fn.get("file", "unknown")).name,
            "time_s": round(fn.get("cumulative_time_s", 0.0), 4),
            "calls": fn.get("total_calls", 0),
        }
        for fn in non_project[:limit]
    ]

    return HarnessSummary(
        total_time_s=harness_total,
        share=harness_total / max(total_all, 0.0001),
        top_calls=top_calls,
        total_external_functions=len(non_project),
    )


def generate_recommendations(
    *,
    signal_quality: SignalQuality,
    target_top_functions: list[dict[str, Any]],
    by_workload: list[WorkloadSignal],
    workload_kind_counts: dict[str, int],
) -> list[str]:
    """Generate recommendations based on hotspot analysis."""
    recommendations: list[str] = []
    reasons = set(signal_quality.low_signal_reasons)

    if "target_file_under_20pct" in reasons:
        recommendations.append(
            "Target file contributes under 20% of hotspot time; add tighter harness/property workloads to isolate target logic."
        )
    if "non_project_dominant" in reasons:
        dominant = signal_quality.dominant_ownership_bucket or "non-project"
        recommendations.append(
            f"Hotspot time is dominated by {dominant}; optimize workload setup or dependency overhead before target rewrites."
        )
    if "no_profile_samples" in reasons:
        recommendations.append(
            "Profiler produced no usable samples; rerun with longer workloads or increase inner repetitions for stable attribution."
        )

    if target_top_functions:
        top_target = target_top_functions[0]
        recommendations.append(
            "Prioritize target hotspot "
            f"{Path(str(top_target.get('file', 'unknown'))).name}:{int(top_target.get('line', 0))}::{top_target.get('function', 'unknown')} "
            f"(share={float(top_target.get('share', 0.0)) * 100:.1f}%)."
        )
    else:
        recommendations.append(
            "No target-file hotspot entries found; verify target resolution and prefer explicit tests/properties for target behavior."
        )

    if workload_kind_counts.get("pytest", 0) > 0 and len(workload_kind_counts) == 1:
        recommendations.append(
            "Only pytest workloads were profiled; add property/harness selectors to reduce harness-heavy hotspot dilution."
        )

    # Low signal workloads
    low_signal_workloads = [w for w in by_workload if w.low_signal]
    if low_signal_workloads:
        first = low_signal_workloads[0]
        recommendations.append(
            f"Workload {first.workload_id} has low project share; inspect workload scope and trim setup/fixture overhead."
        )

    # High call counts (potential loops/N+1)
    if target_top_functions:
        most_called = max(target_top_functions, key=lambda fn: int(fn.get("total_calls", 0)))
        if int(most_called.get("total_calls", 0)) > HIGH_CALL_COUNT_THRESHOLD:
            recommendations.append(
                f"Hotspot {most_called.get('function')} has {most_called.get('total_calls')} calls; check for redundant loops or N+1 patterns."
            )

    return recommendations[:8]


def _create_stable_block_id(
    file: str,
    function: str,
    line_range: tuple[int, int],
    block_type: str,
) -> str:
    """Create a stable block ID based on file, function, line range, and type."""
    import hashlib

    # Create a deterministic string representation
    key = f"{file}:{function}:{line_range[0]}-{line_range[1]}:{block_type}"
    # Use hash for compactness while maintaining stability
    hash_digest = hashlib.md5(key.encode()).hexdigest()[:BLOCK_HASH_LENGTH]
    return f"block:{hash_digest}"


def extract_granular_analysis(records: list[dict]) -> GranularAnalysis | None:
    """Extract and aggregate granular profiling data from records."""
    granular_data: list[dict] = []

    for item in records:
        profile = item.get("profile", {})
        granular = profile.get("granular")
        if granular and isinstance(granular, dict):
            if "error" in granular:
                continue
            granular_data.append({
                "workload_id": item.get("workload_id", "unknown"),
                "function_name": granular.get("function_name", "unknown"),
                "file": granular.get("file", ""),
                "line_range": granular.get("line_range", [0, 0]),
                "total_time_s": granular.get("total_time_s", 0.0),
                "total_hits": granular.get("total_hits", 0),
                "code_blocks": granular.get("code_blocks", []),
                "raw_line_count": granular.get("raw_line_count", 0),
                "raw_line_metrics": granular.get("raw_line_metrics", []),
                "timer_unit_s": granular.get("timer_unit_s", 0.0),
                "profiler": granular.get("profiler", "unknown"),
                "profiler_available": granular.get("profiler_available", True),
            })

    if not granular_data:
        return None

    # Aggregate code blocks across workloads using stable IDs
    block_totals: dict[str, dict] = defaultdict(
        lambda: {
            "block_id": "",
            "type": "",
            "line_range": (0, 0),
            "description": "",
            "nesting_level": 0,
            "parent_block_id": None,
            "child_block_ids": [],
            "total_hits": 0,
            "total_time_s": 0.0,
            "time_min_s": float("inf"),
            "time_max_s": 0.0,
            "count": 0,
            "line_details": [],
        }
    )

    for data in granular_data:
        file = data.get("file", "")
        function = data.get("function_name", "unknown")

        for block in data.get("code_blocks", []):
            line_range = block.get("line_range", [0, 0])
            block_type = block.get("type", "")

            # Create stable block ID
            block_id = _create_stable_block_id(
                file, function, (line_range[0], line_range[1]), block_type
            )

            agg = block_totals[block_id]
            agg["block_id"] = block_id
            agg["type"] = block_type
            agg["line_range"] = (line_range[0], line_range[1])
            agg["description"] = block.get("description", "")
            agg["nesting_level"] = block.get("nesting_level", 0)
            agg["total_hits"] += block.get("hits", 0)
            time_s = block.get("time_s", 0.0)
            agg["total_time_s"] += time_s
            agg["time_min_s"] = min(agg["time_min_s"], time_s)
            agg["time_max_s"] = max(agg["time_max_s"], time_s)
            agg["count"] += 1

            # Collect line details
            if block.get("line_details"):
                agg["line_details"].extend(block["line_details"])

    # Calculate averages and enrich with metrics
    total_function_time = sum(d.get("total_time_s", 0.0) for d in granular_data) / max(len(granular_data), 1)

    blocks: list[BlockMetrics] = []
    for agg in block_totals.values():
        count = agg["count"]
        time_s = agg["total_time_s"] / max(count, 1)
        hits = agg["total_hits"] // max(count, 1)

        blocks.append(
            BlockMetrics(
                block_id=agg["block_id"],
                block_type=agg["type"],
                line_range=agg["line_range"],
                description=agg["description"],
                nesting_level=agg["nesting_level"],
                hits=hits,
                time_s=time_s,
                time_per_hit_ms=round((time_s / max(hits, 1)) * MS_PER_SECOND, 4),
                share_of_function=round(time_s / max(total_function_time, TIME_EPSILON), 4),
                workload_count=count,
                time_min_s=agg["time_min_s"] if agg["time_min_s"] != float("inf") else time_s,
                time_max_s=agg["time_max_s"] if agg["time_max_s"] > 0 else time_s,
                lines_covered=len(set(ld.get("line") for ld in agg["line_details"])) if agg["line_details"] else 0,
                line_details=agg["line_details"][:LINE_DETAILS_LIMIT],  # Limit details
            )
        )

    # Sort by time (descending)
    blocks.sort(key=lambda x: x.time_s, reverse=True)

    # Calculate summary by block type
    type_totals: dict[str, float] = defaultdict(float)
    for block in blocks:
        type_totals[block.block_type] += block.time_s

    # Get function info from first record
    first = granular_data[0]

    # Generate structured insights
    insights = InsightRecord.from_granular_data(blocks, dict(type_totals), total_function_time)

    return GranularAnalysis(
        target_function=first.get("function_name", "unknown"),
        file=first.get("file", ""),
        line_range=(first.get("line_range", [0, 0])[0], first.get("line_range", [0, 0])[1]),
        total_time_s=total_function_time,
        total_hits=first.get("total_hits", 0),
        workloads_profiled=len(granular_data),
        code_blocks=blocks[:TOP_BLOCKS_LIMIT],  # Limit to top blocks
        insights=insights,
        raw_line_count=first.get("raw_line_count", 0),
        raw_line_metrics=first.get("raw_line_metrics", []),
        timer_unit_s=first.get("timer_unit_s", 0.0),
        profiler=first.get("profiler", "unknown"),
        profiler_available=first.get("profiler_available", True),
    )
