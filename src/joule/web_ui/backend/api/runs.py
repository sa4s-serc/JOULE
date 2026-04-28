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
from joule.utils.db import JouleDB

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])

# Background thread pool for long-running jobs
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="joule-run")

# In-memory registry of active background runs
_active_runs: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_path(request: Request) -> str:
    return getattr(request.app.state, "project_path", ".")


def _load(project_path: str):
    path = Path(project_path)
    settings = load_settings(path)
    db = JouleDB(settings.db_path)
    return settings, db


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------

@router.get("/runs")
async def list_runs(request: Request, project_path: str | None = None) -> list[dict[str, Any]]:
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        runs = db.list_runs()

        # Enrich each run with target info from the DB
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

            # Check if there's an active background run
            if run_id in _active_runs:
                run_summary["status"] = _active_runs[run_id].get("status", run_summary.get("status"))

            enriched.append(run_summary)
        return enriched
    except Exception as exc:
        logger.warning("Failed to list runs from DB – returning empty: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}
# ---------------------------------------------------------------------------

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

    # Base payload
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

    # Baseline measurements
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

    # Candidates
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

        # Find measurements for this candidate
        for m in measurements:
            if m.get("candidate_id") == c["candidate_id"]:
                agg = m.get("aggregate", {})
                cand["measurements"] = {
                    "energy_j": agg.get("mean_energy_j", 0),
                    "wall_time_s": agg.get("mean_wall_time_s", 0),
                    "cpu_time_s": agg.get("mean_cpu_time_s", 0),
                    "peak_memory_bytes": int(agg.get("mean_peak_memory_bytes", 0)),
                }
                # Compute improvement ratios vs baseline
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

    # Hotspot profiles
    try:
        hotspot_profiles = db.get_hotspot_profiles(run_id)
        if hotspot_profiles:
            # Look for the aggregated profile (schema_version is present)
            agg = next((h["payload"] for h in hotspot_profiles if "schema_version" in h.get("payload", {})), None)
            if not agg:
                agg = hotspot_profiles[-1].get("payload", {})  # fallback
            payload["hotspots"] = agg
    except Exception:
        pass

    return payload


# ---------------------------------------------------------------------------
# POST /api/projects/{project_path}/baseline
# ---------------------------------------------------------------------------

@router.post("/projects/{project_path:path}/baseline")
async def run_baseline_endpoint(project_path: str, config: BaselineConfig, request: Request):
    pp = project_path if project_path != "." else _project_path(request)
    try:
        settings, db = _load(pp)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    run_id = settings.new_run_id()
    _active_runs[run_id] = {"status": "starting", "run_type": "baseline", "started_at": time.time()}

    # Dispatch synchronous CLI logic in a background thread
    _executor.submit(_run_baseline_sync, pp, config, run_id)

    return {
        "run_id": run_id,
        "status": "started",
        "config": config.model_dump(),
    }


def _run_baseline_sync(project_path: str, config: BaselineConfig, run_id: str):
    """Execute baseline in a background thread."""
    from joule.web_ui.backend.api.websocket import manager
    import asyncio

    try:
        _active_runs[run_id]["status"] = "running"
        # Use CLI internals to run the baseline
        from joule.config import load_settings
        from joule.utils.db import JouleDB
        from joule.utils.artifacts import ensure_artifacts, seed_random
        from joule.cli_helpers.flow import resolve_target_and_bundle, create_run_record, JouleContainer, ExecutionContext
        from joule.utils.terminal import TerminalReporter
        from joule.evaluators.oracle import PerformanceOracle
        from joule.orchestrator.mfbo import OptimizationOrchestrator
        from joule.models import RunType
        from rich.console import Console

        from joule.discovery.resolver import discover_targets

        path = Path(project_path)
        settings = load_settings(path)
        db = JouleDB(settings.db_path)
        ensure_artifacts(settings)
        seed_random(settings.seed)
        console = Console(stderr=True, quiet=True)
        reporter = TerminalReporter(console, "quiet")

        # Resolve the actual file_path for the given target qualname
        all_targets = discover_targets(settings, path)
        matched_target = next((t.target for t in all_targets if t.target.qualname == config.target), None)
        if not matched_target:
            raise ValueError(f"Target '{config.target}' not found in project {project_path}")

        target, bundle = resolve_target_and_bundle(
            path=matched_target.file_path,
            function=config.target,
            settings=settings,
            reporter=reporter,
            tests=None,
            properties=None,
            harness=None,
        )
        chosen_backend = config.backend or settings.default_backend

        record, actual_run_id, run_dir = create_run_record(
            settings=settings,
            db=db,
            run_type=RunType.BASELINE,
            target=target,
            bundle=bundle,
            chosen_backend=chosen_backend,
        )
        reporter.set_log_file(run_dir / "events.jsonl")

        oracle = PerformanceOracle.create(settings, backend_name=config.backend, reporter=reporter, db=db)
        orchestrator = OptimizationOrchestrator.create(settings, db, oracle, reporter=reporter)
        container = JouleContainer(
            settings=settings, db=db, reporter=reporter,
            oracle=oracle, orchestrator=orchestrator,
            correctness=orchestrator.correctness,
            registry=orchestrator.registry,
            surrogate=orchestrator.surrogate,
        )
        context = ExecutionContext(
            container=container, settings=settings, db=db, reporter=reporter,
            target=target, bundle=bundle, chosen_backend=chosen_backend,
            run_id=actual_run_id, run_dir=run_dir, record=record,
            oracle=oracle, orchestrator=orchestrator,
        )

        from joule.cli_commands.baseline import run_baseline as _cli_baseline
        _cli_baseline(
            context,
            output="json",
            repetitions=config.repetitions,
            hotspots=config.hotspots,
            hotspot_limit=config.hotspot_limit,
            granular=config.granular_profiling,
            no_dashboard=True,
            no_cache=not config.cache,
        )

        _active_runs[run_id]["status"] = "completed"
        _active_runs[run_id]["actual_run_id"] = actual_run_id

    except Exception as exc:
        logger.exception("Background baseline %s failed", run_id)
        _active_runs[run_id]["status"] = "failed"
        _active_runs[run_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_path}/optimize
# ---------------------------------------------------------------------------

@router.post("/projects/{project_path:path}/optimize")
async def run_optimization_endpoint(project_path: str, config: OptimizationConfig, request: Request):
    pp = project_path if project_path != "." else _project_path(request)
    try:
        settings, db = _load(pp)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    run_id = settings.new_run_id()
    _active_runs[run_id] = {"status": "starting", "run_type": "optimize", "started_at": time.time()}

    _executor.submit(_run_optimize_sync, pp, config, run_id)

    return {
        "run_id": run_id,
        "status": "started",
        "config": config.model_dump(),
    }


def _run_optimize_sync(project_path: str, config: OptimizationConfig, run_id: str):
    """Execute optimisation in a background thread."""
    try:
        _active_runs[run_id]["status"] = "running"
        from joule.config import load_settings
        from joule.utils.db import JouleDB
        from joule.utils.artifacts import ensure_artifacts, seed_random
        from joule.cli_helpers.flow import resolve_target_and_bundle, create_run_record, JouleContainer, ExecutionContext
        from joule.utils.terminal import TerminalReporter
        from joule.evaluators.oracle import PerformanceOracle
        from joule.orchestrator.mfbo import OptimizationOrchestrator
        from joule.models import RunType
        from rich.console import Console

        from joule.discovery.resolver import discover_targets

        path = Path(project_path)
        settings = load_settings(path)
        if config.parallel:
            settings.max_parallel_workers = config.parallel
        db = JouleDB(settings.db_path)
        ensure_artifacts(settings)
        seed_random(settings.seed)
        console = Console(stderr=True, quiet=True)
        reporter = TerminalReporter(console, "quiet")

        # Resolve the actual file_path for the given target qualname
        all_targets = discover_targets(settings, path)
        matched_target = next((t.target for t in all_targets if t.target.qualname == config.target), None)
        if not matched_target:
            raise ValueError(f"Target '{config.target}' not found in project {project_path}")

        target, bundle = resolve_target_and_bundle(
            path=matched_target.file_path,
            function=config.target,
            settings=settings,
            reporter=reporter,
            tests=None,
            properties=None,
            harness=None,
        )
        chosen_backend = config.backend or settings.default_backend

        record, actual_run_id, run_dir = create_run_record(
            settings=settings, db=db,
            run_type=RunType.OPTIMIZE,
            target=target, bundle=bundle,
            chosen_backend=chosen_backend,
        )
        reporter.set_log_file(run_dir / "events.jsonl")

        oracle = PerformanceOracle.create(settings, backend_name=config.backend, reporter=reporter, db=db)
        orchestrator = OptimizationOrchestrator.create(settings, db, oracle, reporter=reporter)
        container = JouleContainer(
            settings=settings, db=db, reporter=reporter,
            oracle=oracle, orchestrator=orchestrator,
            correctness=orchestrator.correctness,
            registry=orchestrator.registry,
            surrogate=orchestrator.surrogate,
        )
        context = ExecutionContext(
            container=container, settings=settings, db=db, reporter=reporter,
            target=target, bundle=bundle, chosen_backend=chosen_backend,
            run_id=actual_run_id, run_dir=run_dir, record=record,
            oracle=oracle, orchestrator=orchestrator,
        )

        from joule.cli_commands.run import run_optimize as _cli_optimize
        _cli_optimize(
            context,
            budget=config.budget,
            analysis=config.analysis,
            no_dashboard=True,
            output="json",
            no_cache=not config.cache,
            ci=False,
            improvement_threshold=config.improvement_threshold,
            fresh_surrogate=config.fresh_surrogate,
        )

        _active_runs[run_id]["status"] = "completed"
        _active_runs[run_id]["actual_run_id"] = actual_run_id

    except Exception as exc:
        logger.exception("Background optimisation %s failed", run_id)
        _active_runs[run_id]["status"] = "failed"
        _active_runs[run_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/apply
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/artifacts
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/artifacts")
async def get_run_artifacts(run_id: str, request: Request, project_path: str | None = None) -> list[dict[str, Any]]:
    pp = project_path or _project_path(request)
    try:
        settings, db = _load(pp)
        path = Path(pp)

        # Check artifact files on disk
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

        # Also include DB-stored artifacts
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


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/artifacts/{artifact_name}
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /api/runs/active  – list background runs
# ---------------------------------------------------------------------------

@router.get("/runs/active")
async def list_active_runs() -> dict[str, Any]:
    return {
        "active_runs": {
            k: {"status": v["status"], "run_type": v.get("run_type"), "error": v.get("error")}
            for k, v in _active_runs.items()
        }
    }
