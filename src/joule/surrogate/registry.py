from __future__ import annotations

from typing import Callable

from joule.config import JouleSettings
from joule.surrogate.gp import GaussianProcessSurrogateModel
from joule.surrogate.hist_gbdt import HistGradientBoostingSurrogateModel
from joule.surrogate.local_kernel import LocalKernelSurrogateModel
from joule.surrogate.models import SurrogateModel


SurrogateFactory = Callable[[JouleSettings], SurrogateModel]


class SurrogateRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, SurrogateFactory] = {
            "gp": lambda settings: GaussianProcessSurrogateModel(settings.surrogate.gp),
            "local_kernel": lambda settings: LocalKernelSurrogateModel(settings.surrogate.local_kernel),
            "hist_gbdt": lambda settings: HistGradientBoostingSurrogateModel(settings.surrogate.hist_gbdt),
        }

    def create(self, kind: str, settings: JouleSettings) -> SurrogateModel:
        key = kind.strip().lower()
        try:
            return self._factories[key](settings)
        except KeyError as exc:
            available = ", ".join(sorted(self._factories))
            raise ValueError(f"Unknown surrogate model {kind!r}. Available models: {available}") from exc
