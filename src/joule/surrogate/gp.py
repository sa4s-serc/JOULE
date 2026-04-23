from __future__ import annotations

import math

import numpy as np

from joule.config import GPSurrogateSettings
from joule.surrogate.models import SurrogateModelError, ensure_metric_payload
from joule.surrogate.types import METRIC_NAMES, MetricPrediction


class GaussianProcessSurrogateModel:
    kind = "gp"

    def __init__(self, settings: GPSurrogateSettings) -> None:
        self._noise = max(float(settings.noise), 1e-9)
        self._length_scale = max(float(settings.length_scale), 1e-6)
        self._nu = 2.5 if float(settings.nu) > 1.5 else 1.5
        self._max_exact_points = max(3, int(settings.max_exact_points))
        self._cache_revision = -1
        self._cached_x_train: np.ndarray | None = None
        self._cached_length_scale = self._length_scale
        self._cached_cholesky: np.ndarray | None = None
        self._cached_heads: dict[str, tuple[float, float, np.ndarray]] = {}

    def predict(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        x_query: np.ndarray,
        training_revision: int,
    ) -> dict[str, MetricPrediction]:
        if len(x_train) > self._max_exact_points:
            raise SurrogateModelError("GP exact mode disabled above max_exact_points")
        if not self._ensure_cache(x_train=x_train, y_train=y_train, training_revision=training_revision):
            raise SurrogateModelError("GP cache unavailable")
        if self._cached_x_train is None or self._cached_cholesky is None:
            raise SurrogateModelError("GP cache missing training matrix")
        chol = self._cached_cholesky
        k_star = self._matern_kernel(
            self._cached_x_train,
            x_query.reshape(1, -1),
            length_scale=self._cached_length_scale,
        ).reshape(-1)
        v = np.linalg.solve(chol, k_star)
        k_self = float(
            self._matern_kernel(
                x_query.reshape(1, -1),
                x_query.reshape(1, -1),
                length_scale=self._cached_length_scale,
            )[0, 0]
        )
        variance_norm = max(k_self - float(v @ v), 1e-9)
        predictions: dict[str, MetricPrediction] = {}
        for metric in METRIC_NAMES:
            y_mean, y_scale, alpha = self._cached_heads[metric]
            mean_norm = float(k_star @ alpha)
            predictions[metric] = MetricPrediction(
                mean=float(y_mean + (y_scale * mean_norm)),
                uncertainty=float(abs(y_scale) * math.sqrt(variance_norm)),
            )
        return ensure_metric_payload(predictions)

    def _ensure_cache(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        training_revision: int,
    ) -> bool:
        if self._cache_revision == training_revision:
            return self._cached_cholesky is not None and bool(self._cached_heads)
        length_scale = self._adaptive_length_scale(x_train)
        kernel = self._matern_kernel(x_train, x_train, length_scale=length_scale)
        jitter_schedule = (self._noise, 1e-6, 1e-5, 1e-4, 1e-3)
        self._cached_x_train = x_train
        self._cached_length_scale = length_scale
        self._cached_cholesky = None
        self._cached_heads = {}
        for jitter in jitter_schedule:
            stabilized = kernel + (np.eye(len(x_train)) * jitter)
            try:
                chol = np.linalg.cholesky(stabilized)
            except np.linalg.LinAlgError:
                continue
            heads: dict[str, tuple[float, float, np.ndarray]] = {}
            for metric in METRIC_NAMES:
                values = y_train[metric]
                y_mean = float(np.mean(values))
                y_std = float(np.std(values))
                y_scale = y_std if y_std > 1e-9 else 1.0
                y_norm = (values - y_mean) / y_scale
                alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y_norm))
                heads[metric] = (y_mean, y_scale, alpha)
            self._cached_cholesky = chol
            self._cached_heads = heads
            self._cache_revision = training_revision
            return True
        self._cache_revision = training_revision
        return False

    def _adaptive_length_scale(self, x_train: np.ndarray) -> float:
        if len(x_train) < 2:
            return self._length_scale
        diffs = x_train[:, None, :] - x_train[None, :, :]
        distances = np.linalg.norm(diffs, axis=2)
        tri_upper = distances[np.triu_indices(len(x_train), k=1)]
        non_zero = tri_upper[tri_upper > 1e-9]
        if non_zero.size == 0:
            return self._length_scale
        median_distance = float(np.median(non_zero))
        return max(self._length_scale, median_distance)

    def _matern_kernel(self, left: np.ndarray, right: np.ndarray, *, length_scale: float) -> np.ndarray:
        scale = max(length_scale, 1e-6)
        deltas = (left[:, None, :] - right[None, :, :]) / scale
        distances = np.linalg.norm(deltas, axis=2)
        if self._nu <= 1.5:
            root3 = math.sqrt(3.0)
            return (1.0 + (root3 * distances)) * np.exp(-root3 * distances)
        root5 = math.sqrt(5.0)
        return (1.0 + (root5 * distances) + ((5.0 / 3.0) * (distances**2))) * np.exp(-root5 * distances)
