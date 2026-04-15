from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
from typing import Any

from joule.metadata import parse_candidate_metadata
from joule.models import MeasurementReport
from joule.utils.db import CandidateRecord
from joule.utils.metrics import improvement_ratio


FUNNEL_ORDER = [
    "generated",
    "unchanged",
    "duplicate",
    "correctness_rejected",
    "surrogate_rejected",
    "measured_f1",
    "rejected_f1",
    "measured_f2",
    "rejected_f2",
    "measured_f3",
    "accepted",
    "rejected_f3",
]

TERMINAL_EVENT_TYPES = (
    "unchanged",
    "duplicate",
    "correctness_rejected",
    "surrogate_rejected",
    "rejected_f1",
    "rejected_f2",
    "rejected_f3",
    "accepted",
)


def candidate_source_hash(source: str) -> str:
    import hashlib

    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def summarize_search_events(events: list[dict]) -> dict:
    funnel = {key: 0 for key in FUNNEL_ORDER}
    rejection_reasons: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    stage_timings: defaultdict[str, float] = defaultdict(float)
    for event in events:
        event_type = event["event_type"]
        detail = event.get("detail", {})
        event_counts[event_type] += 1
        if event_type in funnel:
            funnel[event_type] += 1
        reason = detail.get("reason")
        if reason and event_type != "accepted":
            rejection_reasons[str(reason)] += 1
        duration_s = detail.get("duration_s")
        if isinstance(duration_s, (int, float)):
            stage_timings[str(event["stage"])] += float(duration_s)
    return {
        "funnel": funnel,
        "event_counts": dict(event_counts.most_common()),
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "stage_timings_s": dict(stage_timings),
    }


def summarize_operator_performance(candidates: list[CandidateRecord], baseline_aggregate: dict | None = None) -> list[dict]:
    stats: dict[str, dict] = {}
    for item in candidates:
        operator = item["operator_name"]
        entry = stats.setdefault(
            operator,
            {
                "operator_name": operator,
                "attempts": 0,
                "accepted": 0,
                "skipped": 0,
                "rejected": 0,
                "stage_reached": Counter(),
                "rejection_reasons": Counter(),
                "tier_counts": Counter(),
                "tier_descriptors": Counter(),
                "improvements": [],
            },
        )
        entry["attempts"] += 1
        status = item["status"]
        if status == "accepted":
            entry["accepted"] += 1
        elif status == "skipped":
            entry["skipped"] += 1
        else:
            entry["rejected"] += 1
        metadata = parse_candidate_metadata(item.get("metadata", {}))
        stage = metadata.stage
        if stage:
            entry["stage_reached"][str(stage)] += 1
        reason = metadata.rejected
        if reason:
            entry["rejection_reasons"][str(reason)] += 1
        tier = metadata.operator_tier
        if tier:
            entry["tier_counts"][str(tier)] += 1
        tier_descriptor = metadata.operator_tier_descriptor
        if tier_descriptor:
            entry["tier_descriptors"][str(tier_descriptor)] += 1
        entry["improvements"].append(
            {
                "energy": metadata.improvement_summary.energy,
                "latency": metadata.improvement_summary.latency,
                "memory": metadata.improvement_summary.memory,
            }
        )
    results = []
    for entry in stats.values():
        improvements = entry.pop("improvements")
        if improvements:
            count = len(improvements)
            entry["avg_energy_delta"] = sum(item["energy"] for item in improvements) / count
            entry["avg_latency_delta"] = sum(item["latency"] for item in improvements) / count
            entry["avg_memory_delta"] = sum(item["memory"] for item in improvements) / count
        else:
            entry["avg_energy_delta"] = 0.0
            entry["avg_latency_delta"] = 0.0
            entry["avg_memory_delta"] = 0.0
        entry["stage_reached"] = dict(entry["stage_reached"])
        entry["rejection_reasons"] = dict(entry["rejection_reasons"].most_common())
        entry["tier_counts"] = dict(entry["tier_counts"].most_common())
        entry["tier_descriptors"] = dict(entry["tier_descriptors"].most_common())
        entry["primary_tier"] = next(iter(entry["tier_counts"]), None)
        entry["acceptance_rate"] = entry["accepted"] / max(entry["attempts"], 1)
        results.append(entry)
    results.sort(key=lambda item: (-item["acceptance_rate"], -item["attempts"], item["operator_name"]))
    return results


def _normalized_profile_path(path_value: str) -> str:
    value = str(path_value or "")
    if not value or value.startswith("~"):
        return value
    try:
        return str(Path(value).resolve())
    except (OSError, RuntimeError, ValueError):
        return value


def _enrich_hotspot_function(entry: dict[str, Any], *, total_cumulative: float) -> dict[str, Any]:
    cumulative_time = float(entry.get("cumulative_time_s", 0.0))
    total_calls = max(0, int(entry.get("total_calls", 0)))
    avg_cost_us = (cumulative_time / total_calls * 1_000_000.0) if total_calls > 0 else 0.0
    share = cumulative_time / total_cumulative if total_cumulative > 0 else 0.0
    return {
        **entry,
        "share": round(share, 4),
        "avg_cost_us": round(avg_cost_us, 2),
    }


def _hotspot_recommendations(
    *,
    signal_quality: dict[str, Any],
    target_top_functions: list[dict[str, Any]],
    by_workload: list[dict[str, Any]],
    workload_kind_counts: Counter[str],
) -> list[str]:
    recommendations: list[str] = []
    reasons = set(signal_quality.get("low_signal_reasons") or [])

    if "target_file_under_20pct" in reasons:
        recommendations.append(
            "Target file contributes under 20% of hotspot time; add tighter harness/property workloads to isolate target logic."
        )
    if "non_project_dominant" in reasons:
        dominant = signal_quality.get("dominant_ownership_bucket") or "non-project"
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

    low_signal_workloads = [
        item
        for item in by_workload
        if bool((item.get("signal") or {}).get("low_signal", False))
    ]
    if low_signal_workloads:
        first = low_signal_workloads[0]
        recommendations.append(
            f"Workload {first.get('workload_id', 'unknown')} has low project share; inspect workload scope and trim setup/fixture overhead."
        )

    return recommendations[:6]


def summarize_hotspots(records: list[dict], limit: int = 12, target_file: str | Path | None = None) -> dict:
    by_workload: list[dict[str, Any]] = []
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
    project_like_buckets = {"project", "candidate-overlay"}
    normalized_target_file = _normalized_profile_path(str(target_file)) if target_file else ""

    for item in records:
        profile = item.get("profile", {})
        functions = list(profile.get("functions", []))
        ownership = list(profile.get("ownership", []))
        workload_kind = str(item.get("workload_kind", "unknown"))
        workload_label = str(item.get("workload_label", ""))
        workload_selector = str(item.get("workload_selector", ""))
        workload_kind_counts[workload_kind] += 1
        workload_total_time = sum(float(fn.get("cumulative_time_s", 0.0)) for fn in functions)
        workload_project_time = sum(
            float(fn.get("cumulative_time_s", 0.0))
            for fn in functions
            if str(fn.get("ownership", "")) in project_like_buckets
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
        by_workload.append(
            {
                "workload_id": item["workload_id"],
                "workload_kind": workload_kind,
                "workload_label": workload_label,
                "workload_selector": workload_selector,
                "success": item.get("success", False),
                "top_functions": functions[:limit],
                "ownership": ownership,
                "stderr": item.get("stderr", ""),
                "signal": {
                    "project_share": round(workload_project_share, 4),
                    "target_share": round(workload_target_share, 4),
                    "dominant_ownership_bucket": dominant_bucket,
                    "total_cumulative_time_s": round(workload_total_time, 6),
                    "low_signal": workload_total_time > 0 and workload_project_share < 0.2,
                },
            }
        )
        for fn in functions:
            key = (fn["file"], int(fn["line"]), fn["function"], fn["ownership"])
            agg = aggregate_functions[key]
            agg["file"] = fn["file"]
            agg["line"] = int(fn["line"])
            agg["function"] = fn["function"]
            agg["ownership"] = fn["ownership"]
            agg["cumulative_time_s"] += float(fn["cumulative_time_s"])
            agg["total_time_s"] += float(fn["total_time_s"])
            agg["total_calls"] += int(fn["total_calls"])
        for owner in ownership:
            ownership_totals[str(owner["bucket"])] += float(owner["cumulative_time_s"])

    all_functions_raw = sorted(aggregate_functions.values(), key=lambda item: item["cumulative_time_s"], reverse=True)
    merged_ownership = [
        {"bucket": bucket, "cumulative_time_s": total}
        for bucket, total in sorted(ownership_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    total_cumulative = sum(float(item["cumulative_time_s"]) for item in all_functions_raw)
    all_functions = [_enrich_hotspot_function(item, total_cumulative=total_cumulative) for item in all_functions_raw]
    merged_functions = all_functions[:limit]
    project_cumulative = sum(float(total) for bucket, total in ownership_totals.items() if bucket in project_like_buckets)
    target_matches = [
        fn
        for fn in all_functions
        if normalized_target_file and _normalized_profile_path(str(fn["file"])) == normalized_target_file
    ]
    target_cumulative = sum(float(item.get("cumulative_time_s", 0.0)) for item in target_matches)
    target_top_functions = target_matches[:limit]

    project_top_functions = [
        fn
        for fn in all_functions
        if str(fn.get("ownership", "")) in project_like_buckets
    ][:limit]
    non_project_top_functions = [
        fn
        for fn in all_functions
        if str(fn.get("ownership", "")) not in project_like_buckets
    ][:limit]

    project_share = project_cumulative / total_cumulative if total_cumulative > 0 else 0.0
    target_share = target_cumulative / total_cumulative if total_cumulative > 0 else 0.0
    dominant_bucket = merged_ownership[0]["bucket"] if merged_ownership else None
    low_signal_reasons: list[str] = []
    if total_cumulative <= 0:
        low_signal_reasons.append("no_profile_samples")
    if normalized_target_file and target_share < 0.2:
        low_signal_reasons.append("target_file_under_20pct")
    if dominant_bucket and dominant_bucket not in project_like_buckets:
        low_signal_reasons.append("non_project_dominant")

    by_workload.sort(key=lambda item: float((item.get("signal") or {}).get("project_share", 0.0)), reverse=True)

    strongest_workload = by_workload[0] if by_workload else None
    weakest_workload = by_workload[-1] if by_workload else None

    signal_quality = {
        "total_cumulative_time_s": total_cumulative,
        "project_cumulative_time_s": project_cumulative,
        "target_cumulative_time_s": target_cumulative,
        "project_share": round(project_share, 4),
        "target_share": round(target_share, 4),
        "low_signal": bool(low_signal_reasons),
        "low_signal_reasons": low_signal_reasons,
        "dominant_ownership_bucket": dominant_bucket,
    }
    recommendations = _hotspot_recommendations(
        signal_quality=signal_quality,
        target_top_functions=target_top_functions,
        by_workload=by_workload,
        workload_kind_counts=workload_kind_counts,
    )
    strongest_signal = None
    weakest_signal = None
    if strongest_workload is not None:
        strongest_signal = {
            "workload_id": strongest_workload.get("workload_id"),
            "workload_kind": strongest_workload.get("workload_kind"),
            "project_share": (strongest_workload.get("signal") or {}).get("project_share", 0.0),
            "target_share": (strongest_workload.get("signal") or {}).get("target_share", 0.0),
        }
    if weakest_workload is not None:
        weakest_signal = {
            "workload_id": weakest_workload.get("workload_id"),
            "workload_kind": weakest_workload.get("workload_kind"),
            "project_share": (weakest_workload.get("signal") or {}).get("project_share", 0.0),
            "target_share": (weakest_workload.get("signal") or {}).get("target_share", 0.0),
        }

    return {
        "schema_version": 2,
        "by_workload": by_workload,
        "top_functions": merged_functions,
        "target_top_functions": target_top_functions,
        "project_top_functions": project_top_functions,
        "non_project_top_functions": non_project_top_functions,
        "ownership": merged_ownership,
        "workload_kind_counts": dict(workload_kind_counts.most_common()),
        "signal_quality": signal_quality,
        "insights": {
            "primary_target_hotspot": target_top_functions[0] if target_top_functions else None,
            "strongest_signal_workload": strongest_signal,
            "weakest_signal_workload": weakest_signal,
            "profiled_workload_count": len(by_workload),
        },
        "recommendations": recommendations,
    }


def build_optimization_analysis(
    *,
    run_id: str,
    target_qualname: str,
    baseline: MeasurementReport,
    candidates: list[CandidateRecord],
    events: list[dict],
    best_candidate_id: str | None,
    hotspot_summary: dict | None = None,
) -> dict:
    accepted = [item for item in candidates if item["status"] == "accepted"]
    return {
        "run_id": run_id,
        "target": target_qualname,
        "baseline": baseline.to_record(),
        "search": summarize_search_events(events),
        "operators": summarize_operator_performance(candidates, baseline.aggregate.to_record()),
        "best_candidate_id": best_candidate_id,
        "accepted_candidate_ids": [item["candidate_id"] for item in accepted],
        "hotspots": hotspot_summary,
    }


def build_baseline_analysis(*, run_id: str, target_qualname: str, report: MeasurementReport, hotspot_summary: dict | None) -> dict:
    return {
        "run_id": run_id,
        "target": target_qualname,
        "baseline": report.to_record(),
        "hotspots": hotspot_summary,
    }


def human_baseline_summary(report: MeasurementReport, bundle_notes: list[str], hotspot_summary: dict | None = None) -> str:
    aggregate = report.aggregate
    lines = [
        f"Run: {report.run_id}",
        "Aggregate: "
        f"latency={aggregate.mean_wall_time_s:.6f}s energy={aggregate.mean_energy_j:.6f}J "
        f"memory={aggregate.mean_peak_memory_bytes / (1024 * 1024):.3f}MiB "
        f"repetitions={aggregate.repetitions} success_rate={aggregate.success_rate:.2f}",
    ]
    if report.per_workload:
        lines.append("Workloads:")
        for item in report.per_workload:
            lines.append(
                f"  - {item.workload_id}: "
                f"latency={item.mean_wall_time_s:.6f}s energy={item.mean_energy_j:.6f}J "
                f"memory={item.mean_peak_memory_bytes / (1024 * 1024):.3f}MiB"
            )
    if bundle_notes:
        lines.append("Notes: " + "; ".join(bundle_notes))
    if hotspot_summary and hotspot_summary.get("top_functions"):
        top = hotspot_summary["top_functions"][0]
        lines.append(
            "Hotspot: "
            f"{Path(top['file']).name}:{top['line']}::{top['function']} "
            f"cum={top['cumulative_time_s']:.4f}s owner={top['ownership']}"
        )
        signal_quality = hotspot_summary.get("signal_quality") or {}
        if signal_quality:
            lines.append(
                "Hotspot quality: "
                f"project_share={signal_quality.get('project_share', 0.0)} "
                f"target_share={signal_quality.get('target_share', 0.0)}"
            )
        if signal_quality.get("low_signal"):
            lines.append(
                "Hotspot signal: low target coverage; inspect hotspots.json signal_quality/ownership details"
            )
        recommendations = hotspot_summary.get("recommendations") or []
        if recommendations:
            lines.append(f"Hotspot recommendation: {recommendations[0]}")
    return "\n".join(lines)


def human_run_summary(summary: dict) -> str:
    baseline = summary["baseline"]["aggregate"]
    lines = [
        f"Run: {summary['run_id']}",
        f"Baseline: latency={baseline['mean_wall_time_s']:.6f}s energy={baseline['mean_energy_j']:.6f}J memory={baseline['mean_peak_memory_bytes'] / (1024 * 1024):.3f}MiB",
    ]
    analysis = summary.get("analysis") or {}
    search = analysis.get("search") or {}
    funnel = search.get("funnel") or {}
    if funnel:
        lines.append(
            "Funnel: "
            f"generated={funnel.get('generated', 0)} "
            f"correctness_rejected={funnel.get('correctness_rejected', 0)} "
            f"surrogate_rejected={funnel.get('surrogate_rejected', 0)} "
            f"accepted={funnel.get('accepted', 0)}"
        )
    best = summary.get("best_candidate")
    if best:
        lines.append(
            "Best: "
            f"{best['candidate_id']} via {best['operator_name']} "
            f"{best.get('improvement_summary', {}).get('summary', '')}".strip()
        )
    else:
        lines.append("Best: none accepted")
    reasons = search.get("rejection_reasons") or {}
    if reasons:
        top_reason = next(iter(reasons.items()))
        lines.append(f"Top rejection: {top_reason[0]} ({top_reason[1]})")
    artifact_paths = summary.get("artifact_paths") or {}
    if artifact_paths:
        lines.append("Artifacts: " + ", ".join(f"{key}={value}" for key, value in artifact_paths.items()))
    return "\n".join(lines)


def _metrics_text_from_record(record: dict[str, Any]) -> str:
    return (
        f"latency={float(record.get('mean_wall_time_s', 0.0)):.6f}s "
        f"energy={float(record.get('mean_energy_j', 0.0)):.6f}J "
        f"memory={float(record.get('mean_peak_memory_bytes', 0.0)) / (1024 * 1024):.3f}MiB "
        f"repetitions={int(record.get('repetitions', 0))} "
        f"success_rate={float(record.get('success_rate', 0.0)):.2f}"
    )


def human_baseline_analysis_summary(payload: dict[str, Any]) -> str:
    baseline = payload.get("baseline") or {}
    aggregate = baseline.get("aggregate") or {}
    lines = [
        f"Run: {payload.get('run_id', 'unknown')}",
        f"Target: {payload.get('target', 'unknown')}",
    ]
    if aggregate:
        lines.append("Aggregate: " + _metrics_text_from_record(aggregate))
    hotspots = payload.get("hotspots") or {}
    if hotspots:
        top_functions = hotspots.get("top_functions") or []
        lines.append(f"Hotspots: top_functions={len(top_functions)}")
        signal_quality = hotspots.get("signal_quality") or {}
        if signal_quality:
            lines.append(
                "Hotspot signal: "
                f"low_signal={signal_quality.get('low_signal', False)} "
                f"target_share={signal_quality.get('target_share', 0.0)}"
            )
        recommendations = hotspots.get("recommendations") or []
        if recommendations:
            lines.append(f"Hotspot recommendation: {recommendations[0]}")
    else:
        lines.append("Hotspots: none")
    return "\n".join(lines)


def human_discover_summary(payload: list[dict[str, Any]]) -> str:
    lines = [f"Discover: {len(payload)} target(s)"]
    preview = payload[:10]
    for item in preview:
        target = item.get("target") or {}
        qualname = target.get("qualname", "unknown")
        score = item.get("score", 0)
        workloads = item.get("workloads") or []
        provenance = item.get("workload_provenance") or []
        lines.append(
            f"- {qualname}: score={score} workloads={len(workloads)} provenance={len(provenance)}"
        )
    if len(payload) > len(preview):
        lines.append(f"... {len(payload) - len(preview)} more target(s)")
    return "\n".join(lines)


def json_pretty(payload: Any) -> str:
    return json.dumps(payload, indent=2)


def candidate_detail_payload(candidate: dict, measurements: list[dict]) -> dict:
    return {
        "candidate": candidate,
        "measurements": [item for item in measurements if item.get("candidate_id") == candidate["candidate_id"]],
    }


def human_json_payload_summary(payload: Any) -> str:
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and "target" in payload[0]:
            return human_discover_summary(payload)
        return f"JSON list payload with {len(payload)} item(s)"
    if not isinstance(payload, dict):
        return f"JSON payload type: {type(payload).__name__}"
    if "run" in payload and "summary" in payload:
        return human_inspect_summary(payload)
    if "candidate" in payload and "measurements" in payload:
        return human_candidate_detail_summary(payload)
    if "analysis" in payload and "baseline" in payload and "run_id" in payload:
        return human_run_summary(payload)
    if "baseline" in payload and "target" in payload and "run_id" in payload:
        return human_baseline_analysis_summary(payload)
    return "Unsupported JSON payload shape; use --output json for raw data or inspect known artifact files"


def _measurement_issue_samples(measurements: list[dict], *, limit: int = 5) -> list[dict]:
    issues: list[dict] = []
    for report in measurements:
        for sample in report.get("samples", []):
            stderr = str(sample.get("stderr", "")).strip()
            success = bool(sample.get("success", False))
            if success and not stderr:
                continue
            issue = {
                "candidate_id": report.get("candidate_id"),
                "workload_id": sample.get("workload_id"),
                "fidelity": sample.get("fidelity"),
                "success": success,
                "return_code": sample.get("return_code"),
                "stderr_excerpt": stderr.splitlines()[0][:180] if stderr else "",
            }
            issues.append(issue)
            if len(issues) >= limit:
                return issues
    return issues


def summarize_inspect_payload(
    *,
    candidates: list[dict],
    measurements: list[dict],
    search_events: list[dict],
    hotspots: list[dict],
    artifacts: list[dict],
    apply_audits: list[dict],
    filesystem_artifacts: list[str] | None = None,
) -> dict:
    candidate_status = Counter(item.get("status", "unknown") for item in candidates)
    dependency_review_required = sum(
        1
        for item in candidates
        if parse_candidate_metadata(item.get("metadata", {})).dependency_policy_state == "review_required"
    )
    search_summary = summarize_search_events(search_events)
    generated_events = int(search_summary.get("funnel", {}).get("generated", 0))
    terminal_events = sum(int(search_summary.get("funnel", {}).get(key, 0)) for key in TERMINAL_EVENT_TYPES)
    event_counts = search_summary.get("event_counts", {})

    db_artifact_names = {str(item.get("name", "")) for item in artifacts if item.get("name")}
    artifact_count = len(artifacts)
    artifact_counts: dict[str, int] = {"db_recorded": artifact_count}
    artifact_reconciliation: dict[str, Any] | None = None
    if filesystem_artifacts is not None:
        filesystem_names = {str(name) for name in filesystem_artifacts}
        missing_in_db = sorted(filesystem_names - db_artifact_names)
        db_only = sorted(db_artifact_names - filesystem_names)
        artifact_counts["filesystem_files"] = len(filesystem_names)
        artifact_reconciliation = {
            "in_sync": not missing_in_db and not db_only,
            "missing_db_records": len(missing_in_db),
            "db_only_records": len(db_only),
            "missing_db_record_examples": missing_in_db[:10],
            "db_only_record_examples": db_only[:10],
        }

    summary = {
        "candidate_counts": {
            "total": len(candidates),
            "accepted": candidate_status.get("accepted", 0),
            "rejected": candidate_status.get("rejected", 0),
            "skipped": candidate_status.get("skipped", 0),
            "dependency_review_required": dependency_review_required,
        },
        "search_consistency": {
            "generated_events": generated_events,
            "terminal_events": terminal_events,
            "candidate_records": len(candidates),
            "generated_minus_candidates": generated_events - len(candidates),
            "terminal_minus_candidates": terminal_events - len(candidates),
            "frontier_dominated_events": int(event_counts.get("frontier_dominated", 0)),
        },
        "measurement_reports": len(measurements),
        "search_event_count": len(search_events),
        "hotspot_profile_count": len(hotspots),
        "artifact_count": artifact_count,
        "artifact_counts": artifact_counts,
        "apply_audit_count": len(apply_audits),
        "top_rejection": next(iter((search_summary.get("rejection_reasons") or {}).items()), None),
        "measurement_issues": _measurement_issue_samples(measurements),
    }
    if artifact_reconciliation is not None:
        summary["artifact_reconciliation"] = artifact_reconciliation
    return summary


def human_candidate_detail_summary(candidate_payload: dict) -> str:
    candidate = candidate_payload["candidate"]
    measurements = candidate_payload.get("measurements", [])
    metadata = parse_candidate_metadata(candidate.get("metadata", {}))
    lines = [
        f"Candidate: {candidate['candidate_id']}",
        f"Status: {candidate['status']} via {candidate['operator_name']}",
        f"Parent: {candidate.get('parent_id')}",
        f"Stage: {metadata.stage or 'unknown'} phase={metadata.phase or 'unknown'}",
        f"Dependency policy: {metadata.dependency_policy_state}",
        f"Measurements: {len(measurements)} report(s)",
    ]
    if metadata.improvement_summary.summary:
        lines.append(f"Improvement: {metadata.improvement_summary.summary}")
    if metadata.rejected:
        lines.append(f"Rejected: {metadata.rejected}")
    return "\n".join(lines)


def human_inspect_summary(payload: dict) -> str:
    run = payload["run"]
    summary = payload.get("summary", {})
    candidate_counts = summary.get("candidate_counts", {})
    search_consistency = summary.get("search_consistency", {})
    artifact_counts = summary.get("artifact_counts", {})
    lines = [
        f"Run: {run['run_id']} ({run['run_type']}) status={run['status']}",
        f"Target: {run['target']['qualname']}",
        f"Workloads: {len(run['bundle'].get('workloads', []))}",
        (
            "Candidates: "
            f"total={candidate_counts.get('total', 0)} "
            f"accepted={candidate_counts.get('accepted', 0)} "
            f"rejected={candidate_counts.get('rejected', 0)} "
            f"skipped={candidate_counts.get('skipped', 0)}"
        ),
        (
            "Diagnostics: "
            f"measurement_reports={summary.get('measurement_reports', 0)} "
            f"search_events={summary.get('search_event_count', 0)} "
            f"hotspots={summary.get('hotspot_profile_count', 0)}"
        ),
    ]
    if search_consistency:
        lines.append(
            "Search consistency: "
            f"generated={search_consistency.get('generated_events', 0)} "
            f"candidates={search_consistency.get('candidate_records', 0)} "
            f"terminal={search_consistency.get('terminal_events', 0)} "
            f"frontier_dominated={search_consistency.get('frontier_dominated_events', 0)}"
        )
    if artifact_counts:
        artifact_line = "Artifacts: " + f"db={artifact_counts.get('db_recorded', 0)}"
        if "filesystem_files" in artifact_counts:
            artifact_line += f" filesystem={artifact_counts.get('filesystem_files', 0)}"
        lines.append(artifact_line)
    if summary.get("top_rejection"):
        reason, count = summary["top_rejection"]
        lines.append(f"Top rejection: {reason} ({count})")
    issues = summary.get("measurement_issues") or []
    surrogate = summary.get("surrogate_learning") or {}
    if surrogate:
        lines.append(
            "Surrogate learning: "
            f"stored={surrogate.get('stored_observations', 0)} "
            f"preview={surrogate.get('preview_count', 0)} "
            f"reuse={surrogate.get('reuse_enabled', False)} "
            f"warm_start_limit={surrogate.get('warm_start_limit', 0)}"
        )
    if issues:
        first = issues[0]
        lines.append(
            "Worker issue: "
            f"workload={first.get('workload_id')} fidelity={first.get('fidelity')} "
            f"success={first.get('success')} return_code={first.get('return_code')}"
        )
        if first.get("stderr_excerpt"):
            lines.append(f"Worker stderr: {first['stderr_excerpt']}")
    return "\n".join(lines)


def cross_run_trends(runs: list[dict]) -> dict:
    by_target: defaultdict[str, list[dict]] = defaultdict(list)
    for run in runs:
        metadata = run.get("metadata", {})
        target = metadata.get("target_qualname") or metadata.get("best_candidate", {}).get("target") or "unknown"
        aggregate = metadata.get("aggregate") or {}
        if aggregate:
            by_target[target].append(
                {
                    "run_id": run["run_id"],
                    "created_at": run["created_at"],
                    "energy_j": aggregate.get("mean_energy_j", 0.0),
                    "latency_s": aggregate.get("mean_wall_time_s", 0.0),
                    "memory_mb": aggregate.get("mean_peak_memory_bytes", 0.0) / (1024 * 1024),
                }
            )
    return {"targets": dict(by_target)}
