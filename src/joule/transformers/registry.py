from __future__ import annotations

import math
from typing import Any

from joule.models import SearchContext, SearchPhase, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator
from joule.transformers.deterministic import default_deterministic_operators
from joule.transformers.generative import default_llm_operators, escape_llm_operators


class OperatorRegistry:
    def __init__(self, *, llm_model: str, include_llm: bool = True) -> None:
        self.operators: list[BaseOperator] = default_deterministic_operators()
        self.escape_operators: list[BaseOperator] = []
        self.stats: dict[str, dict[str, Any]] = {operator.name: self._empty_stat() for operator in self.operators}
        if include_llm and llm_model.strip():
            llm_ops = default_llm_operators(llm_model)
            self.operators.extend(llm_ops)
            self.escape_operators.extend(escape_llm_operators(llm_model))
            for operator in [*llm_ops, *self.escape_operators]:
                self.stats.setdefault(operator.name, self._empty_stat())

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

    def select_operator_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
    ) -> BaseOperator | None:
        ranked = self.ranked(phase=phase, parent_generation=parent_generation)
        valid = self._precheck_ranked(ranked, target=target, context=context)
        return valid[0] if valid else None

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
            + (0.60 * frontier_rate)
            + (0.25 * depth_fit)
            + (0.20 * phase_fit)
            - (0.35 * duplicate_rate)
            - (0.40 * correctness_failure_rate)
            - (0.20 * precheck_failure_rate)
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
