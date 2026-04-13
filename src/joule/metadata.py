from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


CANDIDATE_METADATA_SCHEMA_VERSION = 1
SURROGATE_DECISION_SCHEMA_VERSION = 1
SEARCH_EVENT_DETAIL_SCHEMA_VERSION = 1


@dataclass(slots=True)
class SurrogateDecision:
    decision: str = ""
    reason: str = ""
    predicted_score: float = 0.0
    uncertainty: float = 0.0
    novelty: float = 0.0
    acquisition_score: float = 0.0
    expected_improvement: float = 0.0
    model_mode: str = ""
    acquisition: str = ""
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
            "model_mode": self.model_mode,
            "acquisition": self.acquisition,
        }

    @classmethod
    def from_record(cls, payload: Mapping[str, Any] | None) -> "SurrogateDecision":
        if payload is None:
            return cls()
        return cls(
            decision=str(payload.get("decision", "")),
            reason=str(payload.get("reason", "")),
            predicted_score=float(payload.get("predicted_score", 0.0)),
            uncertainty=float(payload.get("uncertainty", 0.0)),
            novelty=float(payload.get("novelty", 0.0)),
            acquisition_score=float(payload.get("acquisition_score", 0.0)),
            expected_improvement=float(payload.get("expected_improvement", 0.0)),
            model_mode=str(payload.get("model_mode", "")),
            acquisition=str(payload.get("acquisition", "")),
            schema_version=int(payload.get("schema_version", SURROGATE_DECISION_SCHEMA_VERSION)),
        )


@dataclass(slots=True)
class ImprovementSummary:
    energy: float = 0.0
    latency: float = 0.0
    memory: float = 0.0
    summary: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "energy": float(self.energy),
            "latency": float(self.latency),
            "memory": float(self.memory),
            "summary": self.summary,
        }

    @classmethod
    def from_record(cls, payload: Mapping[str, Any] | None) -> "ImprovementSummary":
        if payload is None:
            return cls()
        return cls(
            energy=float(payload.get("energy", 0.0)),
            latency=float(payload.get("latency", 0.0)),
            memory=float(payload.get("memory", 0.0)),
            summary=str(payload.get("summary", "")),
        )


@dataclass(slots=True)
class CandidateMetadata:
    stage: str = ""
    phase: str = ""
    measurement_decision: str = ""
    measurement_cost_s: float = 0.0
    rejected: str | None = None
    reason: list[str] = field(default_factory=list)
    source_hash: str = ""
    parent_id: str = ""
    generation_depth: int = 0
    frontier_state: str = ""
    duplicate_of: str | None = None
    surrogate: SurrogateDecision = field(default_factory=SurrogateDecision)
    operator_family: str = ""
    operator_tier: str = ""
    operator_tier_descriptor: str = ""
    proposal_rank: int = 0
    generation_delta: int = 1
    composed_operator_chain: list[str] = field(default_factory=list)
    composition_hops: int = 0
    dependency_policy_state: str = "unknown"
    dependency_policy_reason: str = ""
    improvement: dict[str, float] = field(default_factory=dict)
    improvement_summary: ImprovementSummary = field(default_factory=ImprovementSummary)
    explanation_summary: str = ""
    schema_version: int = CANDIDATE_METADATA_SCHEMA_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **dict(self.extra),
            "schema_version": int(self.schema_version),
            "stage": self.stage,
            "phase": self.phase,
            "measurement_decision": self.measurement_decision,
            "measurement_cost_s": float(self.measurement_cost_s),
            "rejected": self.rejected,
            "reason": list(self.reason),
            "source_hash": self.source_hash,
            "parent_id": self.parent_id,
            "generation_depth": int(self.generation_depth),
            "frontier_state": self.frontier_state,
            "duplicate_of": self.duplicate_of,
            "surrogate": self.surrogate.to_record(),
            "operator_family": self.operator_family,
            "operator_tier": self.operator_tier,
            "operator_tier_descriptor": self.operator_tier_descriptor,
            "proposal_rank": int(self.proposal_rank),
            "generation_delta": int(self.generation_delta),
            "composed_operator_chain": list(self.composed_operator_chain),
            "composition_hops": int(self.composition_hops),
            "dependency_policy_state": self.dependency_policy_state,
            "dependency_policy_reason": self.dependency_policy_reason,
            "improvement": {key: float(value) for key, value in self.improvement.items()},
            "improvement_summary": self.improvement_summary.to_record(),
            "explanation_summary": self.explanation_summary,
        }
        return payload

    @classmethod
    def from_record(cls, payload: Mapping[str, Any] | None) -> "CandidateMetadata":
        if payload is None:
            return cls()

        reason_payload = payload.get("reason", [])
        if isinstance(reason_payload, list):
            reasons = [str(item) for item in reason_payload]
        elif reason_payload:
            reasons = [str(reason_payload)]
        else:
            reasons = []

        improvement_payload = payload.get("improvement", {})
        if isinstance(improvement_payload, Mapping):
            improvement = {
                str(key): float(value)
                for key, value in improvement_payload.items()
                if isinstance(value, (int, float))
            }
        else:
            improvement = {}

        known_fields = {
            "schema_version",
            "stage",
            "phase",
            "measurement_decision",
            "measurement_cost_s",
            "rejected",
            "reason",
            "source_hash",
            "parent_id",
            "generation_depth",
            "frontier_state",
            "duplicate_of",
            "surrogate",
            "operator_family",
            "operator_tier",
            "operator_tier_descriptor",
            "proposal_rank",
            "generation_delta",
            "composed_operator_chain",
            "composition_hops",
            "dependency_policy_state",
            "dependency_policy_reason",
            "improvement",
            "improvement_summary",
            "explanation_summary",
        }
        extra = {str(key): value for key, value in payload.items() if key not in known_fields}

        chain = payload.get("composed_operator_chain", [])
        return cls(
            schema_version=int(payload.get("schema_version", CANDIDATE_METADATA_SCHEMA_VERSION)),
            stage=str(payload.get("stage", "")),
            phase=str(payload.get("phase", "")),
            measurement_decision=str(payload.get("measurement_decision", "")),
            measurement_cost_s=float(payload.get("measurement_cost_s", 0.0)),
            rejected=(str(payload.get("rejected")) if payload.get("rejected") is not None else None),
            reason=reasons,
            source_hash=str(payload.get("source_hash", "")),
            parent_id=str(payload.get("parent_id", "")),
            generation_depth=int(payload.get("generation_depth", 0)),
            frontier_state=str(payload.get("frontier_state", "")),
            duplicate_of=(str(payload.get("duplicate_of")) if payload.get("duplicate_of") else None),
            surrogate=SurrogateDecision.from_record(payload.get("surrogate") if isinstance(payload.get("surrogate"), Mapping) else None),
            operator_family=str(payload.get("operator_family", "")),
            operator_tier=str(payload.get("operator_tier", "")),
            operator_tier_descriptor=str(payload.get("operator_tier_descriptor", "")),
            proposal_rank=int(payload.get("proposal_rank", 0)),
            generation_delta=max(1, int(payload.get("generation_delta", 1))),
            composed_operator_chain=[str(item) for item in chain] if isinstance(chain, list) else [],
            composition_hops=max(0, int(payload.get("composition_hops", 0))),
            dependency_policy_state=str(payload.get("dependency_policy_state", "unknown")),
            dependency_policy_reason=str(payload.get("dependency_policy_reason", "")),
            improvement=improvement,
            improvement_summary=ImprovementSummary.from_record(
                payload.get("improvement_summary") if isinstance(payload.get("improvement_summary"), Mapping) else None
            ),
            explanation_summary=str(payload.get("explanation_summary", "")),
            extra=extra,
        )


def parse_candidate_metadata(payload: Mapping[str, Any] | None) -> CandidateMetadata:
    return CandidateMetadata.from_record(payload)


def versioned_event_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(detail)
    payload.setdefault("schema_version", SEARCH_EVENT_DETAIL_SCHEMA_VERSION)
    return payload
