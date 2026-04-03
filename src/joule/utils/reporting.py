from __future__ import annotations

import json

from joule.models import AggregateMetrics, MeasurementReport, WorkloadBundle
from joule.utils.metrics import improvement_ratio


def metrics_to_text(metrics: AggregateMetrics) -> str:
    memory_mb = metrics.mean_peak_memory_bytes / (1024 * 1024)
    ci_mb = metrics.peak_memory_ci95 / (1024 * 1024)
    return (
        f"repetitions={metrics.repetitions} "
        f"success_rate={metrics.success_rate:.2f} "
        f"latency={metrics.mean_wall_time_s:.6f}s +/- {metrics.wall_time_ci95:.6f} "
        f"cpu={metrics.mean_cpu_time_s:.6f}s +/- {metrics.cpu_time_ci95:.6f} "
        f"memory={memory_mb:.3f}MiB +/- {ci_mb:.3f} "
        f"energy={metrics.mean_energy_j:.6f}J +/- {metrics.energy_ci95:.6f}"
    )


def baseline_report_text(bundle: WorkloadBundle, report: MeasurementReport) -> str:
    lines = [
        f"Run: {report.run_id}",
        f"Target: {bundle.target.qualname} ({bundle.target.file_path})",
        f"Aggregate: {metrics_to_text(report.aggregate)}",
        "Workloads:",
    ]
    workload_map = {workload.identifier: workload for workload in bundle.workloads}
    for item in report.per_workload:
        workload = workload_map.get(item.workload_id)
        provenance = format_workload_provenance(workload.metadata) if workload else "unknown"
        lines.append(f"  - {item.workload_id}: {metrics_to_text(item)} [{provenance}]")
    if bundle.notes:
        lines.append("Notes:")
        for note in bundle.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)


def measurement_to_json(report: MeasurementReport) -> str:
    return json.dumps(report.to_record(), indent=2)


def workload_provenance_records(bundle: WorkloadBundle) -> list[dict]:
    return [
        {
            "identifier": workload.identifier,
            "kind": workload.kind.value,
            "selector": workload.selector,
            "provenance": workload.metadata.get("provenance", "unknown"),
            "resolution_strategy": workload.metadata.get("resolution_strategy", "unknown"),
            "alignment_score": workload.metadata.get("alignment_score"),
        }
        for workload in bundle.workloads
    ]


def format_workload_provenance(metadata: dict | None) -> str:
    if not metadata:
        return "unknown"
    provenance = metadata.get("provenance", "unknown")
    resolution = metadata.get("resolution_strategy")
    if resolution:
        return f"{provenance}/{resolution}"
    return str(provenance)


def improvement_summary(baseline: AggregateMetrics, candidate: AggregateMetrics) -> dict[str, float | str]:
    delta = improvement_ratio(baseline, candidate)
    summary = (
        f"energy={delta['energy']:.1%} "
        f"latency={delta['latency']:.1%} "
        f"memory={delta['memory']:.1%}"
    )
    return {"energy": delta["energy"], "latency": delta["latency"], "memory": delta["memory"], "summary": summary}
