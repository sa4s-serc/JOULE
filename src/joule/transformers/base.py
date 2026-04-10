from __future__ import annotations

from abc import ABC, abstractmethod

from joule.models import SearchContext, TargetSpec, TransformationResult


class BaseOperator(ABC):
    name: str
    family: str = "deterministic"

    @abstractmethod
    def generate(self, target: TargetSpec, context: SearchContext | None = None) -> list[TransformationResult]:
        raise NotImplementedError
