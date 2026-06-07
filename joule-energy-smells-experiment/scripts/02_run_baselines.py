"""
Phase 2: Run joule baseline on every scaffolded workspace in parallel.

For each snippet:
  ./joule baseline workspaces/<idx>/target.py \
    --function <fn> \
    --tests tests/test_target.py::test_<fn> \
    --output json \
    --no-dashboard

Results are written to results/baselines/<idx>/baseline_status.json.
A master progress file tracks completion for resumability.
"""

import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from experiment_config import (  # noqa: E402
    BASELINE_TIMEOUT_S,
    CHECKPOINT_INTERVAL,
    JOULE_BIN,
    LOGS_DIR,
    MAX_PARALLEL_BASELINES,
    RESULTS_DIR,
    WORKSPACES_DIR,
)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOGS_DIR / "experiment.log")],
)
log = logging.getLogger(__name__)


def _load_progress(progress_path: Path) -> set[int]:
    """Returns set of unique_index values already completed."""
    if not progress_path.exists():
        return set()
    with open(progress_path) as f:
        return set(json.loads(f.read()).get("completed", []))


def _save_progress(progress_path: Path, completed: set[int]) -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(json.dumps({"completed": sorted(completed)}))


def run_baseline(rec: dict) -> dict:
    """Run joule baseline for one snippet. Returns result dict."""
    idx = rec["unique_index"]
    ws = WORKSPACES_DIR / str(idx)
    out_dir = RESULTS_DIR / "baselines" / str(idx)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read actual function name resolved during scaffolding
    meta_path = ws / ".scaffold_meta.json"
    if meta_path.exists():
        fn_name = json.loads(meta_path.read_text()).get("actual_function_name", rec["target_function_name"])
    else:
        fn_name = rec["target_function_name"]

    cmd = [
        JOULE_BIN,
        "baseline",
        str(ws / "target.py"),
        "--function", fn_name,
        "--tests", f"tests/test_target.py::test_{fn_name}",
        "--output", "json",
        "--no-dashboard",
    ]

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=BASELINE_TIMEOUT_S,
        )
        elapsed = time.monotonic() - start
        success = result.returncode == 0
        status = {
            "unique_index": idx,
            "status": "ok" if success else "baseline_failed",
            "returncode": result.returncode,
            "elapsed_s": round(elapsed, 2),
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        status = {
            "unique_index": idx,
            "status": "baseline_timeout",
            "elapsed_s": BASELINE_TIMEOUT_S,
            "stdout": "",
            "stderr": "Timed out",
        }
    except Exception as e:
        status = {
            "unique_index": idx,
            "status": "baseline_error",
            "elapsed_s": 0,
            "error": str(e),
            "stdout": "",
            "stderr": "",
        }

    # Write per-snippet status
    (out_dir / "baseline_status.json").write_text(json.dumps(status, indent=2))
    return status


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    prep_path = RESULTS_DIR / "prep" / "prepared_records.jsonl"
    if not prep_path.exists():
        log.error("Run phase 0 first — %s not found", prep_path)
        sys.exit(1)

    with open(prep_path) as f:
        records = [json.loads(l) for l in f]

    progress_path = RESULTS_DIR / "baselines" / "progress.json"
    completed = _load_progress(progress_path)
    log.info("Loaded progress: %d already done", len(completed))

    pending = [r for r in records if r["unique_index"] not in completed]
    log.info("Running baselines for %d snippets (%d workers)...", len(pending), MAX_PARALLEL_BASELINES)

    results = []
    errors = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BASELINES) as pool:
        futures = {pool.submit(run_baseline, rec): rec for rec in pending}
        for future in as_completed(futures):
            status = future.result()
            idx = status["unique_index"]
            completed.add(idx)
            done += 1

            if status["status"] == "ok":
                results.append(status)
            else:
                errors.append(status)
                log.warning("baseline %s: %s", idx, status["status"])

            if done % CHECKPOINT_INTERVAL == 0:
                _save_progress(progress_path, completed)
                log.info("  checkpoint: %d / %d done, %d errors", done, len(pending), len(errors))

    _save_progress(progress_path, completed)

    # Write error log
    err_path = RESULTS_DIR / "baselines" / "errors.jsonl"
    with open(err_path, "w") as f:
        for e in errors:
            f.write(json.dumps(e) + "\n")

    ok_count = len(results)
    log.info("Baselines complete: %d ok, %d failed", ok_count, len(errors))
    log.info("Success rate: %.1f%%", 100 * ok_count / max(len(pending), 1))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "experiment.log"),
        ],
    )
    main()
