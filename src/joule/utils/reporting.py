from __future__ import annotations

import json

from joule.models import AggregateMetrics, MeasurementReport, WorkloadBundle


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
    for item in report.per_workload:
        lines.append(f"  - {item.workload_id}: {metrics_to_text(item)}")
    if bundle.notes:
        lines.append("Notes:")
        for note in bundle.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)


def measurement_to_json(report: MeasurementReport) -> str:
    return json.dumps(report.to_record(), indent=2)
