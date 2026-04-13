from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from joule.config import JouleSettings, load_settings
from joule.utils.terminal import TerminalReporter


def _backend_ready(settings: JouleSettings, backend_name: str) -> bool:
    if backend_name == "mock":
        return True
    if backend_name == "rapl":
        rapl_options: dict[str, Any] = settings.backends.options.get("rapl", {}) if settings.backends.options else {}
        rapl_path = Path(rapl_options.get("path", "/sys/class/powercap/intel-rapl:0/energy_uj"))
        return rapl_path.exists()
    return False


def run_doctor(
    path: Path,
    backend: str | None,
    verbose: bool,
    quiet: bool,
    *,
    console,
    bootstrap_fn,
) -> None:
    import typer

    settings, _db, reporter = bootstrap_fn(path, verbose=verbose, quiet=quiet)
    chosen_backend = backend or settings.default_backend
    required_checks = [
        ("python", "ok", console.color_system is not None, "Python interpreter available"),
        ("typer", "ok", importlib.util.find_spec("typer") is not None, "Typer import"),
        ("libcst", "ok", importlib.util.find_spec("libcst") is not None, "LibCST import"),
        ("psutil", "ok", importlib.util.find_spec("psutil") is not None, "psutil import"),
        ("backend", chosen_backend, _backend_ready(settings, chosen_backend), f"Backend {chosen_backend}"),
    ]
    optional_checks = [
        ("llm-model", settings.llm_model or "unset", bool(settings.llm_model), "LLM model configured"),
        ("litellm", "ok", importlib.util.find_spec("litellm") is not None, "LiteLLM installed"),
        ("git", "ok", (settings.project_root / ".git").exists(), "Git repository detected"),
    ]
    reporter.info("doctor", f"Checking project at {settings.project_root}")
    reporter.info("doctor", "Required runtime checks")
    for _, value, ok, label in required_checks:
        status = "PASS" if ok else "WARN"
        reporter.info("doctor", f"{status} {label}: {value if value else 'missing'}")
    reporter.info("doctor", "Optional capabilities")
    for _, value, ok, label in optional_checks:
        status = "PASS" if ok else "WARN"
        reporter.info("doctor", f"{status} {label}: {value if value else 'missing'}")
