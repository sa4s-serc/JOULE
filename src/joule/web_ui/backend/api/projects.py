from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from joule.config import load_settings
from joule.utils.db import JouleDB

router = APIRouter(tags=["projects"])


def _project_path(request: Request) -> str:
    return getattr(request.app.state, "project_path", ".")


def _load(project_path: str):
    path = Path(project_path)
    settings = load_settings(path)
    try:
        db = JouleDB(settings.db_path)
    except Exception:
        db = None
    return settings, db


@router.get("/projects")
async def list_projects(request: Request) -> list[dict[str, Any]]:
    pp = _project_path(request)
    try:
        info = await _get_project_info(pp)
        return [info]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


async def _get_project_info(project_path: str) -> dict[str, Any]:
    path = Path(project_path)
    try:
        settings = load_settings(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load project: {exc}")

    health = await _get_project_health(project_path, settings)
    config_record = settings.to_record()

    return {
        "path": str(path.resolve()),
        "name": path.resolve().name,
        "config": config_record,
        "health": health,
    }


@router.post("/projects/{project_path:path}/doctor")
async def run_project_doctor(project_path: str) -> dict[str, Any]:
    settings, _ = _load(project_path)
    health = await _get_project_health(project_path, settings)
    return {"status": "success" if not health["issues"] else "issues", "checks": health}


@router.get("/projects/{project_path:path}/discover/targets")
async def discover_targets(project_path: str) -> list[dict[str, Any]]:
    try:
        from joule.discovery.resolver import discover_targets as _discover

        settings = load_settings(Path(project_path))
        results = _discover(settings, Path(project_path))

        payload: list[dict[str, Any]] = []
        for result in results:
            t = result.target
            fn_type = "function"
            if t.is_async and t.owner_path:
                fn_type = "async_method"
            elif t.is_async:
                fn_type = "async_function"
            elif t.owner_path:
                fn_type = "method"

            payload.append({
                "qualname": t.qualname,
                "file_path": str(t.file_path),
                "line_number": t.line_start,
                "function_type": fn_type,
                "score": result.score,
                "reasons": result.reasons,
                "workloads": [
                    {
                        "id": w.identifier,
                        "kind": w.kind.value,
                        "description": w.label,
                        "file_path": w.metadata.get("file_path"),
                        "node_id": w.selector,
                    }
                    for w in result.workloads
                ],
            })
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Target discovery failed: {exc}")


@router.get("/projects/{project_path:path}/discover/workloads/{target_qualname}")
async def discover_workloads(project_path: str, target_qualname: str) -> list[dict[str, Any]]:
    try:
        from joule.discovery.resolver import discover_targets as _discover

        settings = load_settings(Path(project_path))
        results = _discover(settings, Path(project_path))
        for result in results:
            if result.target.qualname == target_qualname:
                return [
                    {
                        "id": w.identifier,
                        "kind": w.kind.value,
                        "description": w.label,
                        "file_path": w.metadata.get("file_path"),
                        "node_id": w.selector,
                    }
                    for w in result.workloads
                ]
        return []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workload discovery failed: {exc}")


async def _get_project_health(project_path: str, settings=None) -> dict[str, Any]:
    path = Path(project_path)
    if settings is None:
        try:
            settings = load_settings(path)
        except Exception as exc:
            return {
                "backend_available": False,
                "backend_name": "unknown",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "dependencies_ok": False,
                "artifact_dir_exists": False,
                "db_accessible": False,
                "issues": [f"Settings error: {exc}"],
            }

    issues: list[str] = []

    artifact_dir = path / settings.artifact_dir
    artifact_dir_exists = artifact_dir.exists()
    if not artifact_dir_exists:
        issues.append(f"Artifact directory {artifact_dir} does not exist yet (run a baseline first)")

    db_accessible = False
    try:
        db = JouleDB(settings.db_path)
        db.list_runs()
        db_accessible = True
    except Exception as exc:
        issues.append(f"Database: {exc}")

    return {
        "backend_available": True,
        "backend_name": settings.default_backend,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "dependencies_ok": True,
        "artifact_dir_exists": artifact_dir_exists,
        "db_accessible": db_accessible,
        "issues": issues,
    }
@router.get("/projects/{project_path:path}")
async def get_project(project_path: str) -> dict[str, Any]:
    return await _get_project_info(project_path)
