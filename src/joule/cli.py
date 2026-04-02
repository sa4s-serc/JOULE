from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path

import typer
from rich.console import Console

from joule.config import JouleSettings, load_settings
from joule.dashboard.app import render_dashboard_html, render_dashboard_snapshot, serve_dashboard
from joule.discovery.resolver import discover_targets, resolve_target, resolve_workload_bundle
from joule.evaluators.oracle import PerformanceOracle
from joule.integrations.git import apply_patch_to_target, commit, create_branch, file_sha256, preview_patch, stage_files
from joule.models import RunRecord, RunType
from joule.orchestrator.mfbo import OptimizationOrchestrator
from joule.utils.artifacts import ensure_artifacts, run_directory, seed_random, write_artifact
from joule.utils.db import JouleDB
from joule.utils.reporting import baseline_report_text, measurement_to_json
from joule.utils.terminal import TerminalReporter

app = typer.Typer(help="JOULE optimization toolkit")
console = Console()


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


def _run_metadata(target, settings: JouleSettings) -> dict:
    return {
        "target_file_hash": file_sha256(target.file_path),
        "baseline_source_hash": file_sha256(target.file_path),
        "default_backend": settings.default_backend,
    }


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


@app.command()
def doctor(
    path: Path,
    backend: str | None = typer.Option(None, "--backend", help="Backend to validate"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed checks"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, _db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    chosen_backend = backend or settings.default_backend
    checks = [
        ("python", "ok", console.color_system is not None, "Python interpreter available"),
        ("typer", "ok", importlib.util.find_spec("typer") is not None, "Typer import"),
        ("libcst", "ok", importlib.util.find_spec("libcst") is not None, "LibCST import"),
        ("psutil", "ok", importlib.util.find_spec("psutil") is not None, "psutil import"),
        ("backend", chosen_backend, _backend_ready(settings, chosen_backend), f"Backend {chosen_backend}"),
        ("llm", settings.llm_model or "unset", bool(settings.llm_model), "LLM model configured"),
        ("git", "ok", (settings.project_root / ".git").exists(), "Git repository detected"),
    ]
    reporter.info("doctor", f"Checking project at {settings.project_root}")
    for name, value, ok, label in checks:
        status = "PASS" if ok else "WARN"
        reporter.info("doctor", f"{status} {label}: {value if value else 'missing'}")


@app.command()
def baseline(
    path: Path,
    function: str = typer.Option(..., "--function", help="Target function name"),
    tests: list[str] = typer.Option(None, "--tests", help="Explicit pytest node ids"),
    properties: list[str] = typer.Option(None, "--properties", help="Property callables"),
    harness: str | None = typer.Option(None, "--harness", help="Harness callable"),
    backend: str | None = typer.Option(None, "--backend", help="Energy backend"),
    json_output: bool = typer.Option(False, "--json", help="Print JSON report"),
    repetitions: int | None = typer.Option(None, "--repetitions", help="Override repetition count"),
    no_dashboard: bool = typer.Option(False, "--no-dashboard", help="Skip dashboard hint output"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    reporter.info("setup", f"Project root: {settings.project_root}")
    target = resolve_target(path, function, project_root=settings.project_root)
    reporter.info("target", f"Resolved {target.qualname} at {target.file_path}")
    bundle = resolve_workload_bundle(settings, target, tests=tests, properties=properties, harness=harness)
    reporter.info("workloads", f"Using {len(bundle.workloads)} workload(s)")
    run_id = settings.new_run_id()
    run_dir = run_directory(settings, run_id)
    record = RunRecord(
        run_id=run_id,
        run_type=RunType.BASELINE,
        target=target,
        bundle=bundle,
        status="running",
        created_at=datetime.now(UTC).isoformat(),
        metadata=_run_metadata(target, settings),
    )
    db.create_run(record)
    oracle = PerformanceOracle(settings, backend_name=backend, reporter=reporter)
    orchestrator = OptimizationOrchestrator(settings, db, oracle, reporter=reporter)
    report = orchestrator.baseline(run_id, target, bundle, repetitions=repetitions)
    metadata = {**record.metadata, "aggregate": report.aggregate.to_record()}
    db.update_run_status(run_id, "completed", metadata=metadata)
    write_artifact(run_dir, "baseline.json", measurement_to_json(report))
    _write_dashboard_snapshot(db, run_dir)
    output = measurement_to_json(report) if json_output else baseline_report_text(bundle, report)
    console.print(output)
    if not no_dashboard:
        reporter.info("dashboard", f"Snapshot written to {run_dir / 'dashboard.html'}")


@app.command()
def run(
    path: Path,
    function: str = typer.Option(..., "--function", help="Target function name"),
    tests: list[str] = typer.Option(None, "--tests", help="Explicit pytest node ids"),
    properties: list[str] = typer.Option(None, "--properties", help="Property callables"),
    harness: str | None = typer.Option(None, "--harness", help="Harness callable"),
    backend: str | None = typer.Option(None, "--backend", help="Energy backend"),
    budget: int | None = typer.Option(None, "--budget", help="Candidate budget"),
    no_dashboard: bool = typer.Option(False, "--no-dashboard", help="Skip dashboard hint output"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed optimization events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    reporter.info("setup", f"Project root: {settings.project_root}")
    target = resolve_target(path, function, project_root=settings.project_root)
    reporter.info("target", f"Resolved {target.qualname} at {target.file_path}")
    bundle = resolve_workload_bundle(settings, target, tests=tests, properties=properties, harness=harness)
    reporter.info("workloads", f"Using {len(bundle.workloads)} workload(s)")
    run_id = settings.new_run_id()
    run_dir = run_directory(settings, run_id)
    record = RunRecord(
        run_id=run_id,
        run_type=RunType.OPTIMIZE,
        target=target,
        bundle=bundle,
        status="running",
        created_at=datetime.now(UTC).isoformat(),
        metadata=_run_metadata(target, settings),
    )
    db.create_run(record)
    oracle = PerformanceOracle(settings, backend_name=backend, reporter=reporter)
    orchestrator = OptimizationOrchestrator(settings, db, oracle, reporter=reporter)
    baseline_report, pareto, best = orchestrator.optimize(run_id, target, bundle, budget=budget)
    metadata = {**record.metadata, "aggregate": baseline_report.aggregate.to_record(), "pareto_size": len(pareto.points())}
    best_candidate_payload = None
    if best and best.report:
        diff = preview_patch(target, best.source)
        db.record_artifact(run_id, "best.patch", "diff", diff)
        write_artifact(run_dir, "best.patch", diff)
        write_artifact(run_dir, "best_candidate.py", best.source)
        best_candidate_payload = {
            "candidate_id": best.candidate_id,
            "operator_name": best.operator_name,
            "score": best.score,
            "aggregate": best.report.aggregate.to_record(),
        }
        metadata["best_candidate"] = best_candidate_payload
        metadata["patch_path"] = str(run_dir / "best.patch")
        reporter.info("result", f"Best candidate {best.candidate_id} recorded at {run_dir / 'best.patch'}")
    else:
        reporter.info("result", "No candidate cleared the promotion thresholds")
    db.update_run_status(run_id, "completed", metadata=metadata)
    summary = {
        "run_id": run_id,
        "baseline": baseline_report.to_record(),
        "best_candidate": best.report.to_record() if best and best.report else None,
        "pareto": [point.candidate_id for point in pareto.points()],
    }
    _write_run_summary(db, run_dir, "run_summary.json", summary)
    console.print(json.dumps(summary, indent=2))
    if not no_dashboard:
        reporter.info("dashboard", f"Snapshot written to {run_dir / 'dashboard.html'}")


@app.command()
def apply(
    path: Path,
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
        raise typer.BadParameter(f"No candidate available for run {run_id}")
    expected_hash = run.metadata.get("target_file_hash")
    current_hash = file_sha256(run.target.file_path)
    if expected_hash and current_hash != expected_hash:
        raise typer.BadParameter("Target file changed since the run was measured; refusing to apply")
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
    path: Path,
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed discovery events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, _db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    reporter.info("discovery", f"Scanning {settings.project_root}")
    results = discover_targets(settings, path)
    payload = [
        {
            "target": result.target.to_record(),
            "score": result.score,
            "reasons": result.reasons,
            "workloads": [workload.to_record() for workload in result.workloads],
        }
        for result in results
    ]
    console.print(json.dumps(payload, indent=2))


@app.command()
def dashboard(
    path: Path,
    host: str = typer.Option("127.0.0.1", "--host", help="Dashboard host"),
    port: int | None = typer.Option(None, "--port", help="Dashboard port"),
    once: bool = typer.Option(False, "--once", help="Print HTML instead of serving"),
    verbose: bool = typer.Option(False, "--verbose", help="Print startup details"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    chosen_port = port or settings.dashboard_port
    if once:
        console.print(render_dashboard_html(db))
        return
    reporter.info("dashboard", f"Serving dashboard at http://{host}:{chosen_port}")
    serve_dashboard(settings.db_path, host=host, port=chosen_port)


@app.command()
def inspect(
    path: Path,
    run_id: str,
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed inspection events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
):
    settings, db, reporter = _bootstrap(path, verbose=verbose, quiet=quiet)
    del settings
    reporter.info("inspect", f"Loading run {run_id}")
    record = db.get_run(run_id)
    measurements = db.get_measurements(run_id)
    candidates = db.get_candidates(run_id)
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
        "measurements": measurements,
        "candidates": candidates,
        "artifacts": db.get_artifacts(run_id),
        "apply_audits": db.get_apply_audits(run_id),
    }
    console.print(json.dumps(payload, indent=2))


def _backend_ready(settings: JouleSettings, backend_name: str) -> bool:
    if backend_name == "mock":
        return True
    if backend_name == "rapl":
        rapl_options = settings.backends.options.get("rapl", {}) if settings.backends.options else {}
        rapl_path = Path(rapl_options.get("path", "/sys/class/powercap/intel-rapl:0/energy_uj"))
        return rapl_path.exists()
    return False


if __name__ == "__main__":  # pragma: no cover
    app()
