from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import dataclasses
import os
import tomllib
import uuid
from typing import Any


SUPPORTED_PROFILES = {"quick", "standard", "thorough", "ci"}

PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "quick": {
        "baseline_repetitions": 3,
        "optimization_budget": 3,
        "workload_discovery_limit": 5,
        "hotspot_limit": 8,
        "search_branching_factor": 1,
        "search_convergence_patience": 2,
    },
    "standard": {},
    "thorough": {
        "baseline_repetitions": 8,
        "optimization_budget": 10,
        "workload_discovery_limit": 12,
        "hotspot_limit": 20,
        "search_branching_factor": 3,
        "search_convergence_patience": 6,
    },
    "ci": {
        "baseline_repetitions": 4,
        "optimization_budget": 4,
        "workload_discovery_limit": 6,
        "hotspot_limit": 6,
        "terminal_verbosity": "quiet",
        "search_branching_factor": 1,
        "search_convergence_patience": 2,
    },
}

PROFILE_FIDELITY_DEFAULTS: dict[str, dict[str, Any]] = {
    "quick": {"f1_repetitions": 1, "f2_repetitions": 3, "f3_repetitions": 5},
    "standard": {"f1_repetitions": 3, "f2_repetitions": 7, "f3_repetitions": 12},
    "thorough": {"f1_repetitions": 5, "f2_repetitions": 10, "f3_repetitions": 16},
    "ci": {"f1_repetitions": 2, "f2_repetitions": 4, "f3_repetitions": 6},
}


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


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
    profile: str = "standard"
    seed: int = 1337
    artifact_dir: Path = field(default_factory=lambda: Path(".joule"))
    db_name: str = "joule.db"
    default_backend: str = "mock"
    llm_model: str = ""
    baseline_repetitions: int = 5
    optimization_budget: int = 6
    workload_discovery_limit: int = 8
    hotspot_limit: int = 12
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
    max_parallel_workers: int = 1
    search_max_generations: int = 3
    search_branching_factor: int = 2
    search_exploration_fraction: float = 0.45
    search_exploitation_fraction: float = 0.35
    search_confirmation_fraction: float = 0.20
    search_convergence_patience: int = 4
    search_min_novelty: float = 0.12
    search_composition_enabled: bool = False
    search_composition_width: int = 1
    surrogate_warm_start_limit: int = 50
    surrogate_reuse_observations: bool = True
    surrogate_min_training_points: int = 3
    surrogate_acquisition: str = "ei"
    surrogate_gp_noise: float = 1e-6
    surrogate_gp_length_scale: float = 1.0
    surrogate_gp_nu: float = 1.5
    surrogate_gp_ucb_beta: float = 1.0
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

    if not isinstance(payload, dict):
        payload = {}

    profile = str(payload.get("profile", os.getenv("JOULE_PROFILE", "standard"))).strip().lower()
    if profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise ValueError(f"Unknown JOULE profile {profile!r}. Supported profiles: {supported}")

    resolved_payload = {**PROFILE_DEFAULTS.get(profile, {}), **payload}
    fidelity_payload = {
        **PROFILE_FIDELITY_DEFAULTS.get(profile, {}),
        **(resolved_payload.get("fidelity", {}) if isinstance(resolved_payload.get("fidelity", {}), dict) else {}),
    }
    backend_payload = resolved_payload.get("backends", {}) if isinstance(resolved_payload, dict) else {}

    settings = JouleSettings(
        project_root=project_root,
        profile=profile,
        seed=int(resolved_payload.get("seed", 1337)),
        artifact_dir=Path(resolved_payload.get("artifact_dir", ".joule")),
        db_name=str(resolved_payload.get("db_name", "joule.db")),
        default_backend=str(resolved_payload.get("default_backend", os.getenv("JOULE_BACKEND", "mock"))),
        llm_model=str(resolved_payload.get("llm_model", os.getenv("JOULE_LLM_MODEL", ""))),
        baseline_repetitions=int(resolved_payload.get("baseline_repetitions", 5)),
        optimization_budget=int(resolved_payload.get("optimization_budget", 6)),
        workload_discovery_limit=int(resolved_payload.get("workload_discovery_limit", 8)),
        hotspot_limit=int(resolved_payload.get("hotspot_limit", 12)),
        dashboard_port=int(resolved_payload.get("dashboard_port", 8501)),
        dependency_energy_threshold=float(resolved_payload.get("dependency_energy_threshold", 0.15)),
        dependency_latency_threshold=float(resolved_payload.get("dependency_latency_threshold", 0.20)),
        memory_regression_limit=float(resolved_payload.get("memory_regression_limit", 0.10)),
        terminal_verbosity=str(resolved_payload.get("terminal_verbosity", "normal")),
        promotion_scalar_min=float(resolved_payload.get("promotion_scalar_min", 0.03)),
        final_improvement_min=float(resolved_payload.get("final_improvement_min", 0.05)),
        candidate_memory_regression_limit=float(resolved_payload.get("candidate_memory_regression_limit", 0.10)),
        workload_timeout_s=float(resolved_payload.get("workload_timeout_s", 30.0)),
        inner_repetitions_mode=str(resolved_payload.get("inner_repetitions_mode", "adaptive")),
        inner_repetitions_fixed=int(resolved_payload.get("inner_repetitions_fixed", 1)),
        inner_repetitions_min=int(resolved_payload.get("inner_repetitions_min", 1)),
        inner_repetitions_max=int(resolved_payload.get("inner_repetitions_max", 10_000)),
        adaptive_min_window_s=float(resolved_payload.get("adaptive_min_window_s", 0.05)),
        adaptive_probe_samples=int(resolved_payload.get("adaptive_probe_samples", 1)),
        max_parallel_workers=int(resolved_payload.get("max_parallel_workers", 1)),
        search_max_generations=int(resolved_payload.get("search_max_generations", 3)),
        search_branching_factor=int(resolved_payload.get("search_branching_factor", 2)),
        search_exploration_fraction=float(resolved_payload.get("search_exploration_fraction", 0.45)),
        search_exploitation_fraction=float(resolved_payload.get("search_exploitation_fraction", 0.35)),
        search_confirmation_fraction=float(resolved_payload.get("search_confirmation_fraction", 0.20)),
        search_convergence_patience=int(resolved_payload.get("search_convergence_patience", 4)),
        search_min_novelty=float(resolved_payload.get("search_min_novelty", 0.12)),
        search_composition_enabled=_coerce_bool(
            resolved_payload.get("search_composition_enabled", False),
            default=False,
        ),
        search_composition_width=max(1, int(resolved_payload.get("search_composition_width", 1))),
        surrogate_warm_start_limit=int(resolved_payload.get("surrogate_warm_start_limit", 50)),
        surrogate_reuse_observations=_coerce_bool(
            resolved_payload.get("surrogate_reuse_observations", True),
            default=True,
        ),
        surrogate_min_training_points=int(resolved_payload.get("surrogate_min_training_points", 3)),
        surrogate_acquisition=str(resolved_payload.get("surrogate_acquisition", "ei")),
        surrogate_gp_noise=float(resolved_payload.get("surrogate_gp_noise", 1e-6)),
        surrogate_gp_length_scale=float(resolved_payload.get("surrogate_gp_length_scale", 1.0)),
        surrogate_gp_nu=float(resolved_payload.get("surrogate_gp_nu", 1.5)),
        surrogate_gp_ucb_beta=float(resolved_payload.get("surrogate_gp_ucb_beta", 1.0)),
        backends=BackendSettings(options=backend_payload if isinstance(backend_payload, dict) else {}),
        pareto_weights=ParetoWeights(
            energy=float(resolved_payload.get("pareto_weight_energy", 0.5)),
            latency=float(resolved_payload.get("pareto_weight_latency", 0.3)),
            memory=float(resolved_payload.get("pareto_weight_memory", 0.2)),
        ),
        fidelity=FidelitySettings(
            f1_repetitions=int(fidelity_payload.get("f1_repetitions", 3)),
            f2_repetitions=int(fidelity_payload.get("f2_repetitions", 7)),
            f3_repetitions=int(fidelity_payload.get("f3_repetitions", 12)),
        ),
    )
    return settings
