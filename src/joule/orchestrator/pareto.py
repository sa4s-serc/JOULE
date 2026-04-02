from __future__ import annotations

from dataclasses import dataclass

from joule.models import AggregateMetrics


@dataclass(slots=True)
class ParetoPoint:
    candidate_id: str
    metrics: AggregateMetrics


class ParetoFront:
    def __init__(self) -> None:
        self._points: list[ParetoPoint] = []

    def add(self, point: ParetoPoint) -> None:
        survivors = [item for item in self._points if not _dominates(point.metrics, item.metrics)]
        if any(_dominates(item.metrics, point.metrics) for item in survivors):
            return
        survivors.append(point)
        self._points = survivors

    def best(self) -> ParetoPoint | None:
        if not self._points:
            return None
        return min(
            self._points,
            key=lambda item: item.metrics.mean_energy_j * 0.5
            + item.metrics.mean_wall_time_s * 0.3
            + item.metrics.mean_peak_memory_bytes * 0.2,
        )

    def points(self) -> list[ParetoPoint]:
        return list(self._points)


def _dominates(left: AggregateMetrics, right: AggregateMetrics) -> bool:
    return (
        left.mean_energy_j <= right.mean_energy_j
        and left.mean_wall_time_s <= right.mean_wall_time_s
        and left.mean_peak_memory_bytes <= right.mean_peak_memory_bytes
        and (
            left.mean_energy_j < right.mean_energy_j
            or left.mean_wall_time_s < right.mean_wall_time_s
            or left.mean_peak_memory_bytes < right.mean_peak_memory_bytes
        )
    )
