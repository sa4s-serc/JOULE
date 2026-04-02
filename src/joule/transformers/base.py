from __future__ import annotations

from abc import ABC, abstractmethod

from joule.models import TargetSpec, TransformationResult


class BaseOperator(ABC):
    name: str

    @abstractmethod
    def generate(self, target: TargetSpec) -> list[TransformationResult]:
        raise NotImplementedError
