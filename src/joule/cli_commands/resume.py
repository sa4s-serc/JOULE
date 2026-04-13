from __future__ import annotations

from pathlib import Path

from typer import BadParameter

from joule.cli_commands.run import run_optimize
from joule.cli_helpers.flow import ExecutionContext, JouleContainer
from joule.models import RunType
from joule.evaluators.oracle import PerformanceOracle
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.utils.artifacts import run_directory


def run_resume(
    path: Path,
    run_id: str,
    *,
    output: str,
    budget: int | None,
    analysis: bool,
    no_dashboard: bool,
    no_cache: bool,
    parallel: int | None,
    verbose: bool,
    quiet: bool,
    bootstrap_fn,
) -> None:
    output_mode = output.strip().lower()
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    settings, db, reporter = bootstrap_fn(path, verbose=verbose, quiet=effective_quiet)

    if parallel is not None:
        settings.max_parallel_workers = parallel

    record = db.get_run(run_id)
    if record.run_type is not RunType.OPTIMIZE:
        raise BadParameter(f"Run {run_id} is {record.run_type.value}, only optimize runs can be resumed")

    chosen_backend = str(record.metadata.get("selected_backend", settings.default_backend))
    run_dir = run_directory(settings, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    reporter.set_log_file(run_dir / "events.jsonl")
    reporter.info("resume", f"Resuming optimize run {run_id}")

    oracle = PerformanceOracle.create(settings, backend_name=chosen_backend, reporter=reporter, db=db)
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

    context = ExecutionContext(
        container=container,
        settings=settings,
        db=db,
        reporter=reporter,
        target=record.target,
        bundle=record.bundle,
        chosen_backend=chosen_backend,
        run_id=run_id,
        run_dir=run_dir,
        record=record,
        oracle=oracle,
        orchestrator=orchestrator,
    )
    db.update_run_status(run_id, "running", metadata=record.metadata)

    run_optimize(
        context,
        budget=budget,
        analysis=analysis,
        no_dashboard=no_dashboard,
        output=output,
        resume=run_id,
        no_cache=no_cache,
    )
