from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import dataclasses
import os
import tomllib
import uuid
from typing import Any


@dataclass(slots=True)
class FidelitySettings:
    f1_repetitions: int = 3
    f2_repetitions: int = 7
    f3_repetitions: int = 12


@dataclass(slots=True)
class BackendSettings:
    options: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class ParetoWeights:
    energy: float = 0.5
    latency: float = 0.3
    memory: float = 0.2


@dataclass(slots=True)
class JouleSettings:
    project_root: Path
    seed: int = 1337
    artifact_dir: Path = field(default_factory=lambda: Path(".joule"))
    db_name: str = "joule.db"
    default_backend: str = "mock"
    llm_model: str = ""
    baseline_repetitions: int = 5
    optimization_budget: int = 6
    workload_discovery_limit: int = 8
    dashboard_port: int = 8501
    dependency_energy_threshold: float = 0.15
    dependency_latency_threshold: float = 0.20
    memory_regression_limit: float = 0.10
    terminal_verbosity: str = "normal"
    promotion_scalar_min: float = 0.03
    final_improvement_min: float = 0.05
    candidate_memory_regression_limit: float = 0.10
    workload_timeout_s: float = 30.0
    inner_repetitions_mode: str = "adaptive"
    inner_repetitions_fixed: int = 1
    inner_repetitions_min: int = 1
    inner_repetitions_max: int = 10_000
    adaptive_min_window_s: float = 0.05
    adaptive_probe_samples: int = 1
    search_max_generations: int = 3
    search_branching_factor: int = 2
    search_exploration_fraction: float = 0.45
    search_exploitation_fraction: float = 0.35
    search_confirmation_fraction: float = 0.20
    search_convergence_patience: int = 4
    search_min_novelty: float = 0.12
    surrogate_warm_start_limit: int = 50
    surrogate_min_training_points: int = 3
    backends: BackendSettings = field(default_factory=BackendSettings)
    pareto_weights: ParetoWeights = field(default_factory=ParetoWeights)
    fidelity: FidelitySettings = field(default_factory=FidelitySettings)

    @property
    def artifact_path(self) -> Path:
        return (self.project_root / self.artifact_dir).resolve()

    @property
    def db_path(self) -> Path:
        return self.artifact_path / self.db_name

    @property
    def lock_path(self) -> Path:
        return (self.project_root / ".joule.lock").resolve()

    def new_run_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def to_record(self) -> dict[str, Any]:
        payload = dataclasses.asdict(self)
        payload["project_root"] = str(self.project_root)
        payload["artifact_dir"] = str(self.artifact_dir)
        return payload


def _merge_dict(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _merge_dict(base[key], value)
        else:
            merged[key] = value
    return merged


def find_project_root(path: Path) -> Path:
    candidate = path.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for current in [candidate, *candidate.parents]:
        if (current / "pyproject.toml").exists():
            return current
    return candidate


def load_settings(path: str | Path) -> JouleSettings:
    project_root = find_project_root(Path(path))
    payload: dict[str, Any] = {}
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            raw = tomllib.load(handle)
        payload = raw.get("tool", {}).get("joule", {})

    fidelity_payload = payload.get("fidelity", {}) if isinstance(payload, dict) else {}
    backend_payload = payload.get("backends", {}) if isinstance(payload, dict) else {}
    settings = JouleSettings(
        project_root=project_root,
        seed=int(payload.get("seed", 1337)),
        artifact_dir=Path(payload.get("artifact_dir", ".joule")),
        db_name=str(payload.get("db_name", "joule.db")),
        default_backend=str(payload.get("default_backend", os.getenv("JOULE_BACKEND", "mock"))),
        llm_model=str(payload.get("llm_model", os.getenv("JOULE_LLM_MODEL", ""))),
        baseline_repetitions=int(payload.get("baseline_repetitions", 5)),
        optimization_budget=int(payload.get("optimization_budget", 6)),
        workload_discovery_limit=int(payload.get("workload_discovery_limit", 8)),
        dashboard_port=int(payload.get("dashboard_port", 8501)),
        dependency_energy_threshold=float(payload.get("dependency_energy_threshold", 0.15)),
        dependency_latency_threshold=float(payload.get("dependency_latency_threshold", 0.20)),
        memory_regression_limit=float(payload.get("memory_regression_limit", 0.10)),
        terminal_verbosity=str(payload.get("terminal_verbosity", "normal")),
        promotion_scalar_min=float(payload.get("promotion_scalar_min", 0.03)),
        final_improvement_min=float(payload.get("final_improvement_min", 0.05)),
        candidate_memory_regression_limit=float(payload.get("candidate_memory_regression_limit", 0.10)),
        workload_timeout_s=float(payload.get("workload_timeout_s", 30.0)),
        inner_repetitions_mode=str(payload.get("inner_repetitions_mode", "adaptive")),
        inner_repetitions_fixed=int(payload.get("inner_repetitions_fixed", 1)),
        inner_repetitions_min=int(payload.get("inner_repetitions_min", 1)),
        inner_repetitions_max=int(payload.get("inner_repetitions_max", 10_000)),
        adaptive_min_window_s=float(payload.get("adaptive_min_window_s", 0.05)),
        adaptive_probe_samples=int(payload.get("adaptive_probe_samples", 1)),
        search_max_generations=int(payload.get("search_max_generations", 3)),
        search_branching_factor=int(payload.get("search_branching_factor", 2)),
        search_exploration_fraction=float(payload.get("search_exploration_fraction", 0.45)),
        search_exploitation_fraction=float(payload.get("search_exploitation_fraction", 0.35)),
        search_confirmation_fraction=float(payload.get("search_confirmation_fraction", 0.20)),
        search_convergence_patience=int(payload.get("search_convergence_patience", 4)),
        search_min_novelty=float(payload.get("search_min_novelty", 0.12)),
        surrogate_warm_start_limit=int(payload.get("surrogate_warm_start_limit", 50)),
        surrogate_min_training_points=int(payload.get("surrogate_min_training_points", 3)),
        backends=BackendSettings(options=backend_payload if isinstance(backend_payload, dict) else {}),
        pareto_weights=ParetoWeights(
            energy=float(payload.get("pareto_weight_energy", 0.5)),
            latency=float(payload.get("pareto_weight_latency", 0.3)),
            memory=float(payload.get("pareto_weight_memory", 0.2)),
        ),
        fidelity=FidelitySettings(
            f1_repetitions=int(fidelity_payload.get("f1_repetitions", 3)),
            f2_repetitions=int(fidelity_payload.get("f2_repetitions", 7)),
            f3_repetitions=int(fidelity_payload.get("f3_repetitions", 12)),
        ),
    )
    return settings
