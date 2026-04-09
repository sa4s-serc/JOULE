from __future__ import annotations

from rich.console import Console


_LEVELS = {"quiet": 0, "normal": 1, "verbose": 2}


class TerminalReporter:
    def __init__(self, console: Console, verbosity: str = "normal") -> None:
        self.console = console
        self.verbosity = verbosity if verbosity in _LEVELS else "normal"

    def event(self, stage: str, message: str, *, minimum: str = "normal") -> None:
        if _LEVELS[self.verbosity] < _LEVELS[minimum]:
            return
        self.console.print(f"[bold cyan]{stage:>10}[/bold cyan] {message}")

    def info(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="normal")

    def verbose(self, stage: str, message: str) -> None:
        self.event(stage, message, minimum="verbose")

    def success(self, stage: str, message: str) -> None:
        if _LEVELS[self.verbosity] < _LEVELS["normal"]:
            return
        self.console.print(f"[bold green]{stage:>10}[/bold green] {message}")

    def warn(self, stage: str, message: str) -> None:
        if _LEVELS[self.verbosity] < _LEVELS["normal"]:
            return
        self.console.print(f"[bold yellow]{stage:>10}[/bold yellow] {message}")
