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
        "search_operator_beam_width": 1,
        "search_convergence_patience": 2,
    },
    "standard": {
        "search_operator_beam_width": 2,
    },
    "thorough": {
        "baseline_repetitions": 8,
        "optimization_budget": 10,
        "workload_discovery_limit": 12,
        "hotspot_limit": 20,
        "search_branching_factor": 3,
        "search_operator_beam_width": 3,
        "search_convergence_patience": 6,
        "search_composition_enabled": True,
        "search_composition_width": 2,
        "search_composition_max_hops": 2,
    },
    "ci": {
        "baseline_repetitions": 4,
        "optimization_budget": 4,
        "workload_discovery_limit": 6,
        "hotspot_limit": 6,
        "terminal_verbosity": "quiet",
        "search_branching_factor": 1,
        "search_operator_beam_width": 1,
        "search_convergence_patience": 2,
    },
}

PROFILE_FIDELITY_DEFAULTS: dict[str, dict[str, Any]] = {
    "quick": {"f1_repetitions": 1, "f2_repetitions": 3, "f3_repetitions": 5},
    "standard": {"f1_repetitions": 3, "f2_repetitions": 7, "f3_repetitions": 12},
    "thorough": {"f1_repetitions": 5, "f2_repetitions": 10, "f3_repetitions": 16},
    "ci": {"f1_repetitions": 2, "f2_repetitions": 4, "f3_repetitions": 6},
}

_LEGACY_SURROGATE_KEYS = {
    "surrogate_warm_start_limit",
    "surrogate_reuse_observations",
    "surrogate_min_training_points",
    "surrogate_acquisition",
    "surrogate_gp_noise",
    "surrogate_gp_length_scale",
    "surrogate_gp_nu",
    "surrogate_gp_ucb_beta",
    "surrogate_max_observations",
}
_SURROGATE_SHARED_KEYS = {
    "model",
    "fallback_model",
    "objective",
    "screening",
    "acquisition",
    "ucb_beta",
    "warm_start_limit",
    "reuse_observations",
    "min_training_points",
    "max_observations",
    "feature_cache_size",
}
_SURROGATE_MODEL_KEYS = {
    "gp": {"noise", "length_scale", "nu", "max_exact_points"},
    "local_kernel": {"bandwidth_floor", "min_neighbors"},
    "hist_gbdt": {
        "learning_rate",
        "max_iter",
        "max_leaf_nodes",
        "max_depth",
        "min_samples_leaf",
        "l2_regularization",
        "lower_quantile",
        "upper_quantile",
    },
}


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Cannot coerce string {value!r} to bool; expected true/false/yes/no/on/off/1/0")
    raise ValueError(f"Cannot coerce {type(value).__name__} value {value!r} to bool; expected a boolean")


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _coerce_bool_map(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): _coerce_bool(raw, default=True) for key, raw in value.items() if str(key).strip()}


def _require_mapping(value: Any, *, table_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"[tool.joule.{table_name}] must be a table")
    return value


def _reject_legacy_surrogate_keys(payload: dict[str, Any]) -> None:
    for key in sorted(_LEGACY_SURROGATE_KEYS & set(payload)):
        raise ValueError(
            f"Unsupported legacy surrogate key [tool.joule].{key}. "
            "Use [tool.joule.surrogate] and [tool.joule.surrogates.<model>] tables instead."
        )


def _validate_allowed_keys(payload: dict[str, Any], *, allowed: set[str], table_name: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if not unknown:
        return
    joined = ", ".join(unknown)
    raise ValueError(f"Unknown key(s) in [tool.joule.{table_name}]: {joined}")


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

    def as_tuple(self) -> tuple[float, float, float]:
        return (float(self.energy), float(self.latency), float(self.memory))


@dataclass(slots=True)
class GPSurrogateSettings:
    noise: float = 1e-6
    length_scale: float = 1.0
    nu: float = 1.5
    max_exact_points: int = 120


@dataclass(slots=True)
class LocalKernelSurrogateSettings:
    bandwidth_floor: float = 1e-6
    min_neighbors: int = 1


@dataclass(slots=True)
class HistGBDTSurrogateSettings:
    """Settings for Histogram-based Gradient Boosting Decision Tree surrogate model."""

    learning_rate: float = 0.1
    max_iter: int = 100
    max_leaf_nodes: int = 31
    max_depth: int | None = None
    min_samples_leaf: int = 2
    l2_regularization: float = 0.0
    lower_quantile: float = 0.16
    upper_quantile: float = 0.84


@dataclass(slots=True)
class SurrogateSettings:
    model: str = "hist_gbdt"
    fallback_model: str = "local_kernel"
    objective: str = "multi_metric"
    screening: str = "scalarized"
    acquisition: str = "ei"
    ucb_beta: float = 1.0
    warm_start_limit: int = 50
    reuse_observations: bool = True
    min_training_points: int = 3
    max_observations: int = 100
    feature_cache_size: int = 2048
    gp: GPSurrogateSettings = field(default_factory=GPSurrogateSettings)
    local_kernel: LocalKernelSurrogateSettings = field(default_factory=LocalKernelSurrogateSettings)
    hist_gbdt: HistGBDTSurrogateSettings = field(default_factory=HistGBDTSurrogateSettings)


@dataclass(slots=True)
class JouleSettings:
    project_root: Path
    profile: str = "standard"
    seed: int = 1337
    artifact_dir: Path = field(default_factory=lambda: Path(".joule"))
    db_name: str = "joule.db"
    default_backend: str = "mock"
    llm_model: str = ""
    enable_llm_operators: bool = True
    baseline_repetitions: int = 5
    optimization_budget: int = 6
    workload_discovery_limit: int = 8
    hotspot_limit: int = 12
    granular_hotspot_analysis: bool = False
    dashboard_port: int = 8501
    # Minimum improvement ratio required for a candidate to be accepted into the frontier.
    # Also used as the default CI threshold when --improvement-threshold is not specified.
    final_improvement_min: float = 0.05
    # Maximum allowed memory regression ratio before a candidate is rejected.
    memory_regression_limit: float = 0.10
    terminal_verbosity: str = "normal"
    promotion_scalar_min: float = 0.03
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
    search_operator_beam_width: int = 1
    search_exploration_fraction: float = 0.45
    search_exploitation_fraction: float = 0.35
    search_confirmation_fraction: float = 0.20
    search_convergence_patience: int = 4
    search_min_novelty: float = 0.12
    search_composition_enabled: bool = False
    search_composition_width: int = 1
    search_composition_max_hops: int = 1
    operator_allowlist: list[str] = field(default_factory=list)
    operator_denylist: list[str] = field(default_factory=list)
    operator_kill_switches: dict[str, bool] = field(default_factory=dict)
    backends: BackendSettings = field(default_factory=BackendSettings)
    pareto_weights: ParetoWeights = field(default_factory=ParetoWeights)
    fidelity: FidelitySettings = field(default_factory=FidelitySettings)
    surrogate: SurrogateSettings = field(default_factory=SurrogateSettings)

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


def _load_raw_payload(project_root: Path) -> dict[str, Any]:
    """Load raw configuration payload from pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as handle:
            raw = tomllib.load(handle)
        payload = raw.get("tool", {}).get("joule", {})
        if isinstance(payload, dict):
            return payload
    return {}


def _resolve_profile(payload: dict[str, Any]) -> str:
    """Resolve and validate the JOULE profile from payload or environment."""
    profile = str(payload.get("profile", os.getenv("JOULE_PROFILE", "standard"))).strip().lower()
    if profile not in SUPPORTED_PROFILES:
        supported = ", ".join(sorted(SUPPORTED_PROFILES))
        raise ValueError(f"Unknown JOULE profile {profile!r}. Supported profiles: {supported}")
    return profile


def _build_fidelity_settings(profile: str, resolved_payload: dict[str, Any]) -> FidelitySettings:
    """Build FidelitySettings from profile defaults and user configuration."""
    fidelity_payload = {
        **PROFILE_FIDELITY_DEFAULTS.get(profile, {}),
        **(
            resolved_payload.get("fidelity", {})
            if isinstance(resolved_payload.get("fidelity", {}), dict)
            else {}
        ),
    }
    return FidelitySettings(
        f1_repetitions=int(fidelity_payload.get("f1_repetitions", 3)),
        f2_repetitions=int(fidelity_payload.get("f2_repetitions", 7)),
        f3_repetitions=int(fidelity_payload.get("f3_repetitions", 12)),
    )


def _build_surrogate_model_payloads(resolved_payload: dict[str, Any]) -> tuple[dict, dict, dict, dict]:
    """Extract and validate surrogate and model-specific payloads."""
    surrogate_payload = _require_mapping(resolved_payload.get("surrogate", {}), table_name="surrogate")
    model_payload = _require_mapping(resolved_payload.get("surrogates", {}), table_name="surrogates")

    _validate_allowed_keys(surrogate_payload, allowed=_SURROGATE_SHARED_KEYS, table_name="surrogate")
    _validate_allowed_keys(model_payload, allowed=set(_SURROGATE_MODEL_KEYS), table_name="surrogates")

    gp_payload = _require_mapping(model_payload.get("gp", {}), table_name="surrogates.gp")
    local_kernel_payload = _require_mapping(model_payload.get("local_kernel", {}), table_name="surrogates.local_kernel")
    hist_gbdt_payload = _require_mapping(model_payload.get("hist_gbdt", {}), table_name="surrogates.hist_gbdt")

    _validate_allowed_keys(gp_payload, allowed=_SURROGATE_MODEL_KEYS["gp"], table_name="surrogates.gp")
    _validate_allowed_keys(
        local_kernel_payload,
        allowed=_SURROGATE_MODEL_KEYS["local_kernel"],
        table_name="surrogates.local_kernel",
    )
    _validate_allowed_keys(
        hist_gbdt_payload,
        allowed=_SURROGATE_MODEL_KEYS["hist_gbdt"],
        table_name="surrogates.hist_gbdt",
    )

    return surrogate_payload, gp_payload, local_kernel_payload, hist_gbdt_payload


def _build_surrogate_settings(
    surrogate_payload: dict,
    gp_payload: dict,
    local_kernel_payload: dict,
    hist_gbdt_payload: dict,
) -> SurrogateSettings:
    """Build SurrogateSettings from validated payloads."""
    return SurrogateSettings(
        model=str(surrogate_payload.get("model", "hist_gbdt")).strip().lower(),
        fallback_model=str(surrogate_payload.get("fallback_model", "local_kernel")).strip().lower(),
        objective=str(surrogate_payload.get("objective", "multi_metric")).strip().lower(),
        screening=str(surrogate_payload.get("screening", "scalarized")).strip().lower(),
        acquisition=str(surrogate_payload.get("acquisition", "ei")).strip().lower(),
        ucb_beta=float(surrogate_payload.get("ucb_beta", 1.0)),
        warm_start_limit=int(surrogate_payload.get("warm_start_limit", 50)),
        reuse_observations=_coerce_bool(surrogate_payload.get("reuse_observations", True), default=True),
        min_training_points=int(surrogate_payload.get("min_training_points", 3)),
        max_observations=max(3, int(surrogate_payload.get("max_observations", 100))),
        feature_cache_size=max(64, int(surrogate_payload.get("feature_cache_size", 2048))),
        gp=GPSurrogateSettings(
            noise=float(gp_payload.get("noise", 1e-6)),
            length_scale=float(gp_payload.get("length_scale", 1.0)),
            nu=float(gp_payload.get("nu", 1.5)),
            max_exact_points=max(3, int(gp_payload.get("max_exact_points", 120))),
        ),
        local_kernel=LocalKernelSurrogateSettings(
            bandwidth_floor=float(local_kernel_payload.get("bandwidth_floor", 1e-6)),
            min_neighbors=max(1, int(local_kernel_payload.get("min_neighbors", 1))),
        ),
        hist_gbdt=HistGBDTSurrogateSettings(
            learning_rate=float(hist_gbdt_payload.get("learning_rate", 0.1)),
            max_iter=max(1, int(hist_gbdt_payload.get("max_iter", 100))),
            max_leaf_nodes=max(2, int(hist_gbdt_payload.get("max_leaf_nodes", 31))),
            max_depth=int(hist_gbdt_payload["max_depth"]) if hist_gbdt_payload.get("max_depth") is not None else None,
            min_samples_leaf=max(1, int(hist_gbdt_payload.get("min_samples_leaf", 2))),
            l2_regularization=float(hist_gbdt_payload.get("l2_regularization", 0.0)),
            lower_quantile=float(hist_gbdt_payload.get("lower_quantile", 0.16)),
            upper_quantile=float(hist_gbdt_payload.get("upper_quantile", 0.84)),
        ),
    )


def load_settings(path: str | Path) -> JouleSettings:
    """Load and validate JouleSettings from pyproject.toml configuration."""
    project_root = find_project_root(Path(path))
    payload = _load_raw_payload(project_root)
    _reject_legacy_surrogate_keys(payload)

    profile = _resolve_profile(payload)
    resolved_payload = {**PROFILE_DEFAULTS.get(profile, {}), **payload}
    backend_payload = resolved_payload.get("backends", {}) if isinstance(resolved_payload, dict) else {}

    fidelity = _build_fidelity_settings(profile, resolved_payload)
    surrogate_payload, gp_payload, local_kernel_payload, hist_gbdt_payload = _build_surrogate_model_payloads(resolved_payload)
    surrogate = _build_surrogate_settings(surrogate_payload, gp_payload, local_kernel_payload, hist_gbdt_payload)

    settings = JouleSettings(
        project_root=project_root,
        profile=profile,
        seed=int(resolved_payload.get("seed", 1337)),
        artifact_dir=Path(resolved_payload.get("artifact_dir", ".joule")),
        db_name=str(resolved_payload.get("db_name", "joule.db")),
        default_backend=str(resolved_payload.get("default_backend", os.getenv("JOULE_BACKEND", "mock"))),
        llm_model=str(resolved_payload.get("llm_model", os.getenv("JOULE_LLM_MODEL", ""))),
        enable_llm_operators=_coerce_bool(resolved_payload.get("enable_llm_operators", True), default=True),
        baseline_repetitions=int(resolved_payload.get("baseline_repetitions", 5)),
        optimization_budget=int(resolved_payload.get("optimization_budget", 6)),
        workload_discovery_limit=int(resolved_payload.get("workload_discovery_limit", 8)),
        hotspot_limit=int(resolved_payload.get("hotspot_limit", 12)),
        granular_hotspot_analysis=_coerce_bool(resolved_payload.get("granular_hotspot_analysis", False), default=False),
        dashboard_port=int(resolved_payload.get("dashboard_port", 8501)),
        final_improvement_min=float(resolved_payload.get("final_improvement_min", 0.05)),
        memory_regression_limit=float(resolved_payload.get("memory_regression_limit", 0.10)),
        terminal_verbosity=str(resolved_payload.get("terminal_verbosity", "normal")),
        promotion_scalar_min=float(resolved_payload.get("promotion_scalar_min", 0.03)),
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
        search_operator_beam_width=max(1, int(resolved_payload.get("search_operator_beam_width", 1))),
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
        search_composition_max_hops=max(1, int(resolved_payload.get("search_composition_max_hops", 1))),
        operator_allowlist=_coerce_str_list(resolved_payload.get("operator_allowlist", [])),
        operator_denylist=_coerce_str_list(resolved_payload.get("operator_denylist", [])),
        operator_kill_switches=_coerce_bool_map(resolved_payload.get("operator_kill_switches", {})),
        backends=BackendSettings(options=backend_payload if isinstance(backend_payload, dict) else {}),
        pareto_weights=ParetoWeights(
            energy=float(resolved_payload.get("pareto_weight_energy", 0.5)),
            latency=float(resolved_payload.get("pareto_weight_latency", 0.3)),
            memory=float(resolved_payload.get("pareto_weight_memory", 0.2)),
        ),
        fidelity=fidelity,
        surrogate=surrogate,
    )
    return settings
