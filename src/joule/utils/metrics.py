from __future__ import annotations

from collections import defaultdict
import math

from joule.models import AggregateMetrics, MetricSample


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return sum((value - avg) ** 2 for value in values) / (len(values) - 1)


def ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return 1.96 * math.sqrt(variance(values)) / math.sqrt(len(values))


def aggregate_samples(samples: list[MetricSample]) -> tuple[AggregateMetrics, list[AggregateMetrics]]:
    if not samples:
        empty = AggregateMetrics(
            workload_id="all",
            repetitions=0,
            success_rate=0.0,
            mean_wall_time_s=0.0,
            mean_cpu_time_s=0.0,
            mean_peak_memory_bytes=0.0,
            mean_energy_j=0.0,
            wall_time_ci95=0.0,
            cpu_time_ci95=0.0,
            peak_memory_ci95=0.0,
            energy_ci95=0.0,
        )
        return empty, []

    grouped: dict[str, list[MetricSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.workload_id].append(sample)

    per_workload = [_aggregate_group(workload_id, group) for workload_id, group in grouped.items()]
    overall = _aggregate_group("all", samples)
    return overall, per_workload


def scalar_score(metrics: AggregateMetrics) -> float:
    return (
        (metrics.mean_energy_j * 0.5)
        + (metrics.mean_wall_time_s * 0.3)
        + ((metrics.mean_peak_memory_bytes / (1024 * 1024)) * 0.2)
    )


def improvement_ratio(baseline: AggregateMetrics, candidate: AggregateMetrics) -> dict[str, float]:
    def safe(base: float, new: float) -> float:
        if base <= 0:
            return 0.0
        return (base - new) / base

    return {
        "energy": safe(baseline.mean_energy_j, candidate.mean_energy_j),
        "latency": safe(baseline.mean_wall_time_s, candidate.mean_wall_time_s),
        "memory": safe(baseline.mean_peak_memory_bytes, candidate.mean_peak_memory_bytes),
    }


def _aggregate_group(workload_id: str, group: list[MetricSample]) -> AggregateMetrics:
    walls = [item.wall_time_s for item in group]
    cpus = [item.cpu_time_s for item in group]
    memories = [float(item.peak_memory_bytes) for item in group]
    energies = [item.energy_j for item in group]
    successes = [1.0 if item.success else 0.0 for item in group]
    return AggregateMetrics(
        workload_id=workload_id,
        repetitions=len(group),
        success_rate=mean(successes),
        mean_wall_time_s=mean(walls),
        mean_cpu_time_s=mean(cpus),
        mean_peak_memory_bytes=mean(memories),
        mean_energy_j=mean(energies),
        wall_time_ci95=ci95(walls),
        cpu_time_ci95=ci95(cpus),
        peak_memory_ci95=ci95(memories),
        energy_ci95=ci95(energies),
    )
