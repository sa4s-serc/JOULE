"""Tests for _ownership_bucket in hotspots.py — venv exclusion, path edge cases."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from joule.profiling.hotspots import _ownership_bucket


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    return tmp_path / "myproject"


# ---------------------------------------------------------------------------
# Builtins / frozen modules
# ---------------------------------------------------------------------------

def test_empty_filename_is_builtin(project_root: Path) -> None:
    assert _ownership_bucket("", project_root, None) == "builtin"


def test_tilde_prefix_is_builtin(project_root: Path) -> None:
    assert _ownership_bucket("~/.local/lib/something.py", project_root, None) == "builtin"


def test_frozen_module_is_builtin(project_root: Path) -> None:
    assert _ownership_bucket("<frozen importlib._bootstrap>", project_root, None) == "builtin"


def test_angle_bracket_prefix_is_builtin(project_root: Path) -> None:
    assert _ownership_bucket("<string>", project_root, None) == "builtin"


# ---------------------------------------------------------------------------
# Project source
# ---------------------------------------------------------------------------

def test_project_file_classified_correctly(project_root: Path) -> None:
    f = str(project_root / "src" / "myapp" / "core.py")
    assert _ownership_bucket(f, project_root, None) == "project"


def test_project_subdir_classified_correctly(project_root: Path) -> None:
    f = str(project_root / "src" / "myapp" / "utils" / "helpers.py")
    assert _ownership_bucket(f, project_root, None) == "project"


# ---------------------------------------------------------------------------
# Virtual-env inside project root must NOT be "project"
# ---------------------------------------------------------------------------

def test_venv_inside_project_is_stdlib_or_site(project_root: Path) -> None:
    f = str(project_root / ".venv" / "lib" / "python3.12" / "site-packages" / "requests" / "api.py")
    result = _ownership_bucket(f, project_root, None)
    assert result == "stdlib-or-site", f"Expected stdlib-or-site, got {result}"


def test_venv_named_venv_inside_project(project_root: Path) -> None:
    f = str(project_root / "venv" / "lib" / "python3.12" / "site-packages" / "flask" / "__init__.py")
    result = _ownership_bucket(f, project_root, None)
    assert result == "stdlib-or-site"


def test_site_packages_outside_project(project_root: Path) -> None:
    f = "/usr/lib/python3.12/site-packages/numpy/core.py"
    assert _ownership_bucket(f, project_root, None) == "stdlib-or-site"


def test_stdlib_path_classified_correctly(project_root: Path) -> None:
    f = "/usr/lib/python3.12/os.py"
    assert _ownership_bucket(f, project_root, None) == "stdlib-or-site"


# ---------------------------------------------------------------------------
# Candidate overlay
# ---------------------------------------------------------------------------

def test_overlay_beats_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    overlay_root = tmp_path / "overlay"
    # overlay is NOT inside project_root, but should still win
    f = str(overlay_root / "src" / "myapp" / "core.py")
    assert _ownership_bucket(f, project_root, overlay_root) == "candidate-overlay"


def test_overlay_inside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    overlay_root = tmp_path / "project" / ".joule-overlay"
    f = str(overlay_root / "src" / "myapp" / "core.py")
    assert _ownership_bucket(f, project_root, overlay_root) == "candidate-overlay"


def test_no_overlay_root_does_not_crash(project_root: Path) -> None:
    f = str(project_root / "src" / "core.py")
    assert _ownership_bucket(f, project_root, None) == "project"


# ---------------------------------------------------------------------------
# External (not project, not stdlib, not overlay)
# ---------------------------------------------------------------------------

def test_external_path_classified_correctly(project_root: Path) -> None:
    f = "/opt/custom_lib/mylib.so"
    assert _ownership_bucket(f, project_root, None) == "external"


def test_joule_runtime_is_external(project_root: Path) -> None:
    # joule's own runtime files are outside the user's project root
    f = "/home/user/joule/src/joule/runtime.py"
    result = _ownership_bucket(f, project_root, None)
    # Should be external (not project, not stdlib)
    assert result in ("external", "stdlib-or-site")
