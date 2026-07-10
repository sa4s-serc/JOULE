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
from joule.metadata import parse_candidate_metadata
from joule.orchestrator.explainer import synthesize_explanation
from joule.utils.analysis import (
    build_baseline_analysis,
    build_optimization_analysis,
    human_run_summary,
    json_pretty,
)
from joule.utils.artifacts import write_artifact
from joule.utils.metrics import objective_score
from joule.utils.reporting import workload_provenance_records
from joule.utils.pareto_chart import build_pareto_summary



def run_optimize(
    context: ExecutionContext,
    *,
    budget: int | None,
    analysis: bool,
    no_dashboard: bool,
    output: str,
    resume: str | None = None,
    no_cache: bool = False,
    ci: bool = False,
    improvement_threshold: float | None = None,
    fresh_surrogate: bool = False,
) -> None:
    from typer import BadParameter, Exit, echo

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
        fresh_surrogate=fresh_surrogate,
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
        granular=context.settings.granular_hotspot_analysis,
    )
    baseline_analysis = build_baseline_analysis(
        run_id=context.run_id,
        target_qualname=context.target.qualname,
        report=baseline_report,
        hotspot_summary=hotspot_summary,
    )
    write_artifact(context.run_dir, "baseline_analysis.json", json_pretty(baseline_analysis))
    baseline_score = objective_score(baseline_report.aggregate, context.settings.pareto_weights)
    best_scalar_improvement = 0.0
    best_regressed_scalar = False
    if best and best.report and baseline_score > 0:
        best_scalar_improvement = (
            baseline_score - objective_score(best.report.aggregate, context.settings.pareto_weights)
        ) / baseline_score
        if best_scalar_improvement <= 0.0:
            best_regressed_scalar = True
            context.reporter.info(
                "result",
                (
                    f"Best frontier candidate {best.candidate_id} did not improve scalar score over baseline; "
                    "skipping patch artifact"
                ),
            )
            best = None
            best_scalar_improvement = 0.0
    metadata = {
        **context.record.metadata,
        "aggregate": baseline_report.aggregate.to_record(),
        "pareto_size": len(pareto.points()),
        "analysis_enabled": analysis,
    }
    best_candidate_payload = None
    if best and best.report:
        best_metadata = parse_candidate_metadata(best.metadata)
        diff = preview_patch(context.target, best.source)
        context.db.record_artifact(context.run_id, "best.patch", "diff", diff)
        write_artifact(context.run_dir, "best.patch", diff)
        write_artifact(context.run_dir, "best_candidate.py", best.source)
        best_candidate_payload = {
            "candidate_id": best.candidate_id,
            "operator_name": best.operator_name,
            "operator_tier": best_metadata.operator_tier,
            "operator_tier_descriptor": best_metadata.operator_tier_descriptor,
            "score": best.score,
            "aggregate": best.report.aggregate.to_record(),
            "dependencies": best.dependencies,
            "dependency_policy_state": best_metadata.dependency_policy_state,
            "improvement_summary": best_metadata.improvement_summary.to_record(),
            "explanation_summary": best_metadata.explanation_summary or synthesize_explanation(baseline_report, best),
        }
        metadata["best_candidate"] = best_candidate_payload
        metadata["patch_path"] = str(context.run_dir / "best.patch")
        context.reporter.info("result", f"Best candidate {best.candidate_id} recorded at {context.run_dir / 'best.patch'}")
    else:
        if best_regressed_scalar:
            context.reporter.info("result", "No candidate improved scalar score over baseline")
        else:
            context.reporter.info("result", "No candidate cleared the promotion thresholds")
    context.db.update_run_status(context.run_id, "completed", metadata=metadata)
    candidates = context.db.get_candidates(context.run_id)
    if analysis:
        write_candidate_artifacts(db=context.db, run_id=context.run_id, run_dir=context.run_dir, candidates=candidates)
    search_events = context.db.get_search_events(context.run_id)
    best_candidate_id: str | None = None
    if best_candidate_payload is not None:
        best_candidate_id = str(best_candidate_payload["candidate_id"])
    optimization_analysis = build_optimization_analysis(
        run_id=context.run_id,
        target_qualname=context.target.qualname,
        baseline=baseline_report,
        candidates=candidates,
        events=search_events,
        hotspot_summary=hotspot_summary,
        best_candidate_id=best_candidate_id,
    )
    write_artifact(context.run_dir, "optimization_analysis.json", json_pretty(optimization_analysis))
    summary_candidates = []
    for item in candidates:
        candidate_metadata = parse_candidate_metadata(item.get("metadata", {}))
        summary_candidates.append(
            {
                "candidate_id": item["candidate_id"],
                "operator_name": item["operator_name"],
                "operator_tier": candidate_metadata.operator_tier,
                "operator_tier_descriptor": candidate_metadata.operator_tier_descriptor,
                "status": item["status"],
                "rejected": candidate_metadata.rejected,
                "dependency_policy_state": candidate_metadata.dependency_policy_state,
                "improvement_summary": candidate_metadata.improvement_summary.to_record(),
                "explanation_summary": candidate_metadata.explanation_summary,
            }
        )

    pareto_points_payload = [
        {
            "candidate_id": point.candidate_id,
            "metrics": point.metrics.to_record(),
            "parent_id": point.parent_id,
            "generation_depth": point.generation_depth,
            "operator_name": point.operator_name,
            "active": point.active,
        }
        for point in pareto.points()
    ]
    summary = {
        "run_id": context.run_id,
        "baseline": baseline_report.to_record(),
        "best_candidate": best_candidate_payload,
        "pareto": [point.candidate_id for point in pareto.points()],
        "pareto_summary": build_pareto_summary(pareto_points_payload, baseline_report.aggregate.to_record()),
        "workload_provenance": workload_provenance_records(context.bundle),
        "analysis": optimization_analysis,
        "candidates": summary_candidates,
    }
    threshold = improvement_threshold if improvement_threshold is not None else context.settings.final_improvement_min
    baseline_failed = baseline_report.aggregate.success_rate < 1.0
    accepted_exists = any(item["status"] == "accepted" for item in candidates)

    ci_exit_code = 0
    if ci:
        if baseline_failed:
            ci_exit_code = 2
        elif (not accepted_exists) or (best_scalar_improvement < threshold):
            ci_exit_code = 1
        summary["ci_result"] = {
            "enabled": True,
            "exit_code": ci_exit_code,
            "improvement_threshold": threshold,
            "best_scalar_improvement": best_scalar_improvement,
            "accepted_candidate": accepted_exists,
            "baseline_success_rate": baseline_report.aggregate.success_rate,
        }

    write_run_summary(context.db, context.run_dir, "run_summary.json", summary)
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
    write_artifact(context.run_dir, "run_summary.json", json_pretty(summary))
    context.reporter.info("artifacts", f"Run artifacts written to {context.run_dir}")
    if output_mode == "json":
        echo(json_pretty(summary))
    else:
        context.reporter.console.print(human_run_summary(summary))
    if not no_dashboard:
        context.reporter.info("dashboard", f"Snapshot written to {context.run_dir / 'dashboard.html'}")
    if ci and ci_exit_code != 0:
        raise Exit(code=ci_exit_code)
