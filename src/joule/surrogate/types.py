from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from joule.models import AggregateMetrics, SearchPhase


FEATURE_SCHEMA_VERSION = 1
SURROGATE_DECISION_SCHEMA_VERSION = 2
METRIC_NAMES = ("energy", "latency", "memory")


@dataclass(slots=True)
class SurrogateMetricTargets:
    energy: float
    latency: float
    memory: float

    @classmethod
    def from_aggregate(cls, aggregate: AggregateMetrics) -> "SurrogateMetricTargets":
        return cls(
            energy=float(aggregate.mean_energy_j),
            latency=float(aggregate.mean_wall_time_s),
            memory=float(aggregate.mean_peak_memory_bytes),
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "SurrogateMetricTargets":
        return cls(
            energy=float(payload.get("energy", 0.0)),
            latency=float(payload.get("latency", 0.0)),
            memory=float(payload.get("memory", 0.0)),
        )

    def to_record(self) -> dict[str, float]:
        return {
            "energy": float(self.energy),
            "latency": float(self.latency),
            "memory": float(self.memory),
        }

    def get(self, metric: str) -> float:
        return float(getattr(self, metric))


@dataclass(slots=True)
class SurrogateObservation:
    source: str
    targets: SurrogateMetricTargets
    feature_hints: dict[str, float] = field(default_factory=dict)
    feature_schema_version: int = FEATURE_SCHEMA_VERSION


@dataclass(slots=True)
class SurrogateQuery:
    source: str
    feature_hints: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class MetricPrediction:
    mean: float
    uncertainty: float

    def to_record(self) -> dict[str, float]:
        return {
            "mean": float(self.mean),
            "uncertainty": float(self.uncertainty),
        }


@dataclass(slots=True)
class SurrogatePrediction:
    metrics: dict[str, MetricPrediction]
    predicted_score: float
    uncertainty: float
    model_kind: str
    fallback_used: bool = False

    def metric_means(self) -> SurrogateMetricTargets:
        return SurrogateMetricTargets(
            energy=float(self.metrics["energy"].mean),
            latency=float(self.metrics["latency"].mean),
            memory=float(self.metrics["memory"].mean),
        )

    def metric_uncertainties(self) -> SurrogateMetricTargets:
        return SurrogateMetricTargets(
            energy=float(self.metrics["energy"].uncertainty),
            latency=float(self.metrics["latency"].uncertainty),
            memory=float(self.metrics["memory"].uncertainty),
        )


@dataclass(slots=True)
class SurrogateScreeningDecision:
    decision: str
    reason: str
    predicted_score: float
    uncertainty: float
    novelty: float
    acquisition_score: float
    expected_improvement: float
    model_kind: str
    acquisition: str
    objective_kind: str
    objective_weights: tuple[float, float, float]
    predicted_metrics: SurrogateMetricTargets
    metric_uncertainties: SurrogateMetricTargets
    phase: SearchPhase
    schema_version: int = SURROGATE_DECISION_SCHEMA_VERSION

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "decision": self.decision,
            "reason": self.reason,
            "predicted_score": float(self.predicted_score),
            "uncertainty": float(self.uncertainty),
            "novelty": float(self.novelty),
            "acquisition_score": float(self.acquisition_score),
            "expected_improvement": float(self.expected_improvement),
            "model_kind": self.model_kind,
            "acquisition": self.acquisition,
            "objective_kind": self.objective_kind,
            "objective_weights": list(self.objective_weights),
            "predicted_metrics": self.predicted_metrics.to_record(),
            "metric_uncertainties": self.metric_uncertainties.to_record(),
            "phase": self.phase.value,
        }
