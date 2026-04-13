from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from joule.cli_helpers.flow import ExecutionContext, JouleContainer, create_run_record, resolve_target_and_bundle
from joule.cli_helpers.output import resolve_output_mode
from joule.cli_commands.apply import run_apply
from joule.cli_commands.baseline import run_baseline
from joule.cli_commands.config_show import run_config_show
from joule.cli_commands.run import run_optimize
from joule.cli_commands.dashboard import run_dashboard
from joule.cli_commands.discover import run_discover
from joule.cli_commands.doctor import run_doctor
from joule.cli_commands.inspect import run_inspect
from joule.cli_commands.parse_json import run_parse_json
from joule.cli_commands.resume import run_resume
from joule.cli_commands.transformations import run_transformations
from joule.config import JouleSettings, load_settings
from joule.evaluators.oracle import PerformanceOracle
from joule.models import RunType
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.utils.artifacts import ensure_artifacts, seed_random
from joule.utils.db import JouleDB
from joule.utils.terminal import TerminalReporter

app = typer.Typer(help="JOULE optimization toolkit")
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")
console = Console()

PATH_HELP = "Path to a target .py file or project root with pyproject.toml"


def _validate_positive(value: int | None, *, option_name: str) -> None:
    if value is not None and value < 1:
        raise typer.BadParameter(f"{option_name} must be >= 1")


def _validate_non_negative(value: float | None, *, option_name: str) -> None:
    if value is not None and value < 0:
        raise typer.BadParameter(f"{option_name} must be >= 0")

def _bootstrap(path: Path, *, verbose: bool = False, quiet: bool = False):
    try:
        settings = load_settings(path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    ensure_artifacts(settings)
    seed_random(settings.seed)
    reporter = TerminalReporter(console, _resolve_verbosity(settings, verbose=verbose, quiet=quiet))
    db = JouleDB(settings.db_path)
    return settings, db, reporter


def _resolve_verbosity(settings: JouleSettings, *, verbose: bool, quiet: bool) -> str:
    if quiet:
        return "quiet"
    if verbose:
        return "verbose"
    return settings.terminal_verbosity

def _build_execution_context(
    *,
    path: Path,
    function: str,
    tests: list[str] | None,
    properties: list[str] | None,
    harness: str | None,
    backend: str | None,
    parallel: int | None,
    run_type: RunType,
    verbose: bool,
    quiet: bool,
) -> ExecutionContext:
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    if parallel is not None:
        settings.max_parallel_workers = parallel
    target, bundle = resolve_target_and_bundle(
        path=path,
        function=function,
        settings=settings,
        reporter=reporter,
        tests=tests,
        properties=properties,
        harness=harness,
    )
    chosen_backend = backend or settings.default_backend
    record, run_id, run_dir = create_run_record(
        settings=settings,
        db=db,
        run_type=run_type,
        target=target,
        bundle=bundle,
        chosen_backend=chosen_backend,
    )
    reporter.set_log_file(run_dir / "events.jsonl")
    reporter.info("run", f"Initialized {run_type.value} run {run_id}")
    oracle = PerformanceOracle.create(settings, backend_name=backend, reporter=reporter, db=db)
    orchestrator = OptimizationOrchestrator.create(settings, db, oracle, reporter=reporter)
    container = JouleContainer(
        settings=settings,
        db=db,
        reporter=reporter,
        oracle=oracle,
        orchestrator=orchestrator,
        correctness=orchestrator.correctness,
        registry=orchestrator.registry,
        surrogate=orchestrator.surrogate,
    )
    return ExecutionContext(
        container=container,
        settings=settings,
        db=db,
        reporter=reporter,
        target=target,
        bundle=bundle,
        chosen_backend=chosen_backend,
        run_id=run_id,
        run_dir=run_dir,
        record=record,
        oracle=oracle,
        orchestrator=orchestrator,
    )


@app.command()
def doctor(
    path: Path = typer.Argument(..., help=PATH_HELP),
    backend: str | None = typer.Option(None, "--backend", help="Backend to validate"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed checks"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    run_doctor(path, backend, verbose, quiet, console=console, bootstrap_fn=_bootstrap)


@app.command("transformations")
def transformations(
    path: Path = typer.Argument(..., help=PATH_HELP),
    output: str = typer.Option("human", "--output", help="Output format: human or json"),
):
    run_transformations(path, output, console=console)


@app.command()
def baseline(
    path: Path = typer.Argument(..., help=PATH_HELP),
    function: str = typer.Option(
        ...,
        "--function",
        help="Target function qualname (for example: module.func or ClassName.method)",
    ),
    tests: list[str] = typer.Option(None, "--tests", help="Explicit pytest node ids"),
    properties: list[str] = typer.Option(None, "--properties", help="Property callables"),
    harness: str | None = typer.Option(None, "--harness", help="Harness callable"),
    backend: str | None = typer.Option(None, "--backend", help="Energy backend"),
    output: str = typer.Option("human", "--output", help="Output format: human or json"),
    repetitions: int | None = typer.Option(
        None,
        "--repetitions",
        help="Override baseline repetitions (default: [tool.joule].baseline_repetitions)",
    ),
    hotspots: bool = typer.Option(False, "--hotspots", help="Run hotspot analysis after baseline measurement"),
    hotspot_limit: int | None = typer.Option(
        None,
        "--hotspot-limit",
        help="Number of hotspot functions to keep (default: [tool.joule].hotspot_limit)",
    ),
    no_dashboard: bool = typer.Option(False, "--no-dashboard", help="Skip dashboard hint output"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable measurement cache"),
    parallel: int | None = typer.Option(None, "--parallel", help="Override max parallel workers"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    _validate_positive(repetitions, option_name="--repetitions")
    _validate_positive(hotspot_limit, option_name="--hotspot-limit")
    _validate_positive(parallel, option_name="--parallel")
    output_mode = resolve_output_mode(output)
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    context = _build_execution_context(
        path=path,
        function=function,
        tests=tests,
        properties=properties,
        harness=harness,
        backend=backend,
        parallel=parallel,
        run_type=RunType.BASELINE,
        verbose=verbose,
        quiet=effective_quiet,
    )
    run_baseline(context, output=output_mode, repetitions=repetitions, hotspots=hotspots, hotspot_limit=hotspot_limit, no_dashboard=no_dashboard, no_cache=no_cache)


@app.command()
def run(
    path: Path = typer.Argument(..., help=PATH_HELP),
    function: str = typer.Option(
        ...,
        "--function",
        help="Target function qualname (for example: module.func or ClassName.method)",
    ),
    tests: list[str] = typer.Option(None, "--tests", help="Explicit pytest node ids"),
    properties: list[str] = typer.Option(None, "--properties", help="Property callables"),
    harness: str | None = typer.Option(None, "--harness", help="Harness callable"),
    backend: str | None = typer.Option(None, "--backend", help="Energy backend"),
    budget: int | None = typer.Option(None, "--budget", help="Candidate budget (must be >= 1)"),
    output: str = typer.Option("human", "--output", help="Output format: human or json"),
    analysis: bool = typer.Option(False, "--analysis", help="Persist deep optimization analysis artifacts"),
    no_dashboard: bool = typer.Option(False, "--no-dashboard", help="Skip dashboard hint output"),
    ci: bool = typer.Option(False, "--ci", help="CI mode: force JSON output, disable dashboard, and use thresholded exit codes"),
    improvement_threshold: float | None = typer.Option(
        None,
        "--improvement-threshold",
        help="Minimum scalar improvement ratio required for CI success",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable measurement cache"),
    fresh_surrogate: bool = typer.Option(
        False,
        "--fresh-surrogate",
        help="Start without loading persisted surrogate observations",
    ),
    parallel: int | None = typer.Option(None, "--parallel", help="Override max parallel workers"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    _validate_positive(budget, option_name="--budget")
    _validate_positive(parallel, option_name="--parallel")
    _validate_non_negative(improvement_threshold, option_name="--improvement-threshold")
    output_mode = "json" if ci else resolve_output_mode(output)
    no_dashboard = no_dashboard or ci
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    context = _build_execution_context(
        path=path,
        function=function,
        tests=tests,
        properties=properties,
        harness=harness,
        backend=backend,
        parallel=parallel,
        run_type=RunType.OPTIMIZE,
        verbose=verbose,
        quiet=effective_quiet,
    )
    run_optimize(
        context,
        budget=budget,
        analysis=analysis,
        no_dashboard=no_dashboard,
        output=output_mode,
        no_cache=no_cache,
        ci=ci,
        improvement_threshold=improvement_threshold,
        fresh_surrogate=fresh_surrogate,
    )


@app.command()
def resume(
    path: Path = typer.Argument(..., help=PATH_HELP),
    run_id: str = typer.Option(..., "--run-id", help="Run identifier to resume"),
    budget: int | None = typer.Option(None, "--budget", help="Override total candidate budget for resumed run"),
    output: str = typer.Option("human", "--output", help="Output format: human or json"),
    analysis: bool = typer.Option(False, "--analysis", help="Persist deep optimization analysis artifacts"),
    no_dashboard: bool = typer.Option(False, "--no-dashboard", help="Skip dashboard hint output"),
    ci: bool = typer.Option(False, "--ci", help="CI mode: force JSON output, disable dashboard, and use thresholded exit codes"),
    improvement_threshold: float | None = typer.Option(
        None,
        "--improvement-threshold",
        help="Minimum scalar improvement ratio required for CI success",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable measurement cache"),
    fresh_surrogate: bool = typer.Option(
        False,
        "--fresh-surrogate",
        help="Start without loading persisted surrogate observations",
    ),
    parallel: int | None = typer.Option(None, "--parallel", help="Override max parallel workers"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    _validate_positive(budget, option_name="--budget")
    _validate_positive(parallel, option_name="--parallel")
    _validate_non_negative(improvement_threshold, option_name="--improvement-threshold")
    run_resume(
        path,
        run_id,
        output=output,
        budget=budget,
        analysis=analysis,
        no_dashboard=no_dashboard,
        ci=ci,
        improvement_threshold=improvement_threshold,
        no_cache=no_cache,
        fresh_surrogate=fresh_surrogate,
        parallel=parallel,
        verbose=verbose,
        quiet=quiet,
        bootstrap_fn=_bootstrap,
    )


@config_app.command("show")
def config_show(
    path: Path = typer.Argument(..., help=PATH_HELP),
    output: str = typer.Option("human", "--output", help="Output format: human or json"),
):
    run_config_show(path, output, console=console)


@app.command()
def apply(
    path: Path = typer.Argument(..., help=PATH_HELP),
    run_id: str = typer.Option(..., "--run-id", help="Run identifier to apply"),
    candidate_id: str | None = typer.Option(None, "--candidate-id", help="Specific candidate to apply"),
    branch: bool = typer.Option(False, "--branch", help="Create a joule/<run_id> branch before applying"),
    commit_changes: bool = typer.Option(False, "--commit", help="Commit after applying; requires --branch"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    run_apply(settings, db, reporter, run_id, candidate_id, branch, commit_changes)


@app.command()
def discover(
    path: Path = typer.Argument(..., help=PATH_HELP),
    output: str = typer.Option("json", "--output", help="Output format: human or json"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed discovery events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    run_discover(path, output, verbose, quiet, console=console, bootstrap_fn=_bootstrap)


@app.command()
def dashboard(
    path: Path = typer.Argument(..., help=PATH_HELP),
    host: str = typer.Option("127.0.0.1", "--host", help="Dashboard host"),
    port: int | None = typer.Option(None, "--port", help="Dashboard port"),
    run_id: str | None = typer.Option(None, "--run-id", help="Filter to a specific run"),
    once: bool = typer.Option(False, "--once", help="Print dashboard HTML to stdout and exit"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    run_dashboard(path, host, port, run_id, once, verbose, quiet, bootstrap_fn=_bootstrap)


@app.command()
def inspect(
    path: Path = typer.Argument(..., help=PATH_HELP),
    run_id: str = typer.Option(..., "--run-id", help="Run identifier produced by baseline or run"),
    candidate_id: str | None = typer.Option(None, "--candidate-id", help="Inspect a specific candidate"),
    output: str = typer.Option("json", "--output", help="Output format: human or json"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed inspection events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    run_inspect(path, run_id, candidate_id, output, verbose, quiet, bootstrap_fn=_bootstrap)


@app.command("parse-json")
def parse_json(
    file: Path | None = typer.Option(None, "--file", help="Read JSON payload from file instead of stdin"),
):
    run_parse_json(file, console=console)

if __name__ == "__main__":  # pragma: no cover
    app()
