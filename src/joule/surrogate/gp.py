from __future__ import annotations

import ast
import math
from typing import Any

import numpy as np

from joule.models import SearchContext, SearchPhase


class GaussianProcessSurrogate:
    def __init__(self) -> None:
        self._x: list[np.ndarray] = []
        self._y: list[float] = []
        self._sources: list[str] = []

    def features(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> np.ndarray:
        tree = ast.parse(source)
        node_count = sum(1 for _ in ast.walk(tree))
        loop_count = sum(isinstance(node, (ast.For, ast.While, ast.comprehension)) for node in ast.walk(tree))
        comp_count = sum(isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for node in ast.walk(tree))
        call_count = sum(isinstance(node, ast.Call) for node in ast.walk(tree))
        branch_count = sum(isinstance(node, (ast.If, ast.Match)) for node in ast.walk(tree))
        assign_count = sum(isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for node in ast.walk(tree))
        container_count = sum(isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) for node in ast.walk(tree))
        literal_count = sum(isinstance(node, ast.Constant) for node in ast.walk(tree))
        subscript_count = sum(isinstance(node, ast.Subscript) for node in ast.walk(tree))
        lambda_count = sum(isinstance(node, ast.Lambda) for node in ast.walk(tree))
        parent_len_delta = 0.0
        generation_depth = 0.0
        if context is not None:
            parent_len_delta = float(abs(len(source) - len(context.parent_source)))
            generation_depth = float(context.generation_depth)
        hints = feature_hints or {}
        return np.array(
            [
                float(len(source)),
                float(node_count),
                float(loop_count),
                float(comp_count),
                float(call_count),
                float(branch_count),
                float(assign_count),
                float(container_count),
                float(literal_count),
                float(subscript_count),
                float(lambda_count),
                parent_len_delta,
                generation_depth,
                float(hints.get("ast_shape_delta", 0.0)),
                float(hints.get("allocation_pattern_delta", 0.0)),
                float(hints.get("call_density_delta", 0.0)),
            ],
            dtype=float,
        )

    def record(
        self,
        source: str,
        score: float,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> None:
        self._x.append(self.features(source, feature_hints=feature_hints, context=context))
        self._y.append(score)
        self._sources.append(source)

    def predict(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> tuple[float, float]:
        if not self._x:
            return 0.0, 1.0
        x = self.features(source, feature_hints=feature_hints, context=context)
        x_train = np.vstack(self._x)
        y_train = np.array(self._y)
        distances = np.linalg.norm(x_train - x, axis=1)
        scale = float(np.median(distances)) if len(distances) else 1.0
        bandwidth = max(1e-6, scale)
        weights = np.exp(-(distances ** 2) / (2.0 * (bandwidth**2)))
        if float(weights.sum()) == 0.0:
            return float(y_train.mean()), float(y_train.std() if len(y_train) > 1 else 1.0)
        mean = float(np.dot(weights, y_train) / weights.sum())
        variance = float(np.average((y_train - mean) ** 2, weights=weights)) if len(y_train) > 1 else 1.0
        return mean, math.sqrt(max(variance, 1e-6))

    def novelty(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> float:
        if not self._x:
            return 1.0
        x = self.features(source, feature_hints=feature_hints, context=context)
        x_train = np.vstack(self._x)
        distances = np.linalg.norm(x_train - x, axis=1)
        nearest = float(distances.min())
        spread = float(np.mean(distances)) if len(distances) else 1.0
        if spread <= 1e-9:
            return 0.0 if nearest <= 1e-9 else 1.0
        return max(0.0, min(1.0, nearest / (spread + 1e-9)))

    def screen_candidate(
        self,
        *,
        source: str,
        best_score: float,
        phase: SearchPhase,
        min_novelty: float,
        min_training_points: int,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> dict[str, Any]:
        novelty = self.novelty(source, feature_hints=feature_hints, context=context)
        mean, uncertainty = self.predict(source, feature_hints=feature_hints, context=context)
        expected_improvement = max(0.0, best_score - mean)
        exploration_weight = {
            SearchPhase.EXPLORATION: 1.0,
            SearchPhase.EXPLOITATION: 0.6,
            SearchPhase.CONFIRMATION: 0.3,
        }[phase]
        acquisition_score = expected_improvement + (exploration_weight * uncertainty)
        decision = "escalate"
        reason = ""
        if novelty < min_novelty:
            decision = "reject"
            reason = "low_novelty"
        elif len(self._y) < min_training_points:
            decision = "escalate"
            reason = "insufficient_training"
        elif acquisition_score <= 0.0 and uncertainty < 0.10:
            decision = "reject"
            reason = "low_value_of_information"
        elif phase is SearchPhase.CONFIRMATION and acquisition_score < 0.03:
            decision = "measure_partial"
            reason = "low_confirmation_value"
        elif expected_improvement < 0.01 and uncertainty < 0.20:
            decision = "measure_partial"
            reason = "uncertain_small_gain"
        return {
            "decision": decision,
            "reason": reason,
            "predicted_score": mean,
            "uncertainty": uncertainty,
            "novelty": novelty,
            "acquisition_score": acquisition_score,
            "expected_improvement": expected_improvement,
        }
