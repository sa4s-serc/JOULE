from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPO_ROOT / "example" / "mock_repo"
TARGET_FILE = EXAMPLE_ROOT / "sample_pkg" / "algos.py"
COMPLEX_TARGET_FILE = EXAMPLE_ROOT / "sample_pkg" / "complex_cases.py"
LAUNCHER = REPO_ROOT / "joule"


def main() -> int:
    artifact_dir = EXAMPLE_ROOT / ".joule"
    lock_path = EXAMPLE_ROOT / ".joule.lock"
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    if lock_path.exists():
        lock_path.unlink()

    run_command(["doctor", str(EXAMPLE_ROOT)])
    baseline_output = run_command(
        [
            "baseline",
            str(TARGET_FILE),
            "--function",
            "membership_total",
            "--tests",
            "tests/test_algos.py::test_membership_total",
            "--hotspots",
            "--no-dashboard",
        ]
    )
    baseline_run_id = extract_run_id(baseline_output)
    run_command(
        [
            "baseline",
            str(COMPLEX_TARGET_FILE),
            "--function",
            "warehouse_balancing_pipeline",
            "--tests",
            "tests/test_complex_cases.py::test_warehouse_balancing_pipeline",
            "--no-dashboard",
        ]
    )
    run_output = run_command(
        [
            "run",
            str(TARGET_FILE),
            "--function",
            "unreferenced_total",
            "--budget",
            "4",
            "--analysis",
            "--no-dashboard",
        ]
    )
    run_id = extract_run_id(run_output)
    run_dir = EXAMPLE_ROOT / ".joule" / "runs" / run_id
    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    candidate_ids = [item["candidate_id"] for item in run_summary["candidates"]]
    if candidate_ids:
        run_command(["inspect", str(EXAMPLE_ROOT), "--run-id", run_id, "--candidate-id", candidate_ids[0]])
    dashboard = run_command(["dashboard", str(EXAMPLE_ROOT), "--run-id", run_id, "--once"])
    baseline_inspect = run_command(["inspect", str(EXAMPLE_ROOT), "--run-id", baseline_run_id])
    if "hotspots" not in baseline_inspect:
        raise SystemExit("Baseline inspect output did not include hotspot data")

    expected = [
        EXAMPLE_ROOT / ".joule.lock",
        run_dir / "baseline_analysis.json",
        run_dir / "optimization_analysis.json",
        run_dir / "hotspots.json",
        run_dir / "run_summary.json",
        run_dir / "dashboard.html",
    ]
    if candidate_ids:
        expected.append(run_dir / "candidates" / candidate_ids[0] / "candidate.json")
    missing = [str(path) for path in expected if not path.exists()]
    if missing:
        raise SystemExit(f"Smoke test missing expected artifacts: {', '.join(missing)}")
    if "JOULE Dashboard" not in dashboard:
        raise SystemExit("Dashboard smoke output did not contain the expected title")

    print("Smoke example completed successfully")
    print(f"Baseline run ID: {baseline_run_id}")
    print(f"Run ID: {run_id}")
    return 0


def run_command(args: list[str]) -> str:
    process = subprocess.run(
        [str(LAUNCHER), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip()
        raise SystemExit(f"Command failed: {' '.join(args)}\n{message}")
    stdout = process.stdout.strip()
    if stdout:
        print(f"$ joule {' '.join(args)}")
        print(stdout)
    return stdout


def extract_run_id(output: str) -> str:
    match = None
    for pattern in (r"Run:\s*([a-f0-9]+)", r'"run_id"\s*:\s*"([^"]+)"'):
        match = re.search(pattern, output)
        if match:
            break
    if not match:
        raise SystemExit(f"Unable to find run_id in output:\n{output}")
    return str(match.group(1))


if __name__ == "__main__":
    raise SystemExit(main())
