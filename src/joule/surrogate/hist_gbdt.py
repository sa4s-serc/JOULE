from __future__ import annotations

import math

import numpy as np

from joule.config import HistGBDTSurrogateSettings
from joule.surrogate.models import SurrogateModelError, ensure_metric_payload
from joule.surrogate.types import METRIC_NAMES, MetricPrediction


class HistGradientBoostingSurrogateModel:
    kind = "hist_gbdt"

    def __init__(self, settings: HistGBDTSurrogateSettings) -> None:
        self._settings = settings
        self._cache_revision = -1
        self._models: dict[str, tuple[object, object, object]] = {}

    def predict(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        x_query: np.ndarray,
        training_revision: int,
    ) -> dict[str, MetricPrediction]:
        required_points = max(4, int(self._settings.min_samples_leaf) * 2)
        if len(x_train) < required_points:
            raise SurrogateModelError("HistGBDT requires more observations")
        self._ensure_models(x_train=x_train, y_train=y_train, training_revision=training_revision)
        predictions: dict[str, MetricPrediction] = {}
        for metric in METRIC_NAMES:
            center_model, lower_model, upper_model = self._models[metric]
            mean = float(center_model.predict(x_query.reshape(1, -1))[0])
            lower = float(lower_model.predict(x_query.reshape(1, -1))[0])
            upper = float(upper_model.predict(x_query.reshape(1, -1))[0])
            spread = max(abs(upper - lower) / 2.0, 1e-6)
            if not all(math.isfinite(value) for value in (mean, lower, upper, spread)):
                raise SurrogateModelError("HistGBDT produced non-finite prediction")
            predictions[metric] = MetricPrediction(mean=mean, uncertainty=spread)
        return ensure_metric_payload(predictions)

    def _ensure_models(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        training_revision: int,
    ) -> None:
        if self._cache_revision == training_revision and self._models:
            return
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
        except ImportError as exc:
            raise SurrogateModelError("scikit-learn is required for the hist_gbdt surrogate") from exc

        kwargs = {
            "learning_rate": float(self._settings.learning_rate),
            "max_iter": int(self._settings.max_iter),
            "max_leaf_nodes": int(self._settings.max_leaf_nodes),
            "max_depth": self._settings.max_depth,
            "min_samples_leaf": int(self._settings.min_samples_leaf),
            "l2_regularization": float(self._settings.l2_regularization),
            "random_state": 1337,
        }
        models: dict[str, tuple[object, object, object]] = {}
        for metric in METRIC_NAMES:
            values = y_train[metric]
            center_model = HistGradientBoostingRegressor(loss="squared_error", **kwargs)
            lower_model = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=float(self._settings.lower_quantile),
                **kwargs,
            )
            upper_model = HistGradientBoostingRegressor(
                loss="quantile",
                quantile=float(self._settings.upper_quantile),
                **kwargs,
            )
            center_model.fit(x_train, values)
            lower_model.fit(x_train, values)
            upper_model.fit(x_train, values)
            models[metric] = (center_model, lower_model, upper_model)
        self._models = models
        self._cache_revision = training_revision
