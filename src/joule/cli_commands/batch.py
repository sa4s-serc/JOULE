"""Batch optimization command.

Discovers optimization targets in the project, then runs the full
MFBO optimization loop on each target sequentially, outputting a
summary table of achievements.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from joule.config import load_settings
from joule.cli_helpers.flow import resolve_target_and_bundle, create_run_record
from joule.discovery.resolver import discover_targets
from joule.evaluators.correctness import CorrectnessEngine
from joule.evaluators.oracle import PerformanceOracle
from joule.models import RunType
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.utils.metrics import objective_score


def run_batch(
    path: Path,
    budget: int | None,
    backend: str | None,
    parallel: int | None,
    verbose: bool,
    quiet: bool,
    *,
    console,
    bootstrap_fn,
) -> None:
    from rich.table import Table
    from typer import echo

    settings, db, reporter = bootstrap_fn(path, verbose=verbose, quiet=quiet)
    if parallel is not None:
        settings.max_parallel_workers = parallel

    reporter.info("batch", f"Discovering optimization targets in {settings.project_root}")
    discovered = discover_targets(settings, settings.project_root)
    if not discovered:
        reporter.warn("batch", "No optimization targets discovered.")
        return

    reporter.info("batch", f"Discovered {len(discovered)} target(s). Starting batch optimization.")

    results: list[dict[str, Any]] = []

    for idx, target_result in enumerate(discovered):
        target = target_result.target
        workloads = target_result.workloads
        if not workloads:
            reporter.warn("batch", f"[{idx+1}/{len(discovered)}] Skipping {target.qualname}: no workloads discovered")
            continue

        reporter.info("batch", f"\n==================================================")
        reporter.info("batch", f"[{idx+1}/{len(discovered)}] Optimizing target: {target.qualname}")
        reporter.info("batch", f"==================================================")

        try:
            # Build execution parameters
            chosen_backend = backend or settings.default_backend
            
            # Create unique run record
            record, run_id, run_dir = create_run_record(
                settings=settings,
                db=db,
                run_type=RunType.OPTIMIZE,
                target=target,
                bundle=target_result,  # target_result is a WorkloadBundle (DiscoveryResult subclasses or wraps it)
                chosen_backend=chosen_backend,
            )

            # Build evaluators
            oracle = PerformanceOracle(db=db, backend=record.bundle.backend, max_workers=settings.max_parallel_workers)
            correctness = CorrectnessEngine(max_workers=settings.max_parallel_workers)

            # Setup orchestrator
            orchestrator = OptimizationOrchestrator.create(
                settings=settings,
                db=db,
                oracle=oracle,
                reporter=reporter,
            )

            # Run optimization
            opt_budget = budget or settings.optimization_budget
            baseline_report, pareto, best = orchestrator.optimize(
                run_id=run_id,
                target=target,
                bundle=record.bundle,
                budget=opt_budget,
            )

            bl_agg = baseline_report.aggregate
            best_agg = best.aggregate if best else bl_agg

            energy_saved = bl_agg.mean_energy_j - best_agg.mean_energy_j
            latency_saved = bl_agg.mean_wall_time_s - best_agg.mean_wall_time_s
            energy_pct = (energy_saved / max(1e-9, bl_agg.mean_energy_j)) * 100
            latency_pct = (latency_saved / max(1e-9, bl_agg.mean_wall_time_s)) * 100

            results.append({
                "target": target.qualname,
                "status": "success",
                "run_id": run_id,
                "energy_before": bl_agg.mean_energy_j,
                "energy_after": best_agg.mean_energy_j,
                "energy_improvement_pct": energy_pct,
                "latency_before": bl_agg.mean_wall_time_s,
                "latency_after": best_agg.mean_wall_time_s,
                "latency_improvement_pct": latency_pct,
                "best_candidate": best.candidate_id if best else "baseline",
            })
        except Exception as exc:
            reporter.error("batch", f"Failed optimizing {target.qualname}: {exc}")
            results.append({
                "target": target.qualname,
                "status": "failed",
                "error": str(exc),
            })

    # Print final batch report
    console.print("\n[bold green]Batch Optimization Report[/bold green]")
    table = Table()
    table.add_column("Target", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Energy Saved %")
    table.add_column("Latency Saved %")
    table.add_column("Best Candidate")

    for res in results:
        if res["status"] == "success":
            table.add_row(
                res["target"],
                "[green]success[/green]",
                f"{res['energy_improvement_pct']:.1f}%",
                f"{res['latency_improvement_pct']:.1f}%",
                res["best_candidate"],
            )
        else:
            table.add_row(
                res["target"],
                f"[red]failed[/red]",
                "-",
                "-",
                "-",
            )
    console.print(table)
