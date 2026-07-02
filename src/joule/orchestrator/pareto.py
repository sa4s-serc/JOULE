from __future__ import annotations

import math
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
    # Beta for the UCB parent selection formula.
    # Higher values favour exploration (expanding less-visited frontier points).
    UCB_BETA: float = 1.0

    def __init__(self, *, weights: tuple[float, float, float] = (0.5, 0.3, 0.2)) -> None:
        self._points: list[ParetoPoint] = []
        self._weights = weights
        self._expansions: dict[str, int] = {}
        self._total_expansions: int = 0

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
        # Remove stale expansion counts for candidates that are no longer on the frontier.
        for dominated_id in dominated_ids:
            self._expansions.pop(dominated_id, None)
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

        total = max(1, self._total_expansions)

        def _ucb_key(item: ParetoPoint) -> float:
            expansion_count = self._expansions.get(item.candidate_id, 0)
            # Exploitation: weighted objective score (lower is better, negate for sort)
            exploit = -self.weighted_score(item.metrics)
            # Exploration: UCB bonus — large when expansion_count is low
            explore = self.UCB_BETA * math.sqrt(math.log(total + 1) / (expansion_count + 1))
            # Depth bias: positive when prefer_deeper=True, negative when prefer_deeper=False.
            # Magnitude is intentionally small so UCB score remains the primary driver.
            depth_bias = (item.generation_depth * 0.001) if prefer_deeper else -(item.generation_depth * 0.001)
            return exploit + explore + depth_bias

        selected = max(choices, key=_ucb_key)
        return selected.candidate_id


    def record_expansion(self, candidate_id: str) -> None:
        self._expansions[candidate_id] = self._expansions.get(candidate_id, 0) + 1
        self._total_expansions += 1

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
    # All comparisons use raw bytes for memory — unit-agnostic for dominance checks.
    # weighted_score() converts to MiB for scoring, but dominance only needs consistent units.
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
