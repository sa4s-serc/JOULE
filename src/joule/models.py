from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunType(str, Enum):
    BASELINE = "baseline"
    OPTIMIZE = "optimize"
    APPLY = "apply"


class WorkloadKind(str, Enum):
    PYTEST = "pytest"
    PROPERTY = "property"
    HARNESS = "harness"
    GOLDEN_TRACE = "golden_trace"


class Fidelity(str, Enum):
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"


@dataclass(slots=True)
class TargetSpec:
    project_root: Path
    module: str
    file_path: Path
    function_name: str
    qualname: str
    owner_path: list[str]
    line_start: int
    line_end: int
    source: str
    is_async: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["project_root"] = str(self.project_root)
        record["file_path"] = str(self.file_path)
        return record

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> "TargetSpec":
        return cls(
            project_root=Path(payload["project_root"]),
            module=payload["module"],
            file_path=Path(payload["file_path"]),
            function_name=payload["function_name"],
            qualname=payload["qualname"],
            owner_path=list(payload.get("owner_path", [])),
            line_start=payload["line_start"],
            line_end=payload["line_end"],
            source=payload["source"],
            is_async=bool(payload.get("is_async", False)),
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class WorkloadSpec:
    kind: WorkloadKind
    identifier: str
    label: str
    selector: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> "WorkloadSpec":
        return cls(
            kind=WorkloadKind(payload["kind"]),
            identifier=payload["identifier"],
            label=payload["label"],
            selector=payload["selector"],
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class WorkloadBundle:
    target: TargetSpec
    workloads: list[WorkloadSpec]
    notes: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {
            "target": self.target.to_record(),
            "workloads": [item.to_record() for item in self.workloads],
            "notes": list(self.notes),
        }

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> "WorkloadBundle":
        return cls(
            target=TargetSpec.from_record(payload["target"]),
            workloads=[WorkloadSpec.from_record(item) for item in payload["workloads"]],
            notes=payload.get("notes", []),
        )


@dataclass(slots=True)
class MetricSample:
    workload_id: str
    fidelity: Fidelity
    repetition: int
    success: bool
    wall_time_s: float
    cpu_time_s: float
    peak_memory_bytes: int
    energy_j: float
    return_code: int
    stdout: str = ""
    stderr: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fidelity"] = self.fidelity.value
        return payload


@dataclass(slots=True)
class AggregateMetrics:
    workload_id: str
    repetitions: int
    success_rate: float
    mean_wall_time_s: float
    mean_cpu_time_s: float
    mean_peak_memory_bytes: float
    mean_energy_j: float
    wall_time_ci95: float
    cpu_time_ci95: float
    peak_memory_ci95: float
    energy_ci95: float

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MeasurementReport:
    run_id: str
    candidate_id: str | None
    fidelity: Fidelity
    aggregate: AggregateMetrics
    per_workload: list[AggregateMetrics]
    samples: list[MetricSample]
    environment: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "fidelity": self.fidelity.value,
            "aggregate": self.aggregate.to_record(),
            "per_workload": [item.to_record() for item in self.per_workload],
            "samples": [item.to_record() for item in self.samples],
            "environment": self.environment,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class CalibrationResult:
    workload_id: str
    inner_repetitions: int
    adaptive_applied: bool
    adaptive_estimated_wall_time_s: float
    adaptive_target_window_s: float
    adaptive_mode: str
    capped: bool = False

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TransformationResult:
    operator_name: str
    candidate_source: str
    reasoning: str
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateEvaluation:
    candidate_id: str
    operator_name: str
    reasoning: str
    source: str
    dependencies: list[str]
    accepted: bool
    score: float
    report: MeasurementReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryResult:
    target: TargetSpec
    score: float
    reasons: list[str]
    workloads: list[WorkloadSpec]


@dataclass(slots=True)
class RunRecord:
    run_id: str
    run_type: RunType
    target: TargetSpec
    bundle: WorkloadBundle
    status: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)
