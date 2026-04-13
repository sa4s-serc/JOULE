from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from rich.console import Console


_LEVELS = {
    "silent": 0,
    "quiet": 1,
    "normal": 2,
    "verbose": 3,
    "debug": 4,
    "trace": 5,
}


@runtime_checkable
class Reporter(Protocol):
    console: Console

    def set_log_file(self, path: Path | None) -> None:
        ...

    def info(self, stage: str, message: str) -> None:
        ...

    def verbose(self, stage: str, message: str) -> None:
        ...

    def debug(self, stage: str, message: str) -> None:
        ...

    def warn(self, stage: str, message: str) -> None:
        ...


class TerminalReporter:
    def __init__(self, console: Console, verbosity: str = "normal", log_file: Path | None = None) -> None:
        self.console = console
        self.verbosity = verbosity if verbosity in _LEVELS else "normal"
        self.log_file = log_file

    def set_log_file(self, path: Path | None) -> None:
        self.log_file = path

    def _should_emit(self, minimum: str) -> bool:
        return _LEVELS[self.verbosity] >= _LEVELS[minimum]

    def _write_log(self, *, level: str, stage: str, message: str, emitted: bool) -> None:
        if self.log_file is None:
            return
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "stage": stage,
            "message": message,
            "emitted": emitted,
            "verbosity": self.verbosity,
        }
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _emit(self, *, level: str, stage: str, message: str, minimum: str, color: str) -> None:
        emitted = self._should_emit(minimum)
        if emitted:
            self.console.print(f"[bold {color}]{stage:>10}[/bold {color}] {message}")
        self._write_log(level=level, stage=stage, message=message, emitted=emitted)

    def event(self, stage: str, message: str, *, minimum: str = "normal") -> None:
        self._emit(level="event", stage=stage, message=message, minimum=minimum, color="cyan")

    def info(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="normal")

    def verbose(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="verbose")

    def debug(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="debug")

    def trace(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="trace")

    def success(self, stage: str, message: str) -> None:
        self._emit(level="success", stage=stage, message=message, minimum="normal", color="green")

    def warn(self, stage: str, message: str) -> None:
        self._emit(level="warn", stage=stage, message=message, minimum="normal", color="yellow")
