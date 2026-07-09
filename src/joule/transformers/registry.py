from __future__ import annotations

from importlib.metadata import entry_points
import inspect
import logging
import math
from typing import Any

from joule.models import SearchContext, SearchPhase, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator
from joule.transformers.deterministic import default_deterministic_operators
from joule.transformers.generative import default_llm_operators, escape_llm_operators
from joule.transformers import smell_tagger


LOGGER = logging.getLogger(__name__)

# Phase 2/3 scoring constants

# Contextual scoring weights for operator selection.
# These balance exploration (UCB) with operator-specific performance signals.
_SCORE_FRONTIER_BONUS = 0.60   # reward for operators that have contributed to the frontier
_SCORE_DEPTH_FIT = 0.25        # reward for operators that succeed at the current generation depth
_SCORE_PHASE_FIT = 0.20        # reward for operators that succeed in the current search phase
_SCORE_DUPLICATE_PENALTY = 0.35        # penalty for operators that produce duplicate sources
_SCORE_CORRECTNESS_PENALTY = 0.40      # penalty for operators that produce incorrect candidates
_SCORE_PRECHECK_PENALTY = 0.20         # penalty for operators that fail precheck

# Phase 2 — taxonomy-aware operator routing
# Bonus applied when operator's targets_smells overlaps with detected smells.
_SCORE_SMELL_OVERLAP_BONUS = 0.30

# Phase 3 — empirically-derived ROI weights per smell category.
# Normalised so median (C3/C10) = 1.0. Source: Energy-Smells taxonomy paper.
_SMELL_ROI_WEIGHT: dict[str, float] = {
    "C6":  1.40,   # Memory — highest energy savings per fix
    "C9":  1.30,   # I/O access
    "C11": 1.20,   # Concurrency
    "C8":  1.15,   # Missing reuse
    "C7":  1.10,   # Algorithmic
    "C12": 1.05,   # Hardware locality
    "C5":  1.00,   # Data structures (median baseline)
    "C3":  1.00,   # Iteration (median baseline)
    "C10": 0.95,   # Language primitives
    "C2":  0.85,   # Call overhead
    "C1":  0.80,   # Redundant computation (common, lower individual ROI)
    "C4":  0.75,   # Control flow (most common, lowest individual ROI)
}

# Phase 4 — tier-phase coupling bonus.
# Key: (tier_value, phase_value)  — applied on top of UCB score.
_TIER_PHASE_BONUS: dict[tuple[str, str], float] = {
    ("L", "exploration"):   0.40,  # prefer cheap syntactic rewrites first
    ("L", "exploitation"):  0.10,
    ("M", "exploitation"):  0.35,  # semantic rewrites shine in exploitation
    ("M", "exploration"):   0.05,
    ("H", "exploitation"):  0.20,
    ("H", "confirmation"):  0.30,  # algorithmic changes earn their place late
}


class OperatorRegistry:
    def __init__(
        self,
        *,
        llm_model: str,
        include_llm: bool = True,
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        kill_switches: dict[str, bool] | None = None,
    ) -> None:
        self.operators: list[BaseOperator] = default_deterministic_operators()
        self.escape_operators: list[BaseOperator] = []
        
        self.allowlist = set(allowlist) if allowlist else None
        self.denylist = set(denylist) if denylist else set()
        self.kill_switches = kill_switches or {}

        if include_llm and llm_model.strip():
            llm_ops = default_llm_operators(llm_model)
            self.operators.extend(llm_ops)
            self.escape_operators.extend(escape_llm_operators(llm_model))

        self.stats: dict[str, dict[str, Any]] = {}
        self._discover_entry_points(llm_model=llm_model)
        
        self.operators = [op for op in self.operators if self._is_allowed(op.name)]
        self.escape_operators = [op for op in self.escape_operators if self._is_allowed(op.name)]

        for operator in [*self.operators, *self.escape_operators]:
            self.stats.setdefault(operator.name, self._empty_stat())

        # Track last target key to reset precheck failure counts on target change.
        self._last_target_key: str | None = None

    def _is_allowed(self, name: str) -> bool:
        if self.kill_switches.get(name, False):
            return False
        if name in self.denylist:
            return False
        if self.allowlist is not None and name not in self.allowlist:
            return False
        return True

    def ranked(
        self,
        *,
        phase: SearchPhase | None = None,
        parent_generation: int = 0,
        smell_tags: frozenset[str] = frozenset(),
    ) -> list[BaseOperator]:
        total_attempts = sum(max(1.0, stat["attempts"]) for stat in self.stats.values())
        return sorted(
            self.operators,
            key=lambda operator: self._contextual_score(
                operator.name,
                total_attempts,
                phase=phase,
                parent_generation=parent_generation,
                smell_tags=smell_tags,
                operator_targets=operator.targets_smells,
                operator_tier=operator.tier.value,
            ),
            reverse=True,
        )

    def select_operator(self, *, phase: SearchPhase, parent_generation: int) -> BaseOperator:
        return self.ranked(phase=phase, parent_generation=parent_generation)[0]

    def select_operators(
        self,
        *,
        phase: SearchPhase,
        parent_generation: int,
        top_k: int = 1,
        smell_tags: frozenset[str] = frozenset(),
    ) -> list[BaseOperator]:
        return self.ranked(
            phase=phase,
            parent_generation=parent_generation,
            smell_tags=smell_tags,
        )[:top_k]

    def select_operator_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
    ) -> BaseOperator | None:
        valid = self.select_operators_for_candidate(
            target=target, context=context, phase=phase, parent_generation=parent_generation, top_k=1
        )
        return valid[0] if valid else None

    def select_operators_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
        top_k: int = 1,
    ) -> list[BaseOperator]:
        # Phase 2: compute smell tags from the target source once and pass down
        tags = smell_tagger.tag_source(target.source)
        # Reset precheck failure penalties when the target changes.
        target_key = f"{target.module}:{target.qualname}"
        if target_key != self._last_target_key:
            self._last_target_key = target_key
            for stat in self.stats.values():
                stat["precheck_failures"] = 0.0
        else:
            # Decay precheck failures so that old failures on this target don't permanently penalise
            for stat in self.stats.values():
                stat["precheck_failures"] = float(stat.get("precheck_failures", 0.0)) * 0.90
        ranked = self.ranked(
            phase=phase,
            parent_generation=parent_generation,
            smell_tags=tags,
        )
        valid = self._precheck_ranked(ranked, target=target, context=context)
        return valid[:top_k]

    def select_escape_operator(self, *, phase: SearchPhase, parent_generation: int) -> BaseOperator | None:
        if not self.escape_operators:
            return None
        total_attempts = sum(max(1.0, stat["attempts"]) for stat in self.stats.values())
        return sorted(
            self.escape_operators,
            key=lambda operator: self._contextual_score(
                operator.name,
                total_attempts,
                phase=phase,
                parent_generation=parent_generation,
                smell_tags=frozenset(),
                operator_targets=operator.targets_smells,
                operator_tier=operator.tier.value,
            ),
            reverse=True,
        )[0]

    def select_escape_operator_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
    ) -> BaseOperator | None:
        escape = self.select_escape_operator(phase=phase, parent_generation=parent_generation)
        if escape is None:
            return None
        if not self._safe_precheck(escape, target=target, context=context):
            return None
        return escape

    def update(
        self,
        result: TransformationResult,
        success: bool,
        reward: float,
        *,
        phase: SearchPhase,
        parent_generation: int,
        duplicate: bool = False,
        correctness_failure: bool = False,
        frontier_contribution: bool = False,
    ) -> None:
        stat = self.stats.setdefault(result.operator_name, self._empty_stat())
        safe_reward = reward if math.isfinite(reward) else 0.0
        stat["attempts"] += 1
        stat["successes"] += 1 if success else 0
        stat["reward"] += safe_reward
        stat["duplicates"] += 1 if duplicate else 0
        stat["correctness_failures"] += 1 if correctness_failure else 0
        stat["frontier_contributions"] += 1 if frontier_contribution else 0
        # EMA success rate: decays old history, upweights recent outcomes (alpha=0.1)
        _ema_alpha = 0.10
        stat["ema_success_rate"] = (
            (1.0 - _ema_alpha) * float(stat["ema_success_rate"])
            + _ema_alpha * (1.0 if success else 0.0)
        )
        depth_key = str(parent_generation)
        depth_attempts = stat.setdefault("depth_attempts", {})
        depth_successes = stat.setdefault("depth_successes", {})
        depth_attempts[depth_key] = float(depth_attempts.get(depth_key, 0.0)) + 1.0
        depth_successes[depth_key] = float(depth_successes.get(depth_key, 0.0)) + (1.0 if success else 0.0)
        phase_attempts = stat.setdefault("phase_attempts", {})
        phase_successes = stat.setdefault("phase_successes", {})
        phase_attempts[phase.value] = float(phase_attempts.get(phase.value, 0.0)) + 1.0
        phase_successes[phase.value] = float(phase_successes.get(phase.value, 0.0)) + (1.0 if success else 0.0)

    def record_empty_attempt(self, operator_name: str, *, phase: SearchPhase, parent_generation: int) -> None:
        stat = self.stats.setdefault(operator_name, self._empty_stat())
        stat["attempts"] += 1.0
        depth_key = str(parent_generation)
        depth_attempts = stat.setdefault("depth_attempts", {})
        depth_attempts[depth_key] = float(depth_attempts.get(depth_key, 0.0)) + 1.0
        phase_attempts = stat.setdefault("phase_attempts", {})
        phase_attempts[phase.value] = float(phase_attempts.get(phase.value, 0.0)) + 1.0

    def load_stats(self, persisted: dict[str, dict[str, float]]) -> None:
        for name, values in persisted.items():
            if name not in self.stats:
                continue
            stat = self.stats[name]
            stat["attempts"] = float(values.get("attempts", 0.0))
            stat["successes"] = float(values.get("successes", 0.0))
            stat["reward"] = float(values.get("reward", 0.0))
            stat["duplicates"] = float(values.get("duplicates", 0.0))
            stat["correctness_failures"] = float(values.get("correctness_failures", 0.0))
            stat["frontier_contributions"] = float(values.get("frontier_contributions", 0.0))
            stat["precheck_failures"] = float(values.get("precheck_failures", 0.0))

    def _ucb(self, name: str, total_attempts: float) -> float:
        stat = self.stats[name]
        raw_attempts = float(stat["attempts"])
        attempts = max(1.0, raw_attempts)
        mean_reward = stat["reward"] / attempts
        if not math.isfinite(mean_reward):
            mean_reward = 0.0
        exploration = math.sqrt((2.0 * math.log(total_attempts + 1.0)) / attempts)
        
        # Add a minimum exploration floor for operators that haven't had a fair chance.
        # This prevents early failures (e.g. transient LLM errors) from permanently suppressing an operator.
        MIN_EXPLORATION_ATTEMPTS = 2.0
        if raw_attempts < MIN_EXPLORATION_ATTEMPTS:
            exploration += 2.0  # Strong bonus to guarantee initial trials

        success_bonus = stat["successes"] / attempts
        return mean_reward + success_bonus + exploration

    def _contextual_score(
        self,
        name: str,
        total_attempts: float,
        *,
        phase: SearchPhase | None,
        parent_generation: int,
        smell_tags: frozenset[str] = frozenset(),
        operator_targets: frozenset[str] = frozenset(),
        operator_tier: str = "L",
    ) -> float:
        stat = self.stats[name]
        attempts = max(1.0, float(stat["attempts"]))
        duplicate_rate = float(stat["duplicates"]) / attempts
        correctness_failure_rate = float(stat["correctness_failures"]) / attempts
        frontier_rate = float(stat["frontier_contributions"]) / attempts
        precheck_failure_rate = float(stat["precheck_failures"]) / attempts
        depth_key = str(parent_generation)
        depth_attempts = float(stat.get("depth_attempts", {}).get(depth_key, 0.0))
        depth_successes = float(stat.get("depth_successes", {}).get(depth_key, 0.0))
        depth_fit = depth_successes / depth_attempts if depth_attempts > 0 else 0.0
        phase_fit = 0.0
        if phase is not None:
            phase_attempts = float(stat.get("phase_attempts", {}).get(phase.value, 0.0))
            phase_successes = float(stat.get("phase_successes", {}).get(phase.value, 0.0))
            phase_fit = phase_successes / phase_attempts if phase_attempts > 0 else 0.0

        base_ucb = self._ucb(name, total_attempts)

        # Exploitation terms (these are scaled by ROI)
        exploitation = (
            (_SCORE_FRONTIER_BONUS * frontier_rate)
            + (_SCORE_DEPTH_FIT * depth_fit)
            + (_SCORE_PHASE_FIT * phase_fit)
        )

        penalties = (
            (_SCORE_DUPLICATE_PENALTY * duplicate_rate)
            + (_SCORE_CORRECTNESS_PENALTY * correctness_failure_rate)
            + (_SCORE_PRECHECK_PENALTY * precheck_failure_rate)
        )

        # Phase 3 — ROI multiplier applies ONLY to exploitation terms, not UCB.
        # This prevents suppressing new operators whose UCB exploration term is unscaled.
        roi = 1.0
        if operator_targets:
            roi = sum(_SMELL_ROI_WEIGHT.get(s, 1.0) for s in operator_targets) / len(operator_targets)

        base_score = base_ucb + (exploitation * roi) - penalties

        # Phase 2 — smell-overlap bonus
        if smell_tags and operator_targets:
            overlap = len(operator_targets & smell_tags) / max(1, len(smell_tags))
            base_score += _SCORE_SMELL_OVERLAP_BONUS * overlap

        # EMA success-rate boost: give slight preference to operators with recent success.
        ema_success = float(stat.get("ema_success_rate", 0.0))
        base_score += 0.10 * ema_success

        # Phase 4 — tier-phase coupling bonus
        if phase is not None:
            tier_phase_key = (operator_tier, phase.value)
            base_score += _TIER_PHASE_BONUS.get(tier_phase_key, 0.0)

        return base_score

    def _empty_stat(self) -> dict[str, Any]:
        return {
            "attempts": 0.0,
            "successes": 0.0,
            "reward": 0.0,
            "duplicates": 0.0,
            "correctness_failures": 0.0,
            "frontier_contributions": 0.0,
            "precheck_failures": 0.0,
            "ema_success_rate": 0.0,
            "depth_attempts": {},
            "depth_successes": {},
            "phase_attempts": {},
            "phase_successes": {},
        }

    def _precheck_ranked(
        self,
        operators: list[BaseOperator],
        *,
        target: TargetSpec,
        context: SearchContext | None,
    ) -> list[BaseOperator]:
        return [operator for operator in operators if self._safe_precheck(operator, target=target, context=context)]

    def _safe_precheck(self, operator: BaseOperator, *, target: TargetSpec, context: SearchContext | None) -> bool:
        try:
            return bool(operator.precheck(target, context))
        except Exception:
            stat = self.stats.setdefault(operator.name, self._empty_stat())
            stat["precheck_failures"] += 1.0
            return False

    def _discover_entry_points(self, *, llm_model: str) -> None:
        discovered = entry_points()
        operator_points = list(discovered.select(group="joule.operators"))
        known_names = {operator.name for operator in [*self.operators, *self.escape_operators]}
        for point in operator_points:
            try:
                loaded = point.load()
                plugin_operators = self._coerce_plugin_operators(point.name, loaded, llm_model=llm_model)
            except Exception as exc:
                LOGGER.warning("Failed to load operator entry point %s: %s", point.name, exc)
                continue
            for operator in plugin_operators:
                if operator.name in known_names or not self._is_allowed(operator.name):
                    continue
                known_names.add(operator.name)
                if operator.escape_only:
                    self.escape_operators.append(operator)
                else:
                    self.operators.append(operator)
                self.stats.setdefault(operator.name, self._empty_stat())

    def _coerce_plugin_operators(self, name: str, loaded: Any, *, llm_model: str) -> list[BaseOperator]:
        if isinstance(loaded, BaseOperator):
            return [loaded]
        if isinstance(loaded, type):
            if not issubclass(loaded, BaseOperator):
                raise TypeError(f"Entry point {name!r} is not a BaseOperator subclass")
            return [self._instantiate_operator_class(name, loaded, llm_model=llm_model)]
        if callable(loaded):
            produced = self._call_operator_factory(name, loaded, llm_model=llm_model)
            return self._normalize_operator_payload(name, produced, llm_model=llm_model)
        return self._normalize_operator_payload(name, loaded, llm_model=llm_model)

    def _normalize_operator_payload(self, name: str, payload: Any, *, llm_model: str) -> list[BaseOperator]:
        if isinstance(payload, BaseOperator):
            return [payload]
        if isinstance(payload, (list, tuple, set)):
            operators: list[BaseOperator] = []
            for item in payload:
                if isinstance(item, BaseOperator):
                    operators.append(item)
                    continue
                if isinstance(item, type) and issubclass(item, BaseOperator):
                    operators.append(self._instantiate_operator_class(name, item, llm_model=llm_model))
            return operators
        raise TypeError(f"Entry point {name!r} did not produce operator instances")

    def _instantiate_operator_class(self, name: str, cls: type[BaseOperator], *, llm_model: str) -> BaseOperator:
        try:
            return self._instantiate_with_llm_model(cls, llm_model)
        except Exception as exc:
            raise TypeError(f"Could not instantiate operator class from entry point {name!r}: {exc}") from exc

    def _call_operator_factory(self, name: str, factory: Any, *, llm_model: str) -> Any:
        try:
            return self._instantiate_with_llm_model(factory, llm_model)
        except Exception as exc:
            raise TypeError(f"Could not call operator factory from entry point {name!r}: {exc}") from exc

    def _instantiate_with_llm_model(self, func: Any, llm_model: str) -> Any:
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return func()

        params = list(sig.parameters.values())
        param_names = {p.name for p in params}

        if "llm_model" in param_names:
            return func(llm_model=llm_model)
        if "model" in param_names:
            return func(model=llm_model)

        if params:
            first_param = params[0]
            if first_param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                return func(llm_model)

        if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
            return func(llm_model)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
            return func(llm_model=llm_model)

        return func()
