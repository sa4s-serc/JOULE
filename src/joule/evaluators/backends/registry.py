from __future__ import annotations

from importlib.metadata import entry_points
import logging
from pathlib import Path
from typing import Any, Callable

from joule.config import JouleSettings
from joule.evaluators.backends.base import EnergyBackend
from joule.evaluators.backends.energibridge import EnergiBridgeBackend
from joule.evaluators.backends.mock import MockEnergyBackend
from joule.evaluators.backends.rapl import RaplEnergyBackend


BackendFactory = Callable[[JouleSettings], EnergyBackend]
LOGGER = logging.getLogger(__name__)


class BackendRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, BackendFactory] = {
            "mock": self._mock_factory,
            "rapl": self._rapl_factory,
            "energibridge": self._energibridge_factory,
        }
        self._discover_entry_points()

    def register(self, name: str, factory: BackendFactory, *, replace: bool = False) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Backend name cannot be empty")
        if key in self._factories and not replace:
            return
        self._factories[key] = factory

    def get(self, name: str, settings: JouleSettings) -> EnergyBackend:
        key = name.strip().lower()
        try:
            factory = self._factories[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._factories))
            raise ValueError(f"Unknown backend {name!r}. Available backends: {available}") from exc
        backend = factory(settings)
        if not isinstance(backend, EnergyBackend):
            raise TypeError(f"Registered backend {name!r} does not implement EnergyBackend")
        return backend

    def names(self) -> list[str]:
        return sorted(self._factories)

    def _mock_factory(self, _settings: JouleSettings) -> EnergyBackend:
        return MockEnergyBackend()

    def _rapl_factory(self, settings: JouleSettings) -> EnergyBackend:
        rapl_options = settings.backends.options.get("rapl", {}) if settings.backends.options else {}
        rapl_path = rapl_options.get("path")
        return RaplEnergyBackend(rapl_path=Path(rapl_path) if isinstance(rapl_path, str) else None)

    def _energibridge_factory(self, settings: JouleSettings) -> EnergyBackend:
        opts = settings.backends.options.get("energibridge", {}) if settings.backends.options else {}
        binary_path: str | None = opts.get("binary_path")
        results_dir_raw: str | None = opts.get("results_dir")
        results_dir = Path(results_dir_raw) if isinstance(results_dir_raw, str) else None
        return EnergiBridgeBackend(binary_path=binary_path, results_dir=results_dir)

    def _discover_entry_points(self) -> None:
        discovered = entry_points()
        backend_points = list(discovered.select(group="joule.backends"))
        for point in backend_points:
            try:
                loaded = point.load()
                factory = self._coerce_factory(point.name, loaded)
                self.register(point.name, factory)
            except Exception as exc:
                LOGGER.warning("Failed to load backend entry point %s: %s", point.name, exc)
                continue

    def _coerce_factory(self, name: str, loaded: Any) -> BackendFactory:
        if isinstance(loaded, EnergyBackend):
            backend = loaded
            return lambda _settings: backend

        if isinstance(loaded, type):
            cls = loaded

            def class_factory(settings: JouleSettings) -> EnergyBackend:
                instance = self._instantiate(name, cls, settings)
                if not isinstance(instance, EnergyBackend):
                    raise TypeError(f"Entry point {name!r} did not create an EnergyBackend instance")
                return instance

            return class_factory

        if callable(loaded):
            factory_fn = loaded

            def callable_factory(settings: JouleSettings) -> EnergyBackend:
                produced = self._call_factory(name, factory_fn, settings)
                if not isinstance(produced, EnergyBackend):
                    raise TypeError(f"Entry point {name!r} did not produce an EnergyBackend instance")
                return produced

            return callable_factory

        raise TypeError(f"Unsupported backend entry point payload for {name!r}: {type(loaded).__name__}")

    def _instantiate(self, name: str, cls: type[Any], settings: JouleSettings) -> Any:
        try:
            return cls(settings=settings)
        except TypeError:
            try:
                return cls(settings)
            except TypeError:
                try:
                    return cls()
                except TypeError as exc:
                    raise TypeError(f"Could not instantiate backend class from entry point {name!r}") from exc

    def _call_factory(self, name: str, factory_fn: Callable[..., Any], settings: JouleSettings) -> Any:
        try:
            return factory_fn(settings=settings)
        except TypeError:
            try:
                return factory_fn(settings)
            except TypeError:
                try:
                    return factory_fn()
                except TypeError as exc:
                    raise TypeError(f"Could not call backend factory from entry point {name!r}") from exc
