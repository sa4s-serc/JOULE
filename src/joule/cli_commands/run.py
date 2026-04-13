from __future__ import annotations

from joule.cli_helpers.artifacts import (
    artifact_paths_payload,
    collect_hotspot_analysis,
    write_candidate_artifacts,
    write_run_summary,
)
from joule.cli_helpers.flow import ExecutionContext
from joule.cli_helpers.output import resolve_output_mode
from joule.integrations.git import preview_patch
from joule.orchestrator.explainer import synthesize_explanation
from joule.utils.analysis import (
    build_baseline_analysis,
    build_optimization_analysis,
    human_run_summary,
    json_pretty,
)
from joule.utils.artifacts import write_artifact
from joule.utils.reporting import workload_provenance_records


def run_optimize(context: ExecutionContext, *, budget: int | None, analysis: bool, no_dashboard: bool, output: str, resume: str | None = None, no_cache: bool = False) -> None:
    from typer import BadParameter, echo

    output_mode = resolve_output_mode(output)
    if resume and resume != context.run_id:
        raise BadParameter(
            "Use `joule resume --run-id <id>` to continue an existing run."
        )
    baseline_report, pareto, best = context.orchestrator.optimize(
        context.run_id,
        context.target,
        context.bundle,
        budget=budget,
        analysis=analysis,
        resume=resume,
        use_cache=not no_cache,
        checkpoint_path=context.run_dir / "checkpoint.json",
    )
    hotspot_summary = collect_hotspot_analysis(
        oracle=context.oracle,
        db=context.db,
        run_id=context.run_id,
        target=context.target,
        bundle=context.bundle,
        run_dir=context.run_dir,
        reporter=context.reporter,
        enabled=analysis,
        limit=context.settings.hotspot_limit,
    )
    baseline_analysis = build_baseline_analysis(
        run_id=context.run_id,
        target_qualname=context.target.qualname,
        report=baseline_report,
        hotspot_summary=hotspot_summary,
    )
    write_artifact(context.run_dir, "baseline_analysis.json", json_pretty(baseline_analysis))
    metadata = {
        **context.record.metadata,
        "aggregate": baseline_report.aggregate.to_record(),
        "pareto_size": len(pareto.points()),
        "analysis_enabled": analysis,
    }
    best_candidate_payload = None
    if best and best.report:
        diff = preview_patch(context.target, best.source)
        context.db.record_artifact(context.run_id, "best.patch", "diff", diff)
        write_artifact(context.run_dir, "best.patch", diff)
        write_artifact(context.run_dir, "best_candidate.py", best.source)
        best_candidate_payload = {
            "candidate_id": best.candidate_id,
            "operator_name": best.operator_name,
            "operator_tier": best.metadata.get("operator_tier"),
            "operator_tier_descriptor": best.metadata.get("operator_tier_descriptor"),
            "score": best.score,
            "aggregate": best.report.aggregate.to_record(),
            "dependencies": best.dependencies,
            "dependency_policy_state": best.metadata.get("dependency_policy_state"),
            "improvement_summary": best.metadata.get("improvement_summary"),
            "explanation_summary": best.metadata.get("explanation_summary") or synthesize_explanation(baseline_report, best),
        }
        metadata["best_candidate"] = best_candidate_payload
        metadata["patch_path"] = str(context.run_dir / "best.patch")
        context.reporter.info("result", f"Best candidate {best.candidate_id} recorded at {context.run_dir / 'best.patch'}")
    else:
        context.reporter.info("result", "No candidate cleared the promotion thresholds")
    context.db.update_run_status(context.run_id, "completed", metadata=metadata)
    candidates = context.db.get_candidates(context.run_id)
    if analysis:
        write_candidate_artifacts(context.run_dir, candidates)
    search_events = context.db.get_search_events(context.run_id)
    optimization_analysis = build_optimization_analysis(
        run_id=context.run_id,
        target_qualname=context.target.qualname,
        baseline=baseline_report,
        candidates=candidates,
        events=search_events,
        hotspot_summary=hotspot_summary,
    )
    write_artifact(context.run_dir, "optimization_analysis.json", json_pretty(optimization_analysis))
    summary = {
        "run_id": context.run_id,
        "baseline": baseline_report.to_record(),
        "best_candidate": best_candidate_payload,
        "pareto": [point.candidate_id for point in pareto.points()],
        "workload_provenance": workload_provenance_records(context.bundle),
        "analysis": optimization_analysis,
        "candidates": [
            {
                "candidate_id": item["candidate_id"],
                "operator_name": item["operator_name"],
                "operator_tier": item["metadata"].get("operator_tier"),
                "operator_tier_descriptor": item["metadata"].get("operator_tier_descriptor"),
                "status": item["status"],
                "rejected": item["metadata"].get("rejected"),
                "dependency_policy_state": item["metadata"].get("dependency_policy_state"),
                "improvement_summary": item["metadata"].get("improvement_summary"),
                "explanation_summary": item["metadata"].get("explanation_summary"),
            }
            for item in candidates
        ],
    }
    summary["artifact_paths"] = artifact_paths_payload(
        context.run_dir,
        [
            "run_summary.json",
            "optimization_analysis.json",
            "hotspots.json",
            "best.patch",
            "dashboard.html",
            "events.jsonl",
        ],
    )
    write_run_summary(context.db, context.run_dir, "run_summary.json", summary)
    context.reporter.info("artifacts", f"Run artifacts written to {context.run_dir}")
    if output_mode == "json":
        echo(json_pretty(summary))
    else:
        context.reporter.console.print(human_run_summary(summary))
    if not no_dashboard:
        context.reporter.info("dashboard", f"Snapshot written to {context.run_dir / 'dashboard.html'}")
