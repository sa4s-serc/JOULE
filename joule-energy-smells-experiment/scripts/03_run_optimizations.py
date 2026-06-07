"""
Phase 3: Run joule optimization on every snippet that passed baseline.

For each snippet:
  ./joule run workspaces/<idx>/target.py \
    --function <fn> \
    --tests tests/test_target.py::test_<fn> \
    --budget 8 \
    --analysis \
    --ci \
    --no-dashboard \
    --output json

Results are written to results/optimizations/<idx>/run_status.json.
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
    CHECKPOINT_INTERVAL,
    JOULE_BIN,
    LOGS_DIR,
    MAX_PARALLEL_OPTIMIZATIONS,
    OPTIMIZATION_BUDGET,
    OPTIMIZATION_TIMEOUT_S,
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


def _load_progress(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()).get("completed", []))


def _save_progress(path: Path, completed: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"completed": sorted(completed)}))


def _baseline_succeeded(idx: int) -> bool:
    status_file = RESULTS_DIR / "baselines" / str(idx) / "baseline_status.json"
    if not status_file.exists():
        return False
    return json.loads(status_file.read_text()).get("status") == "ok"


def run_optimization(rec: dict) -> dict:
    idx = rec["unique_index"]
    ws = WORKSPACES_DIR / str(idx)
    out_dir = RESULTS_DIR / "optimizations" / str(idx)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read actual function name resolved during scaffolding
    meta_path = ws / ".scaffold_meta.json"
    if meta_path.exists():
        fn_name = json.loads(meta_path.read_text()).get("actual_function_name", rec["target_function_name"])
    else:
        fn_name = rec["target_function_name"]

    cmd = [
        JOULE_BIN,
        "run",
        str(ws / "target.py"),
        "--function", fn_name,
        "--tests", f"tests/test_target.py::test_{fn_name}",
        "--budget", str(OPTIMIZATION_BUDGET),
        "--analysis",
        "--ci",
        "--no-dashboard",
        "--output", "json",
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=OPTIMIZATION_TIMEOUT_S,
        )
        elapsed = time.monotonic() - start

        # joule --ci exits 0 = improved, 1 = no improvement, 2+ = error
        rc = proc.returncode
        if rc == 0:
            outcome = "improved"
        elif rc == 1:
            outcome = "no_improvement"
        else:
            outcome = "run_failed"

        # Try to parse JSON output for richer data
        parsed_output: dict = {}
        try:
            parsed_output = json.loads(proc.stdout)
        except Exception:
            pass

        status = {
            "unique_index": idx,
            "status": outcome,
            "returncode": rc,
            "elapsed_s": round(elapsed, 2),
            "joule_output": parsed_output,
            "stderr": proc.stderr[-500:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        status = {
            "unique_index": idx,
            "status": "optimization_timeout",
            "elapsed_s": OPTIMIZATION_TIMEOUT_S,
            "joule_output": {},
            "stderr": "Timed out",
        }
    except Exception as e:
        status = {
            "unique_index": idx,
            "status": "optimization_error",
            "elapsed_s": 0,
            "error": str(e),
            "joule_output": {},
            "stderr": "",
        }

    (out_dir / "run_status.json").write_text(json.dumps(status, indent=2))
    return status


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    prep_path = RESULTS_DIR / "prep" / "prepared_records.jsonl"
    if not prep_path.exists():
        log.error("Run phase 0 first")
        sys.exit(1)

    with open(prep_path) as f:
        records = [json.loads(l) for l in f]

    # Only process snippets where baseline succeeded
    eligible = [r for r in records if _baseline_succeeded(r["unique_index"])]
    log.info("%d snippets eligible (baseline passed)", len(eligible))

    progress_path = RESULTS_DIR / "optimizations" / "progress.json"
    completed = _load_progress(progress_path)
    pending = [r for r in eligible if r["unique_index"] not in completed]
    log.info("Running optimizations for %d snippets (%d workers)...", len(pending), MAX_PARALLEL_OPTIMIZATIONS)

    improved = skipped = failed = 0
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_OPTIMIZATIONS) as pool:
        futures = {pool.submit(run_optimization, rec): rec for rec in pending}
        for future in as_completed(futures):
            status = future.result()
            idx = status["unique_index"]
            completed.add(idx)
            done += 1

            s = status["status"]
            if s == "improved":
                improved += 1
            elif s == "no_improvement":
                skipped += 1
            else:
                failed += 1
                log.warning("optimization %s: %s", idx, s)

            if done % CHECKPOINT_INTERVAL == 0:
                _save_progress(progress_path, completed)
                log.info(
                    "  checkpoint %d/%d | improved=%d no_improvement=%d failed=%d",
                    done, len(pending), improved, skipped, failed,
                )

    _save_progress(progress_path, completed)

    total = improved + skipped + failed
    log.info(
        "Optimizations complete: %d improved (%.1f%%), %d no_improvement, %d failed",
        improved,
        100 * improved / max(total, 1),
        skipped,
        failed,
    )


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
