from __future__ import annotations

from pathlib import Path
import json
import platform
import random
import sys

from joule.config import JouleSettings
from joule.models import TargetSpec


def ensure_artifacts(settings: JouleSettings) -> None:
    settings.artifact_path.mkdir(parents=True, exist_ok=True)
    (settings.artifact_path / "runs").mkdir(parents=True, exist_ok=True)
    if not settings.lock_path.exists():
        write_lockfile(settings)


def run_directory(settings: JouleSettings, run_id: str) -> Path:
    path = settings.artifact_path / "runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_artifact(path: Path, name: str, content: str) -> Path:
    output = path / name
    output.write_text(content, encoding="utf-8")
    return output


def seed_random(seed: int) -> None:
    random.seed(seed)


def write_lockfile(
    settings: JouleSettings,
    *,
    run_id: str | None = None,
    target: TargetSpec | None = None,
    backend: str | None = None,
    target_file_hash: str | None = None,
    baseline_source_hash: str | None = None,
) -> Path:
    payload = {
        "seed": settings.seed,
        "run_id": run_id,
        "target": target.to_record() if target else None,
        "backend": backend or settings.default_backend,
        "config": settings.to_record(),
        "target_file_hash": target_file_hash,
        "baseline_source_hash": baseline_source_hash,
        "db_path": str(settings.db_path),
        "python": sys.version,
        "platform": platform.platform(),
    }
    settings.lock_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return settings.lock_path
