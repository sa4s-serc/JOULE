from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from joule.surrogate.types import METRIC_NAMES, MetricPrediction


class SurrogateModelError(RuntimeError):
    pass


class SurrogateModel(Protocol):
    kind: str

    def predict(
        self,
        *,
        x_train: np.ndarray,
        y_train: dict[str, np.ndarray],
        x_query: np.ndarray,
        training_revision: int,
    ) -> dict[str, MetricPrediction]:
        raise NotImplementedError


@dataclass(slots=True)
class ModelDataset:
    x_train: np.ndarray
    y_train: dict[str, np.ndarray]
    x_query: np.ndarray
    training_revision: int


def ensure_metric_payload(payload: dict[str, MetricPrediction]) -> dict[str, MetricPrediction]:
    return {metric: payload[metric] for metric in METRIC_NAMES}
