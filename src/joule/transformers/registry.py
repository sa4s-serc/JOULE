from __future__ import annotations

from importlib.metadata import entry_points
import logging
import math
from typing import Any

from joule.models import SearchContext, SearchPhase, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator
from joule.transformers.deterministic import default_deterministic_operators
from joule.transformers.generative import default_llm_operators, escape_llm_operators


LOGGER = logging.getLogger(__name__)

# Contextual scoring weights for operator selection.
# These balance exploration (UCB) with operator-specific performance signals.
_SCORE_FRONTIER_BONUS = 0.60   # reward for operators that have contributed to the frontier
_SCORE_DEPTH_FIT = 0.25        # reward for operators that succeed at the current generation depth
_SCORE_PHASE_FIT = 0.20        # reward for operators that succeed in the current search phase
_SCORE_DUPLICATE_PENALTY = 0.35        # penalty for operators that produce duplicate sources
_SCORE_CORRECTNESS_PENALTY = 0.40      # penalty for operators that produce incorrect candidates
_SCORE_PRECHECK_PENALTY = 0.20         # penalty for operators that fail precheck


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

    def _is_allowed(self, name: str) -> bool:
        if self.kill_switches.get(name, False):
            return False
        if name in self.denylist:
            return False
        if self.allowlist is not None and name not in self.allowlist:
            return False
        return True

    def ranked(self, *, phase: SearchPhase | None = None, parent_generation: int = 0) -> list[BaseOperator]:
        total_attempts = sum(max(1.0, stat["attempts"]) for stat in self.stats.values())
        return sorted(
            self.operators,
            key=lambda operator: self._contextual_score(
                operator.name,
                total_attempts,
                phase=phase,
                parent_generation=parent_generation,
            ),
            reverse=True,
        )

    def select_operator(self, *, phase: SearchPhase, parent_generation: int) -> BaseOperator:
        return self.ranked(phase=phase, parent_generation=parent_generation)[0]

    def select_operators(self, *, phase: SearchPhase, parent_generation: int, top_k: int = 1) -> list[BaseOperator]:
        return self.ranked(phase=phase, parent_generation=parent_generation)[:top_k]

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
        ranked = self.ranked(phase=phase, parent_generation=parent_generation)
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
        attempts = max(1.0, stat["attempts"])
        mean_reward = stat["reward"] / attempts
        if not math.isfinite(mean_reward):
            mean_reward = 0.0
        exploration = math.sqrt((2.0 * math.log(total_attempts + 1.0)) / attempts)
        success_bonus = stat["successes"] / attempts
        return mean_reward + success_bonus + exploration

    def _contextual_score(
        self,
        name: str,
        total_attempts: float,
        *,
        phase: SearchPhase | None,
        parent_generation: int,
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
        return (
            self._ucb(name, total_attempts)
            + (_SCORE_FRONTIER_BONUS * frontier_rate)
            + (_SCORE_DEPTH_FIT * depth_fit)
            + (_SCORE_PHASE_FIT * phase_fit)
            - (_SCORE_DUPLICATE_PENALTY * duplicate_rate)
            - (_SCORE_CORRECTNESS_PENALTY * correctness_failure_rate)
            - (_SCORE_PRECHECK_PENALTY * precheck_failure_rate)
        )

    def _empty_stat(self) -> dict[str, Any]:
        return {
            "attempts": 0.0,
            "successes": 0.0,
            "reward": 0.0,
            "duplicates": 0.0,
            "correctness_failures": 0.0,
            "frontier_contributions": 0.0,
            "precheck_failures": 0.0,
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
        for args, kwargs in [
            ((llm_model,), {}),
            ((), {"model": llm_model}),
            ((), {"llm_model": llm_model}),
            ((), {}),
        ]:
            try:
                return cls(*args, **kwargs)
            except TypeError:
                continue
        raise TypeError(f"Could not instantiate operator class from entry point {name!r}")

    def _call_operator_factory(self, name: str, factory: Any, *, llm_model: str) -> Any:
        for args, kwargs in [
            ((llm_model,), {}),
            ((), {"model": llm_model}),
            ((), {"llm_model": llm_model}),
            ((), {}),
        ]:
            try:
                return factory(*args, **kwargs)
            except TypeError:
                continue
        raise TypeError(f"Could not call operator factory from entry point {name!r}")
