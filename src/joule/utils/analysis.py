from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json

from joule.models import MeasurementReport
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


def candidate_source_hash(source: str) -> str:
    import hashlib

    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def summarize_search_events(events: list[dict]) -> dict:
    funnel = {key: 0 for key in FUNNEL_ORDER}
    rejection_reasons: Counter[str] = Counter()
    stage_timings: defaultdict[str, float] = defaultdict(float)
    for event in events:
        event_type = event["event_type"]
        detail = event.get("detail", {})
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
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "stage_timings_s": dict(stage_timings),
    }


def summarize_operator_performance(candidates: list[dict], baseline_aggregate: dict | None = None) -> list[dict]:
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
        stage = item.get("metadata", {}).get("stage")
        if stage:
            entry["stage_reached"][str(stage)] += 1
        reason = item.get("metadata", {}).get("rejected")
        if reason:
            entry["rejection_reasons"][str(reason)] += 1
        improvement = item.get("metadata", {}).get("improvement_summary")
        if isinstance(improvement, dict):
            entry["improvements"].append(
                {
                    "energy": float(improvement.get("energy", 0.0)),
                    "latency": float(improvement.get("latency", 0.0)),
                    "memory": float(improvement.get("memory", 0.0)),
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
        entry["acceptance_rate"] = entry["accepted"] / max(entry["attempts"], 1)
        results.append(entry)
    results.sort(key=lambda item: (-item["acceptance_rate"], -item["attempts"], item["operator_name"]))
    return results


def summarize_hotspots(records: list[dict], limit: int = 12) -> dict:
    by_workload = []
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
    for item in records:
        profile = item.get("profile", {})
        functions = list(profile.get("functions", []))
        ownership = list(profile.get("ownership", []))
        by_workload.append(
            {
                "workload_id": item["workload_id"],
                "success": item.get("success", False),
                "top_functions": functions[:limit],
                "ownership": ownership,
                "stderr": item.get("stderr", ""),
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
    merged_functions = sorted(aggregate_functions.values(), key=lambda item: item["cumulative_time_s"], reverse=True)[:limit]
    merged_ownership = [
        {"bucket": bucket, "cumulative_time_s": total}
        for bucket, total in sorted(ownership_totals.items(), key=lambda item: item[1], reverse=True)
    ]
    return {"by_workload": by_workload, "top_functions": merged_functions, "ownership": merged_ownership}


def build_optimization_analysis(
    *,
    run_id: str,
    target_qualname: str,
    baseline: MeasurementReport,
    candidates: list[dict],
    events: list[dict],
    hotspot_summary: dict | None = None,
) -> dict:
    accepted = [item for item in candidates if item["status"] == "accepted"]
    best = accepted[0] if accepted else None
    return {
        "run_id": run_id,
        "target": target_qualname,
        "baseline": baseline.to_record(),
        "search": summarize_search_events(events),
        "operators": summarize_operator_performance(candidates, baseline.aggregate.to_record()),
        "best_candidate_id": best["candidate_id"] if best else None,
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


def json_pretty(payload: dict) -> str:
    return json.dumps(payload, indent=2)


def candidate_detail_payload(candidate: dict, measurements: list[dict]) -> dict:
    return {
        "candidate": candidate,
        "measurements": [item for item in measurements if item.get("candidate_id") == candidate["candidate_id"]],
    }


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
