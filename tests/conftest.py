from __future__ import annotations

from pathlib import Path
import shutil

import pytest

collect_ignore_glob = ["fixtures/*"]


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "sample_project"
    destination = tmp_path / "sample_project"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".joule", ".joule.lock", "__pycache__", ".pytest_cache"),
    )
    return destination
