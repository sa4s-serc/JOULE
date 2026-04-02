from __future__ import annotations

import math

from joule.models import TransformationResult
from joule.transformers.base import BaseOperator
from joule.transformers.deterministic import default_deterministic_operators
from joule.transformers.generative import GenerativeLLMOperator


class OperatorRegistry:
    def __init__(self, *, llm_model: str, include_llm: bool = True) -> None:
        self.operators: list[BaseOperator] = default_deterministic_operators()
        self.stats: dict[str, dict[str, float]] = {operator.name: {"attempts": 0.0, "successes": 0.0, "reward": 0.0} for operator in self.operators}
        if include_llm:
            llm = GenerativeLLMOperator(llm_model)
            self.operators.append(llm)
            self.stats[llm.name] = {"attempts": 0.0, "successes": 0.0, "reward": 0.0}

    def ranked(self) -> list[BaseOperator]:
        total_attempts = sum(max(1.0, stat["attempts"]) for stat in self.stats.values())
        return sorted(self.operators, key=lambda operator: self._ucb(operator.name, total_attempts), reverse=True)

    def update(self, result: TransformationResult, success: bool, reward: float) -> None:
        stat = self.stats.setdefault(result.operator_name, {"attempts": 0.0, "successes": 0.0, "reward": 0.0})
        stat["attempts"] += 1
        stat["successes"] += 1 if success else 0
        stat["reward"] += reward

    def load_stats(self, persisted: dict[str, dict[str, float]]) -> None:
        for name, values in persisted.items():
            if name not in self.stats:
                continue
            self.stats[name] = {
                "attempts": float(values.get("attempts", 0.0)),
                "successes": float(values.get("successes", 0.0)),
                "reward": float(values.get("reward", 0.0)),
            }

    def _ucb(self, name: str, total_attempts: float) -> float:
        stat = self.stats[name]
        attempts = max(1.0, stat["attempts"])
        mean_reward = stat["reward"] / attempts
        exploration = math.sqrt((2.0 * math.log(total_attempts + 1.0)) / attempts)
        success_bonus = stat["successes"] / attempts
        return mean_reward + success_bonus + exploration
