from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from joule.models import AggregateMetrics
from joule.utils.metrics import weighted_score


@dataclass(slots=True)
class ParetoPoint:
    candidate_id: str
    metrics: AggregateMetrics
    parent_id: str | None = None
    generation_depth: int = 0
    operator_name: str = "baseline"
    active: bool = True


class ParetoFront:
    def __init__(self, *, weights: tuple[float, float, float] = (0.5, 0.3, 0.2)) -> None:
        self._points: list[ParetoPoint] = []
        self._weights = weights
        self._expansions: dict[str, int] = {}

    def add(self, point: ParetoPoint) -> dict[str, Any]:
        dominated_ids = [item.candidate_id for item in self._points if _dominates(point.metrics, item.metrics)]
        survivors = [item for item in self._points if item.candidate_id not in dominated_ids]
        dominating_ids = [item.candidate_id for item in survivors if _dominates(item.metrics, point.metrics)]
        if dominating_ids:
            return {
                "accepted": False,
                "dominated_by": dominating_ids,
                "dominated_ids": [],
            }
        survivors.append(point)
        self._points = survivors
        self._expansions.setdefault(point.candidate_id, 0)
        return {
            "accepted": True,
            "dominated_by": [],
            "dominated_ids": dominated_ids,
        }

    def best(self, *, exclude_ids: set[str] | None = None) -> ParetoPoint | None:
        points = [item for item in self._points if exclude_ids is None or item.candidate_id not in exclude_ids]
        if not points:
            return None
        return min(points, key=lambda item: self.weighted_score(item.metrics))

    def weighted_score(self, metrics: AggregateMetrics) -> float:
        return weighted_score(metrics, self._weights)

    def expansion_counts(self) -> dict[str, int]:
        return dict(self._expansions)

    def load_expansion_counts(self, counts: dict[str, int]) -> None:
        self._expansions = {candidate_id: max(0, int(count)) for candidate_id, count in counts.items()}
        for point in self._points:
            self._expansions.setdefault(point.candidate_id, 0)

    def dominance_summary(self, metrics: AggregateMetrics) -> dict[str, Any]:
        dominated_by = [item.candidate_id for item in self._points if _dominates(item.metrics, metrics)]
        dominates = [item.candidate_id for item in self._points if _dominates(metrics, item.metrics)]
        return {
            "dominated": bool(dominated_by),
            "dominated_by": dominated_by,
            "dominates": dominates,
            "frontier_size": len(self._points),
        }

    def sample_active_parent(self, *, max_generation: int, prefer_deeper: bool = False) -> str | None:
        choices = [item for item in self._points if item.active and item.generation_depth < max_generation]
        if not choices:
            return None
        selected = min(
            choices,
            key=lambda item: (
                self._expansions.get(item.candidate_id, 0),
                -item.generation_depth if prefer_deeper else item.generation_depth,
                self.weighted_score(item.metrics),
                item.candidate_id,
            ),
        )
        self._expansions[selected.candidate_id] = self._expansions.get(selected.candidate_id, 0) + 1
        return selected.candidate_id

    def mark_exhausted(self, candidate_id: str) -> None:
        for item in self._points:
            if item.candidate_id == candidate_id:
                item.active = False
                return

    def expansion_count(self, candidate_id: str) -> int:
        return self._expansions.get(candidate_id, 0)

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
