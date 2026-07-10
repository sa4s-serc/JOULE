"""Doctor command — runtime and plugin readiness checks."""

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


def _check_plugins(settings: JouleSettings) -> list[tuple[str, str, bool, str]]:
    """Validate all registered operator plugins against the BaseOperator protocol.

    Returns a list of ``(name, value, ok, label)`` tuples compatible with the
    doctor check format.
    """
    from importlib.metadata import entry_points
    from joule.transformers.base import BaseOperator
    from joule.transformers.protocols import OperatorSelectorProtocol

    checks: list[tuple[str, str, bool, str]] = []
    points = list(entry_points().select(group="joule.operators"))
    if not points:
        checks.append(("plugins", "none registered", True, "No external operator plugins found"))
        return checks

    for point in points:
        try:
            loaded = point.load()
            # Resolve to an instance or class
            if isinstance(loaded, type):
                instance = loaded()
            elif callable(loaded):
                instance = loaded()
            else:
                instance = loaded

            is_base = isinstance(instance, BaseOperator)
            has_name = hasattr(instance, "name") and isinstance(instance.name, str)
            has_generate = callable(getattr(instance, "generate", None))
            ok = is_base and has_name and has_generate
            detail = "valid" if ok else f"missing: {'name ' if not has_name else ''}{'generate' if not has_generate else ''}"
            checks.append((f"plugin:{point.name}", detail, ok, f"Plugin {point.name!r}"))
        except Exception as exc:
            checks.append((f"plugin:{point.name}", str(exc)[:60], False, f"Plugin {point.name!r} load error"))

    return checks


def run_doctor(
    path: Path,
    backend: str | None,
    verbose: bool,
    quiet: bool,
    *,
    console,
    bootstrap_fn,
    plugin_check: bool = False,
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

    if plugin_check:
        reporter.info("doctor", "Plugin checks")
        plugin_checks = _check_plugins(settings)
        any_plugin_fail = False
        for _, value, ok, label in plugin_checks:
            status = "PASS" if ok else "FAIL"
            reporter.info("doctor", f"{status} {label}: {value}")
            if not ok:
                any_plugin_fail = True
        if any_plugin_fail:
            raise typer.Exit(code=1)
