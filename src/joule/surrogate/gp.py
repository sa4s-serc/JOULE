from __future__ import annotations

import ast
import math

import numpy as np

from joule.models import TargetSpec


class GaussianProcessSurrogate:
    def __init__(self) -> None:
        self._x: list[np.ndarray] = []
        self._y: list[float] = []

    def features(self, source: str) -> np.ndarray:
        tree = ast.parse(source)
        node_count = sum(1 for _ in ast.walk(tree))
        loop_count = sum(isinstance(node, (ast.For, ast.While, ast.comprehension)) for node in ast.walk(tree))
        call_count = sum(isinstance(node, ast.Call) for node in ast.walk(tree))
        branch_count = sum(isinstance(node, (ast.If, ast.Match)) for node in ast.walk(tree))
        return np.array([len(source), node_count, loop_count, call_count, branch_count], dtype=float)

    def record(self, source: str, score: float) -> None:
        self._x.append(self.features(source))
        self._y.append(score)

    def predict(self, source: str) -> tuple[float, float]:
        if not self._x:
            return 0.0, 1.0
        x = self.features(source)
        x_train = np.vstack(self._x)
        y_train = np.array(self._y)
        distances = np.linalg.norm(x_train - x, axis=1)
        weights = np.exp(-(distances ** 2) / (2.0 * (np.var(distances) + 1.0)))
        if float(weights.sum()) == 0.0:
            return float(y_train.mean()), float(y_train.std() if len(y_train) > 1 else 1.0)
        mean = float(np.dot(weights, y_train) / weights.sum())
        variance = float(np.average((y_train - mean) ** 2, weights=weights)) if len(y_train) > 1 else 1.0
        return mean, math.sqrt(max(variance, 1e-6))

    def is_promising(self, source: str, best_score: float) -> bool:
        mean, uncertainty = self.predict(source)
        return (mean - uncertainty) <= best_score or uncertainty >= 0.25
