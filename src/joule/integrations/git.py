from __future__ import annotations

from pathlib import Path
import difflib
import hashlib
import subprocess

from joule.integrations.libcst_tools import replace_function_in_module
from joule.models import TargetSpec


def preview_patch(target: TargetSpec, candidate_source: str) -> str:
    original = target.file_path.read_text(encoding="utf-8")
    updated = replace_function_in_module(original, target.function_name, candidate_source)
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=str(target.file_path),
            tofile=str(target.file_path),
        )
    )


def apply_patch_to_target(target: TargetSpec, candidate_source: str) -> None:
    original = target.file_path.read_text(encoding="utf-8")
    updated = replace_function_in_module(original, target.function_name, candidate_source)
    target.file_path.write_text(updated, encoding="utf-8")


def create_branch(project_root: Path, run_id: str) -> str:
    branch = f"joule/{run_id}"
    subprocess.run(["git", "checkout", "-b", branch], cwd=project_root, check=True)
    return branch


def stage_files(project_root: Path, paths: list[Path]) -> None:
    if not paths:
        return
    subprocess.run(["git", "add", *[str(path) for path in paths]], cwd=project_root, check=True)


def commit(project_root: Path, message: str) -> None:
    subprocess.run(["git", "commit", "-m", message], cwd=project_root, check=True)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
