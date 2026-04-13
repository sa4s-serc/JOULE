from __future__ import annotations

from joule.cli_helpers.artifacts import (
    collect_hotspot_analysis,
    write_dashboard_snapshot,
)
from joule.cli_helpers.flow import ExecutionContext
from joule.cli_helpers.output import resolve_output_mode
from joule.utils.analysis import (
    build_baseline_analysis,
    human_baseline_summary,
    json_pretty,
)
from joule.utils.reporting import measurement_to_json
from joule.utils.artifacts import write_artifact


def run_baseline(context: ExecutionContext, *, output: str, repetitions: int | None, hotspots: bool, hotspot_limit: int | None, no_dashboard: bool, no_cache: bool = False) -> None:
    from typer import echo

    output_mode = resolve_output_mode(output)
    report = context.orchestrator.baseline(context.run_id, context.target, context.bundle, repetitions=repetitions, use_cache=not no_cache)
    hotspot_summary = collect_hotspot_analysis(
        oracle=context.oracle,
        db=context.db,
        run_id=context.run_id,
        target=context.target,
        bundle=context.bundle,
        run_dir=context.run_dir,
        reporter=context.reporter,
        enabled=hotspots,
        limit=hotspot_limit if hotspot_limit is not None else context.settings.hotspot_limit,
    )
    baseline_analysis = build_baseline_analysis(
        run_id=context.run_id,
        target_qualname=context.target.qualname,
        report=report,
        hotspot_summary=hotspot_summary,
    )
    write_artifact(context.run_dir, "baseline_analysis.json", json_pretty(baseline_analysis))
    metadata = {**context.record.metadata, "aggregate": report.aggregate.to_record(), "hotspots_enabled": hotspots}
    context.db.update_run_status(context.run_id, "completed", metadata=metadata)
    write_artifact(context.run_dir, "baseline.json", measurement_to_json(report))
    write_dashboard_snapshot(context.db, context.run_dir)
    context.reporter.info("artifacts", f"Run artifacts written to {context.run_dir}")
    if output_mode == "json":
        echo(json_pretty(baseline_analysis))
    else:
        context.reporter.console.print(human_baseline_summary(report, context.bundle.notes, hotspot_summary))
    if not no_dashboard:
        context.reporter.info("dashboard", f"Snapshot written to {context.run_dir / 'dashboard.html'}")
