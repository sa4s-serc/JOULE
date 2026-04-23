from __future__ import annotations

import math

import numpy as np

from joule.config import LocalKernelSurrogateSettings
from joule.surrogate.models import SurrogateModelError, ensure_metric_payload
from joule.surrogate.types import METRIC_NAMES, MetricPrediction


class LocalKernelSurrogateModel:
    kind = "local_kernel"

    def __init__(self, settings: LocalKernelSurrogateSettings) -> None:
        self._bandwidth_floor = max(float(settings.bandwidth_floor), 1e-9)
        self._min_neighbors = max(1, int(settings.min_neighbors))

    def predict(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        x_query: np.ndarray,
        training_revision: int,
    ) -> dict[str, MetricPrediction]:
        del training_revision
        if len(x_train) == 0:
            raise SurrogateModelError("Local kernel model requires at least one observation")
        distances = np.linalg.norm(x_train - x_query, axis=1)
        scale = float(np.median(distances)) if len(distances) else 1.0
        bandwidth = max(self._bandwidth_floor, scale)
        if self._min_neighbors > 1 and len(distances) > self._min_neighbors:
            neighbor_count = min(len(distances), max(self._min_neighbors, 3))
            nearest = np.partition(distances, neighbor_count - 1)[:neighbor_count]
            bandwidth = max(bandwidth, float(np.max(nearest)))
        weights = np.exp(-(distances**2) / (2.0 * (bandwidth**2)))
        if float(weights.sum()) <= 0.0:
            weights = np.ones_like(distances, dtype=float)
        predictions: dict[str, MetricPrediction] = {}
        for metric in METRIC_NAMES:
            values = y_train[metric]
            if len(values) == 0:
                raise SurrogateModelError(f"Missing training targets for metric {metric}")
            mean = float(np.dot(weights, values) / weights.sum())
            if len(values) > 1:
                variance = float(np.average((values - mean) ** 2, weights=weights))
            else:
                variance = 1.0
            predictions[metric] = MetricPrediction(
                mean=mean,
                uncertainty=math.sqrt(max(variance, 1e-6)),
            )
        return ensure_metric_payload(predictions)
