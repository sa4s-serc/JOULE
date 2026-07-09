"""Run execution, listing, inspection, and apply API routes.

Baseline and optimisation jobs are dispatched in background threads via
``concurrent.futures.ThreadPoolExecutor`` so the async API server stays
responsive.  Real-time progress is pushed over the WebSocket channel.
"""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from joule.config import load_settings
from joule.models import RunType
from joule.utils.db import JouleDB

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="joule-run")
_active_runs: dict[str, dict[str, Any]] = {}

class BaselineConfig(BaseModel):
    target: str
    workloads: list[str] = []
    backend: str = "mock"
    repetitions: int = 5
    hotspots: bool = True
    hotspot_limit: int = 12
    granular_profiling: bool = False
    memory_profiling: bool = False
    cache: bool = True


class OptimizationConfig(BaseModel):
    target: str
    workloads: list[str] = []
    backend: str = "mock"
    budget: int = 6
    analysis: bool = True
    cache: bool = True
    fresh_surrogate: bool = False
    parallel: int = 1
    improvement_threshold: float = 0.05


class ApplyConfig(BaseModel):
    run_id: str
    candidate_id: str | None = None
    branch: bool = False
    commit_changes: bool = False

def _project_path(request: Request) -> str:
    return getattr(request.app.state, "project_path", ".")


def _load(project_path: str):
    path = Path(project_path)
    settings = load_settings(path)
    db = JouleDB(settings.db_path)
    return settings, db


def _resolve_target_bundle(
    *,
    project_path: str,
    settings,
    reporter,
    target_qualname: str,
):
    from joule.cli_helpers.flow import resolve_target_and_bundle
    from joule.discovery.resolver import discover_targets

    path = Path(project_path)
    all_targets = discover_targets(settings, path)
    matched_target = next((t.target for t in all_targets if t.target.qualname == target_qualname), None)
    if not matched_target:
        raise ValueError(f"Target '{target_qualname}' not found in project {project_path}")

    return resolve_target_and_bundle(
        path=matched_target.file_path,
        function=target_qualname,
        settings=settings,
        reporter=reporter,
        tests=None,
        properties=None,
        harness=None,
    )


def _prepare_execution(
    *,
    project_path: str,
    settings,
    db: JouleDB,
    target_qualname: str,
    chosen_backend: str,
    run_type,
):
    from joule.cli_helpers.flow import JouleContainer, ExecutionContext, create_run_record
    from joule.evaluators.oracle import PerformanceOracle
    from joule.orchestrator.mfbo import OptimizationOrchestrator
    from joule.utils.artifacts import ensure_artifacts, seed_random
    from joule.utils.terminal import TerminalReporter
    from rich.console import Console

    ensure_artifacts(settings)
    seed_random(settings.seed)
    reporter = TerminalReporter(Console(stderr=True, quiet=True), "quiet")
    target, bundle = _resolve_target_bundle(
        project_path=project_path,
        settings=settings,
        reporter=reporter,
        target_qualname=target_qualname,
    )
    record, actual_run_id, run_dir = create_run_record(
        settings=settings,
        db=db,
        run_type=run_type,
        target=target,
        bundle=bundle,
        chosen_backend=chosen_backend,
    )
    reporter.set_log_file(run_dir / "events.jsonl")

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
        target=target,
        bundle=bundle,
        chosen_backend=chosen_backend,
        run_id=actual_run_id,
        run_dir=run_dir,
        record=record,
        oracle=oracle,
        orchestrator=orchestrator,
    )
    return settings, db, reporter, context, actual_run_id


def _run_job_sync(
    *,
    project_path: str,
    config,
    run_id: str,
    run_type,
    cli_runner,
    cli_kwargs: dict[str, Any],
) -> None:
    try:
        _active_runs[run_id]["status"] = "running"
        settings, db = _load(project_path)
        parallel = getattr(config, "parallel", None)
        if parallel:
            settings.max_parallel_workers = parallel
        chosen_backend = config.backend or settings.default_backend
        settings, db, reporter, context, actual_run_id = _prepare_execution(
            project_path=project_path,
            settings=settings,
            db=db,
            target_qualname=config.target,
            chosen_backend=chosen_backend,
            run_type=run_type,
        )
        cli_runner(context, **cli_kwargs)
        _active_runs[run_id]["status"] = "completed"
        _active_runs[run_id]["actual_run_id"] = actual_run_id
    except Exception as exc:
        logger.exception("Background %s %s failed", run_type.value, run_id)
        _active_runs[run_id]["status"] = "failed"
        _active_runs[run_id]["error"] = str(exc)

@router.get("/runs")
async def list_runs(request: Request, project_path: str | None = None) -> list[dict[str, Any]]:
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        runs = db.list_runs()

        enriched: list[dict[str, Any]] = []
        for run_summary in runs:
            run_id = run_summary["run_id"]
            try:
                record = db.get_run(run_id)
                run_summary["target_qualname"] = record.target.qualname
                run_summary["backend"] = record.metadata.get("backend", settings.default_backend)
            except Exception:
                run_summary.setdefault("target_qualname", "unknown")
                run_summary.setdefault("backend", "unknown")

            if run_id in _active_runs:
                run_summary["status"] = _active_runs[run_id].get("status", run_summary.get("status"))

            enriched.append(run_summary)
        return enriched
    except Exception as exc:
        logger.warning("Failed to list runs from DB – returning empty: %s", exc)
        return []

@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request, project_path: str | None = None) -> dict[str, Any]:
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        record = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    payload: dict[str, Any] = {
        "run_id": record.run_id,
        "run_type": record.run_type.value,
        "status": record.status,
        "target_qualname": record.target.qualname,
        "backend": record.metadata.get("backend", settings.default_backend),
        "created_at": record.created_at,
        "completed_at": record.metadata.get("completed_at"),
        "metadata": record.metadata,
    }

    measurements = db.get_measurements(run_id)
    baseline_measurement = None
    for m in measurements:
        if m.get("candidate_id") is None:
            baseline_measurement = m
            break

    if baseline_measurement:
        agg = baseline_measurement.get("aggregate", {})
        payload["baseline"] = {
            "energy_j": agg.get("mean_energy_j", 0),
            "wall_time_s": agg.get("mean_wall_time_s", 0),
            "cpu_time_s": agg.get("mean_cpu_time_s", 0),
            "peak_memory_bytes": int(agg.get("mean_peak_memory_bytes", 0)),
        }

    db_candidates = db.get_candidates(run_id)
    candidates_payload: list[dict[str, Any]] = []
    for c in db_candidates:
        cand: dict[str, Any] = {
            "candidate_id": c["candidate_id"],
            "operator_name": c["operator_name"],
            "operator_tier": c["metadata"].get("operator_tier", "unknown"),
            "status": c["status"],
            "explanation": c["reasoning"],
        }

        for m in measurements:
            if m.get("candidate_id") == c["candidate_id"]:
                agg = m.get("aggregate", {})
                cand["measurements"] = {
                    "energy_j": agg.get("mean_energy_j", 0),
                    "wall_time_s": agg.get("mean_wall_time_s", 0),
                    "cpu_time_s": agg.get("mean_cpu_time_s", 0),
                    "peak_memory_bytes": int(agg.get("mean_peak_memory_bytes", 0)),
                }
                if baseline_measurement:
                    bl = baseline_measurement.get("aggregate", {})
                    bl_e = bl.get("mean_energy_j", 1) or 1
                    bl_t = bl.get("mean_wall_time_s", 1) or 1
                    bl_m = bl.get("mean_peak_memory_bytes", 1) or 1
                    cand["improvements"] = {
                        "energy_ratio": agg.get("mean_energy_j", bl_e) / bl_e,
                        "time_ratio": agg.get("mean_wall_time_s", bl_t) / bl_t,
                        "memory_ratio": agg.get("mean_peak_memory_bytes", bl_m) / bl_m,
                    }
                break

        if c["status"] in ("rejected", "dominated"):
            cand["rejection_reason"] = c["metadata"].get("rejection_reason", c["reasoning"])

        candidates_payload.append(cand)

    payload["candidates"] = candidates_payload

    try:
        hotspot_profiles = db.get_hotspot_profiles(run_id)
        if hotspot_profiles:
            agg = next((h["payload"] for h in hotspot_profiles if "schema_version" in h.get("payload", {})), None)
            if not agg:
                agg = hotspot_profiles[-1].get("payload", {})
            payload["hotspots"] = agg
    except Exception:
        pass

    return payload

@router.post("/projects/{project_path:path}/baseline")
async def run_baseline_endpoint(project_path: str, config: BaselineConfig, request: Request):
    pp = project_path if project_path != "." else _project_path(request)
    try:
        settings, _ = _load(pp)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    run_id = settings.new_run_id()
    _active_runs[run_id] = {"status": "starting", "run_type": "baseline", "started_at": time.time()}
    from joule.cli_commands.baseline import run_baseline as _cli_baseline

    _executor.submit(
        _run_job_sync,
        project_path=pp,
        config=config,
        run_id=run_id,
        run_type=RunType.BASELINE,
        cli_runner=_cli_baseline,
        cli_kwargs={
            "output": "json",
            "repetitions": config.repetitions,
            "hotspots": config.hotspots,
            "hotspot_limit": config.hotspot_limit,
            "granular": config.granular_profiling,
            "no_dashboard": True,
            "no_cache": not config.cache,
        },
    )

    return {
        "run_id": run_id,
        "status": "started",
        "config": config.model_dump(),
    }


@router.post("/projects/{project_path:path}/optimize")
async def run_optimization_endpoint(project_path: str, config: OptimizationConfig, request: Request):
    pp = project_path if project_path != "." else _project_path(request)
    try:
        settings, _ = _load(pp)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    run_id = settings.new_run_id()
    _active_runs[run_id] = {"status": "starting", "run_type": "optimize", "started_at": time.time()}
    from joule.cli_commands.run import run_optimize as _cli_optimize

    _executor.submit(
        _run_job_sync,
        project_path=pp,
        config=config,
        run_id=run_id,
        run_type=RunType.OPTIMIZE,
        cli_runner=_cli_optimize,
        cli_kwargs={
            "budget": config.budget,
            "analysis": config.analysis,
            "no_dashboard": True,
            "output": "json",
            "no_cache": not config.cache,
            "ci": False,
            "improvement_threshold": config.improvement_threshold,
            "fresh_surrogate": config.fresh_surrogate,
        },
    )

    return {
        "run_id": run_id,
        "status": "started",
        "config": config.model_dump(),
    }

@router.post("/runs/{run_id}/apply")
async def apply_candidate_endpoint(run_id: str, config: ApplyConfig, request: Request, project_path: str | None = None):
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        from joule.cli_commands.apply import run_apply as _cli_apply
        from joule.utils.terminal import TerminalReporter
        from rich.console import Console

        console = Console(stderr=True, quiet=True)
        reporter = TerminalReporter(console, "quiet")

        _cli_apply(
            settings, db, reporter,
            run_id=run_id,
            candidate_id=config.candidate_id,
            branch=config.branch,
            commit_changes=config.commit_changes,
        )

        return {
            "status": "applied",
            "run_id": run_id,
            "candidate_id": config.candidate_id,
            "branch_created": config.branch,
            "commit_created": config.commit_changes,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Apply failed: {exc}")

@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str, request: Request, project_path: str | None = None) -> list[dict[str, Any]]:
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        path = Path(pp)

        run_dir = path / settings.artifact_dir / "runs" / run_id
        artifacts: list[dict[str, Any]] = []
        if run_dir.exists():
            for f in sorted(run_dir.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(run_dir)
                    artifacts.append({
                        "name": str(rel),
                        "path": str(f),
                        "size": f.stat().st_size,
                        "created_at": datetime.fromtimestamp(f.stat().st_ctime, tz=UTC).isoformat(),
                    })

        try:
            db_artifacts = db.get_artifacts(run_id)
            for a in db_artifacts:
                artifacts.append({
                    "name": a["name"],
                    "kind": a["kind"],
                    "size": len(a.get("payload", "")),
                    "created_at": None,
                })
        except Exception:
            pass

        return artifacts
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/runs/{run_id}/artifacts/{artifact_name:path}")
async def download_artifact(run_id: str, artifact_name: str, request: Request, project_path: str | None = None):
    pp = project_path or _project_path(request)
    from fastapi.responses import FileResponse

    try:
        settings = load_settings(Path(pp))
        artifact_path = Path(pp) / settings.artifact_dir / "runs" / run_id / artifact_name
        if not artifact_path.exists():
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_name} not found")
        return FileResponse(str(artifact_path))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/runs/active")
async def list_active_runs() -> dict[str, Any]:
    return {
        "active_runs": {
            k: {"status": v["status"], "run_type": v.get("run_type"), "error": v.get("error")}
            for k, v in _active_runs.items()
        }
    }
