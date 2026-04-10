from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Literal

import typer
from rich.console import Console

from joule.cli_helpers.flow import ExecutionContext, create_run_record, resolve_target_and_bundle
from joule.config import JouleSettings, load_settings
from joule.dashboard.app import render_dashboard_html, serve_dashboard
from joule.discovery.resolver import discover_targets
from joule.evaluators.oracle import PerformanceOracle
from joule.integrations.git import (
    apply_patch_to_target,
    commit,
    create_branch,
    file_sha256,
    preview_patch,
    stage_files,
)
from joule.models import RunType
from joule.orchestrator.explainer import synthesize_explanation
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.utils.analysis import (
    build_baseline_analysis,
    build_optimization_analysis,
    candidate_detail_payload,
    human_candidate_detail_summary,
    human_discover_summary,
    human_baseline_summary,
    human_inspect_summary,
    human_json_payload_summary,
    human_run_summary,
    json_pretty,
    summarize_inspect_payload,
    summarize_hotspots,
)
from joule.utils.artifacts import ensure_artifacts, seed_random, write_artifact
from joule.utils.db import JouleDB
from joule.utils.reporting import measurement_to_json, workload_provenance_records
from joule.utils.terminal import TerminalReporter

app = typer.Typer(help="JOULE optimization toolkit")
console = Console()

PATH_HELP = "Path to a target .py file or project root with pyproject.toml"


def _validate_positive(value: int | None, *, option_name: str) -> None:
    if value is not None and value < 1:
        raise typer.BadParameter(f"{option_name} must be >= 1")


def _resolve_output_mode(output: str) -> Literal["human", "json"]:
    normalized = output.strip().lower()
    if normalized in {"human", "json"}:
        return normalized  # type: ignore[return-value]
    if normalized == "parsed":
        return "human"
    raise typer.BadParameter("--output must be either 'human' or 'json'")


def _load_json_input(file: Path | None) -> Any:
    raw = file.read_text(encoding="utf-8") if file else sys.stdin.read()
    if not raw.strip():
        raise typer.BadParameter("No JSON payload provided. Pass --file or pipe JSON to stdin.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc.msg} at line {exc.lineno} column {exc.colno}") from exc


def _bootstrap(path: Path, *, verbose: bool = False, quiet: bool = False):
    settings = load_settings(path)
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


def _write_dashboard_snapshot(db: JouleDB, run_dir: Path) -> Path:
    return write_artifact(run_dir, "dashboard.html", render_dashboard_html(db))


def _write_run_summary(
    db: JouleDB,
    run_dir: Path,
    name: str,
    payload: dict,
) -> Path:
    output = write_artifact(run_dir, name, json.dumps(payload, indent=2))
    _write_dashboard_snapshot(db, run_dir)
    return output


def _collect_hotspot_analysis(
    *,
    oracle: PerformanceOracle,
    db: JouleDB,
    run_id: str,
    target,
    bundle,
    run_dir: Path,
    reporter: TerminalReporter,
    enabled: bool,
    limit: int,
) -> dict | None:
    if not enabled:
        return None
    reporter.info("hotspots", "Profiling workloads for hotspot analysis")
    records = oracle.profile_bundle_hotspots(target=target, bundle=bundle)
    created_at = datetime.now(UTC).isoformat()
    for item in records:
        db.record_hotspot_profile(
            run_id=run_id,
            workload_id=item["workload_id"],
            kind="workload",
            payload=item,
            created_at=created_at,
        )
    summary = summarize_hotspots(records, limit=limit)
    db.record_hotspot_profile(
        run_id=run_id,
        workload_id="all",
        kind="summary",
        payload=summary,
        created_at=created_at,
    )
    write_artifact(run_dir, "hotspots.json", json_pretty(summary))
    return summary


def _write_candidate_artifacts(run_dir: Path, candidates: list[dict]) -> None:
    candidates_dir = run_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for item in candidates:
        candidate_dir = candidates_dir / item["candidate_id"]
        candidate_dir.mkdir(parents=True, exist_ok=True)
        write_artifact(candidate_dir, "candidate.json", json_pretty(item))
        write_artifact(candidate_dir, "candidate.py", item["source_code"])


def _artifact_paths_payload(run_dir: Path, names: list[str]) -> dict[str, str]:
    return {name: str(run_dir / name) for name in names if (run_dir / name).exists()}


def _build_execution_context(
    *,
    path: Path,
    function: str,
    tests: list[str] | None,
    properties: list[str] | None,
    harness: str | None,
    backend: str | None,
    run_type: RunType,
    verbose: bool,
    quiet: bool,
) -> ExecutionContext:
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
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
    oracle = PerformanceOracle(settings, backend_name=backend, reporter=reporter)
    orchestrator = OptimizationOrchestrator(settings, db, oracle, reporter=reporter)
    return ExecutionContext(
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
    settings, _db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
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
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    _validate_positive(repetitions, option_name="--repetitions")
    _validate_positive(hotspot_limit, option_name="--hotspot-limit")
    output_mode = _resolve_output_mode(output)
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    context = _build_execution_context(
        path=path,
        function=function,
        tests=tests,
        properties=properties,
        harness=harness,
        backend=backend,
        run_type=RunType.BASELINE,
        verbose=verbose,
        quiet=effective_quiet,
    )
    report = context.orchestrator.baseline(context.run_id, context.target, context.bundle, repetitions=repetitions)
    hotspot_summary = _collect_hotspot_analysis(
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
    _write_dashboard_snapshot(context.db, context.run_dir)
    context.reporter.info("artifacts", f"Run artifacts written to {context.run_dir}")
    if output_mode == "json":
        typer.echo(json_pretty(baseline_analysis))
    else:
        console.print(human_baseline_summary(report, context.bundle.notes, hotspot_summary))
    if not no_dashboard:
        context.reporter.info("dashboard", f"Snapshot written to {context.run_dir / 'dashboard.html'}")


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
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    _validate_positive(budget, option_name="--budget")
    output_mode = _resolve_output_mode(output)
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    context = _build_execution_context(
        path=path,
        function=function,
        tests=tests,
        properties=properties,
        harness=harness,
        backend=backend,
        run_type=RunType.OPTIMIZE,
        verbose=verbose,
        quiet=effective_quiet,
    )
    baseline_report, pareto, best = context.orchestrator.optimize(
        context.run_id,
        context.target,
        context.bundle,
        budget=budget,
        analysis=analysis,
    )
    hotspot_summary = _collect_hotspot_analysis(
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
        _write_candidate_artifacts(context.run_dir, candidates)
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
                "status": item["status"],
                "rejected": item["metadata"].get("rejected"),
                "dependency_policy_state": item["metadata"].get("dependency_policy_state"),
                "improvement_summary": item["metadata"].get("improvement_summary"),
                "explanation_summary": item["metadata"].get("explanation_summary"),
            }
            for item in candidates
        ],
    }
    summary["artifact_paths"] = _artifact_paths_payload(
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
    _write_run_summary(context.db, context.run_dir, "run_summary.json", summary)
    context.reporter.info("artifacts", f"Run artifacts written to {context.run_dir}")
    if output_mode == "json":
        typer.echo(json_pretty(summary))
    else:
        console.print(human_run_summary(summary))
    if not no_dashboard:
        context.reporter.info("dashboard", f"Snapshot written to {context.run_dir / 'dashboard.html'}")


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
    if commit_changes and not branch:
        raise typer.BadParameter("--commit requires --branch")
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    run = db.get_run(run_id)
    candidates = db.get_candidates(run_id)
    if candidate_id:
        selected = next((item for item in candidates if item["candidate_id"] == candidate_id), None)
    else:
        selected = next((item for item in candidates if item["status"] == "accepted"), None)
    if selected is None:
        raise typer.BadParameter(
            f"No accepted candidate available for run {run_id}; use 'joule inspect {path} --run-id {run_id}' to review candidates"
        )
    if selected["dependencies"]:
        dependencies = ", ".join(str(dep) for dep in selected["dependencies"])
        raise typer.BadParameter(
            f"Candidate {selected['candidate_id']} requires new dependencies ({dependencies}) and remains review-only in JOULE v0"
        )
    expected_hash = run.metadata.get("target_file_hash")
    current_hash = file_sha256(run.target.file_path)
    if expected_hash and current_hash != expected_hash:
        raise typer.BadParameter(
            f"Target file changed since measurement (expected {expected_hash[:8]}, current {current_hash[:8]}); refusing to apply"
        )
    if branch:
        branch_name = create_branch(run.target.project_root, run_id)
        reporter.info("git", f"Created branch {branch_name}")
    apply_patch_to_target(run.target, selected["source_code"])
    artifact_paths = [
        run.target.file_path,
        settings.artifact_path / "runs" / run_id / "best.patch",
        settings.artifact_path / "runs" / run_id / "run_summary.json",
        settings.artifact_path / "runs" / run_id / "dashboard.html",
    ]
    existing_paths = [path for path in artifact_paths if path.exists()]
    if branch:
        stage_files(run.target.project_root, existing_paths)
    if commit_changes:
        commit(run.target.project_root, f"Apply JOULE candidate {selected['candidate_id']} for {run.target.qualname}")
        reporter.info("git", f"Committed candidate {selected['candidate_id']}")
    applied_at = datetime.now(UTC).isoformat()
    db.record_apply_audit(
        run_id=run_id,
        candidate_id=selected["candidate_id"],
        applied_at=applied_at,
        metadata={"branch": branch, "commit": commit_changes},
    )
    reporter.info("apply", f"Applied candidate {selected['candidate_id']} to {run.target.file_path}")


@app.command()
def discover(
    path: Path = typer.Argument(..., help=PATH_HELP),
    output: str = typer.Option("json", "--output", help="Output format: human or json"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed discovery events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, _db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    reporter.verbose("discovery", f"Scanning {settings.project_root}")
    results = discover_targets(settings, path)
    payload = [
        {
            "target": result.target.to_record(),
            "score": result.score,
            "reasons": result.reasons,
            "workloads": [workload.to_record() for workload in result.workloads],
            "workload_provenance": [
                {
                    "identifier": workload.identifier,
                    "provenance": workload.metadata.get("provenance", "unknown"),
                    "resolution_strategy": workload.metadata.get("resolution_strategy", "unknown"),
                    "alignment_score": workload.metadata.get("alignment_score"),
                }
                for workload in result.workloads
            ],
        }
        for result in results
    ]
    output_mode = _resolve_output_mode(output)
    if output_mode == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        console.print(human_discover_summary(payload))


@app.command()
def dashboard(
    path: Path = typer.Argument(..., help=PATH_HELP),
    host: str = typer.Option("127.0.0.1", "--host", help="Dashboard host"),
    port: int | None = typer.Option(None, "--port", help="Dashboard port"),
    run_id: str | None = typer.Option(None, "--run-id", help="Specific run to render"),
    once: bool = typer.Option(False, "--once", help="Print HTML instead of serving"),
    verbose: bool = typer.Option(False, "--verbose", help="Print startup details"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    chosen_port = port or settings.dashboard_port
    if once:
        console.print(render_dashboard_html(db, selected_run_id=run_id))
        return
    reporter.info("dashboard", f"Serving dashboard at http://{host}:{chosen_port}")
    serve_dashboard(settings.db_path, host=host, port=chosen_port, selected_run_id=run_id)


@app.command()
def inspect(
    path: Path = typer.Argument(..., help=PATH_HELP),
    run_id: str = typer.Option(..., "--run-id", help="Run identifier produced by baseline or run"),
    candidate_id: str | None = typer.Option(None, "--candidate-id", help="Inspect a specific candidate"),
    output: str = typer.Option("json", "--output", help="Output format: human or json"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed inspection events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    output_mode = _resolve_output_mode(output)
    effective_quiet = quiet or (output_mode == "json" and not verbose)
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=effective_quiet)
    del settings
    reporter.info("inspect", f"Loading run {run_id}")
    record = db.get_run(run_id)
    measurements = db.get_measurements(run_id)
    candidates = db.get_candidates(run_id)
    hotspot_profiles = db.get_hotspot_profiles(run_id)
    search_events = db.get_search_events(run_id)
    payload = {
        "run": {
            "run_id": record.run_id,
            "run_type": record.run_type.value,
            "status": record.status,
            "created_at": record.created_at,
            "target": record.target.to_record(),
            "bundle": record.bundle.to_record(),
            "metadata": record.metadata,
        },
        "workload_provenance": workload_provenance_records(record.bundle),
        "measurements": measurements,
        "candidates": candidates,
        "search_events": search_events,
        "hotspots": hotspot_profiles,
        "artifacts": db.get_artifacts(run_id),
        "apply_audits": db.get_apply_audits(run_id),
    }
    payload["summary"] = summarize_inspect_payload(
        candidates=candidates,
        measurements=measurements,
        search_events=search_events,
        hotspots=hotspot_profiles,
        artifacts=payload["artifacts"],
        apply_audits=payload["apply_audits"],
    )
    if candidate_id:
        selected = next((item for item in candidates if item["candidate_id"] == candidate_id), None)
        if selected is None:
            raise typer.BadParameter(f"Unknown candidate_id {candidate_id!r} for run {run_id}")
        candidate_payload = candidate_detail_payload(selected, measurements)
        if output_mode == "json":
            typer.echo(json_pretty(candidate_payload))
        else:
            console.print(human_candidate_detail_summary(candidate_payload))
        return
    if output_mode == "json":
        typer.echo(json_pretty(payload))
    else:
        console.print(human_inspect_summary(payload))


@app.command("parse-json")
def parse_json(
    file: Path | None = typer.Option(None, "--file", help="Read JSON payload from file instead of stdin"),
):
    payload = _load_json_input(file)
    console.print(human_json_payload_summary(payload))


def _backend_ready(settings: JouleSettings, backend_name: str) -> bool:
    if backend_name == "mock":
        return True
    if backend_name == "rapl":
        rapl_options: dict[str, Any] = settings.backends.options.get("rapl", {}) if settings.backends.options else {}
        rapl_path = Path(rapl_options.get("path", "/sys/class/powercap/intel-rapl:0/energy_uj"))
        return rapl_path.exists()
    return False


if __name__ == "__main__":  # pragma: no cover
    app()
