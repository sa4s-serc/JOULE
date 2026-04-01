#!/usr/bin/env python3
"""
Run Spectra on prepared BigCodeBench tasks.

Requires tasks to be prepared first:
    python scripts/prepare_bigcodebench.py

Output directory structure:
  bigcodebench_spectra_YYYYMMDD_HHMMSS/
    runs/<BigCodeBench_N>/
      command.txt
      run.log
      artifacts/<func_name>/          ← Spectra output (JSON, CSV, figures)
    summaries/
      run_summary.csv
      run_summary.json

Usage:
  # All prepared tasks, budget=20 per task:
  python scripts/run_spectra_bigcodebench.py

  # Custom budget, no LLM:
  python scripts/run_spectra_bigcodebench.py --budget 30 --no-llm

  # Specific tasks only:
  python scripts/run_spectra_bigcodebench.py --task-ids BigCodeBench/4 BigCodeBench/21

  # Dry-run (print commands only):
  python scripts/run_spectra_bigcodebench.py --dry-run --max-tasks 5

  # Resume a previous run:
  python scripts/run_spectra_bigcodebench.py --out-root bigcodebench_spectra_20260319_123456 --resume

Prerequisites:
  RAPL permissions (for energy measurement):
    sudo chmod a+r /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
    sudo chmod a+r /sys/class/powercap/intel-rapl/intel-rapl:0/intel-rapl:0:*/energy_uj
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_dotenv(repo_root: Path) -> dict[str, str]:
    """
    Parse KEY=value lines from .env in repo_root and return as a dict.
    Handles quoted values and comment lines. Does NOT modify os.environ.
    """
    env_path = repo_root / ".env"
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            result[key] = val
    return result


# ── Utilities ────────────────────────────────────────────────────────────────

def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sort_key(name: str) -> tuple[int, str]:
    """Sort BigCodeBench_N directories numerically."""
    import re
    m = re.search(r"_(\d+)$", name)
    return (int(m.group(1)), name) if m else (10**9, name)


def discover_tasks(tasks_dir: Path, task_ids: list[str] | None = None) -> list[Path]:
    """Return sorted list of prepared task directories."""
    dirs = [
        d for d in tasks_dir.iterdir()
        if d.is_dir()
        and (d / "target.py").exists()
        and (d / "test_target.py").exists()
    ]
    dirs.sort(key=lambda p: _sort_key(p.name))
    if task_ids:
        wanted = {tid.replace("/", "_") for tid in task_ids}
        dirs = [d for d in dirs if d.name in wanted]
    return dirs


def read_func_name(task_dir: Path) -> str:
    """Read entry point from metadata.json, or detect from target.py."""
    meta = task_dir / "metadata.json"
    if meta.exists():
        try:
            ep = json.loads(meta.read_text()).get("entry_point")
            if ep:
                return ep
        except Exception:
            pass
    # Fallback: first function in target.py
    src = (task_dir / "target.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef):
            return node.name
    return "task_func"


def run_and_tee(
    cmd: list[str], log_path: Path, cwd: Path, quiet: bool,
    extra_env: dict[str, str] | None = None,
) -> int:
    """Run cmd, streaming output to both console and log_path."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            logf.write(line)
            if not quiet:
                print(line, end="")
        return proc.wait()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _make_row(
    task_id: str,
    func_name: str,
    status: str,
    rc: int,
    duration: float,
    result: dict | None,
    result_json: Path,
    command: str,
) -> dict:
    return {
        "task_id":        task_id,
        "func_name":      func_name,
        "status":         status,
        "return_code":    rc,
        "duration_s":     round(duration, 1),
        "baseline_mj":    result.get("baseline_mj")    if result else None,
        "best_mj":        result.get("best_mj")        if result else None,
        "improvement_pct":result.get("improvement_pct")if result else None,
        "f3_evals":       result.get("f3_evals")       if result else None,
        "co2_search_ug":  result.get("co2_search_ug")  if result else None,
        "chain_len":      len(result.get("chain", [])) if result else None,
        "result_json":    str(result_json) if result_json.exists() else None,
        "command":        command,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Spectra on prepared BigCodeBench tasks.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  python scripts/run_spectra_bigcodebench.py
  python scripts/run_spectra_bigcodebench.py --budget 30 --no-llm
  python scripts/run_spectra_bigcodebench.py --task-ids BigCodeBench/4 BigCodeBench/21
  python scripts/run_spectra_bigcodebench.py --dry-run --max-tasks 5
""",
    )
    parser.add_argument(
        "--tasks-dir", default="bigcodebench_tasks",
        help="Directory of prepared tasks (default: bigcodebench_tasks)",
    )
    parser.add_argument(
        "--spectra-script", default="spectra/spectra.py",
        help="Path to spectra.py relative to repo root (default: spectra/spectra.py)",
    )
    parser.add_argument(
        "--out-root", default=None,
        help="Output root (default: bigcodebench_spectra_<timestamp>)",
    )
    parser.add_argument(
        "--budget", type=int, default=20,
        help="Spectra F3 evaluation budget per task (default: 20)",
    )
    parser.add_argument(
        "--ei-top-k", type=int, default=2,
        help="Spectra EI top-K candidates per iteration (default: 2)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable LLM operators in Spectra",
    )
    parser.add_argument(
        "--task-ids", nargs="+", metavar="ID",
        help="Run only specific tasks e.g. BigCodeBench/4 BigCodeBench/21",
    )
    parser.add_argument(
        "--max-tasks", type=int, default=0,
        help="Max tasks to run (0 = all found)",
    )
    parser.add_argument(
        "--per-task-timeout", type=int, default=1800,
        help="Seconds before killing a Spectra run (default: 1800 = 30 min)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip tasks that already have a result JSON",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print Spectra commands without executing them",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-line Spectra stdout (still writes to run.log)",
    )
    parser.add_argument(
        "--python", default=sys.executable,
        help="Python executable (default: current interpreter)",
    )
    parser.add_argument(
        "--co2-intensity", type=float, default=475.0,
        help="Grid CO2 intensity gCO2/kWh for Spectra (default: 475)",
    )
    args = parser.parse_args()

    repo_root      = Path(__file__).resolve().parent.parent
    tasks_dir      = Path(args.tasks_dir).resolve()
    spectra_script = (repo_root / args.spectra_script).resolve()

    # ── Load .env for Gemini keys ─────────────────────────────────────────
    dotenv = _load_dotenv(repo_root)
    # Build extra env dict: GEMINI_API_KEYS (supports key rotation) takes
    # precedence; fall back to GEMINI_API_KEY if only that is present.
    extra_env: dict[str, str] = {}
    for key in ("GEMINI_API_KEYS", "GEMINI_API_KEY", "HF_TOKEN"):
        val = dotenv.get(key) or os.environ.get(key, "")
        if val:
            extra_env[key] = val
    # Spectra's GeminiClient reads GEMINI_API_KEYS first, then GEMINI_API_KEY
    gemini_available = bool(extra_env.get("GEMINI_API_KEYS") or extra_env.get("GEMINI_API_KEY"))

    # ── Validation ────────────────────────────────────────────────────────
    if not tasks_dir.exists():
        print(
            f"ERROR: tasks directory not found: {tasks_dir}\n"
            "Run  python scripts/prepare_bigcodebench.py  first.",
            file=sys.stderr,
        )
        return 1
    if not spectra_script.exists():
        print(f"ERROR: spectra.py not found: {spectra_script}", file=sys.stderr)
        return 1

    # ── Output directories ────────────────────────────────────────────────
    out_root = (
        Path(args.out_root).resolve()
        if args.out_root
        else (repo_root / f"bigcodebench_spectra_{_now_stamp()}").resolve()
    )
    runs_root     = out_root / "runs"
    summaries_dir = out_root / "summaries"
    runs_root.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    # ── Discover tasks ────────────────────────────────────────────────────
    task_dirs = discover_tasks(tasks_dir, args.task_ids)
    if args.max_tasks > 0:
        task_dirs = task_dirs[: args.max_tasks]

    if not task_dirs:
        print(
            "No tasks found.\n"
            "  Run  python scripts/prepare_bigcodebench.py  first,\n"
            "  or check --tasks-dir / --task-ids.",
            file=sys.stderr,
        )
        return 1

    total = len(task_dirs)
    print("=" * 70)
    print("SPECTRA — BigCodeBench")
    print("=" * 70)
    print(f"Tasks       : {total}")
    print(f"Budget/task : {args.budget} F3 evals")
    print(f"EI top-k    : {args.ei_top_k}")
    if args.no_llm:
        llm_status = "disabled (--no-llm)"
    elif gemini_available:
        n_keys = len([k for k in extra_env.get("GEMINI_API_KEYS", "").split(",") if k.strip()])
        llm_status = f"enabled ({n_keys} key(s) from .env)"
    else:
        llm_status = "disabled (no GEMINI_API_KEY found)"
    print(f"LLM         : {llm_status}")
    print(f"Tasks dir   : {tasks_dir}")
    print(f"Output      : {out_root}")
    if args.dry_run:
        print("** DRY RUN — no commands will be executed **")
    print()

    # ── Save manifest ─────────────────────────────────────────────────────
    manifest = {
        "created_utc":    datetime.now(timezone.utc).isoformat(),
        "repo_root":      str(repo_root),
        "tasks_dir":      str(tasks_dir),
        "spectra_script": str(spectra_script),
        "output_root":    str(out_root),
        "budget":         args.budget,
        "ei_top_k":       args.ei_top_k,
        "no_llm":         args.no_llm,
        "task_ids":       [d.name.replace("_", "/", 1) for d in task_dirs],
        "dry_run":        args.dry_run,
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # ── Run loop ──────────────────────────────────────────────────────────
    rows: list[dict] = []

    for idx, task_dir in enumerate(task_dirs, 1):
        task_id_dir = task_dir.name                       # e.g. BigCodeBench_4
        task_id     = task_id_dir.replace("_", "/", 1)   # e.g. BigCodeBench/4
        func_name   = read_func_name(task_dir)

        run_dir      = runs_root / task_id_dir
        artifacts    = run_dir / "artifacts"
        log_path     = run_dir / "run.log"
        command_path = run_dir / "command.txt"
        result_json  = artifacts / func_name / f"{func_name}_result.json"

        # Resume: skip if result already exists
        if args.resume and result_json.exists():
            result = _read_json(result_json)
            status = "ok" if result else "missing_result"
            imp = result.get("improvement_pct", "?") if result else "?"
            print(f"[{idx}/{total}] SKIP (resume) {task_id}  improvement={imp}")
            rows.append(_make_row(task_id, func_name, status, 0, 0.0,
                                  result, result_json, ""))
            continue

        # Build Spectra command
        cmd = [
            args.python, str(spectra_script),
            "--source",        str(task_dir / "target.py"),
            "--tests",         str(task_dir / "test_target.py"),
            "--func",          func_name,
            "--budget",        str(args.budget),
            "--ei-top-k",      str(args.ei_top_k),
            "--out-dir",       str(artifacts),
            "--co2-intensity", str(args.co2_intensity),
        ]
        if args.no_llm:
            cmd.append("--no-llm")

        run_dir.mkdir(parents=True, exist_ok=True)
        command_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")

        print(f"[{idx}/{total}] {task_id} ({func_name}) …", end=" ", flush=True)
        start = time.perf_counter()

        if args.dry_run:
            print(f"DRY  {shlex.join(cmd)[:100]}")
            rc, duration = 0, 0.0
            status = "planned"
            result_data = None
        else:
            try:
                rc = run_and_tee(cmd, log_path=log_path, cwd=repo_root,
                                 quiet=args.quiet, extra_env=extra_env)
            except subprocess.TimeoutExpired:
                rc = -1
            except Exception as exc:
                print(f"\n  ERROR launching process: {exc}")
                rc = -2
            duration = time.perf_counter() - start
            result_data = _read_json(result_json)
            status = (
                "ok"             if rc == 0 and result_data else
                "missing_result" if rc == 0 else
                "failed"
            )

            if status == "ok" and result_data:
                imp = result_data.get("improvement_pct", 0.0)
                bmj = result_data.get("baseline_mj")
                bst = result_data.get("best_mj")
                print(
                    f"OK  ({duration:.0f}s  "
                    f"improvement={imp:+.1f}%"
                    + (f"  {bmj:.3f}→{bst:.3f} mJ" if bmj and bst else "")
                    + ")"
                )
            else:
                print(f"{status.upper()}  (rc={rc}  {duration:.0f}s)")

        rows.append(_make_row(task_id, func_name, status, rc if not args.dry_run else 0,
                              duration, result_data if not args.dry_run else None,
                              result_json, shlex.join(cmd)))

    # ── Summaries ─────────────────────────────────────────────────────────
    rows_sorted = sorted(rows, key=lambda r: _sort_key(r["task_id"]))

    summary_json = summaries_dir / "run_summary.json"
    summary_json.write_text(json.dumps(rows_sorted, indent=2), encoding="utf-8")

    fieldnames = [
        "task_id", "func_name", "status", "return_code", "duration_s",
        "baseline_mj", "best_mj", "improvement_pct", "f3_evals",
        "co2_search_ug", "chain_len", "result_json", "command",
    ]
    summary_csv = summaries_dir / "run_summary.csv"
    _write_csv(summary_csv, rows_sorted, fieldnames)

    # ── Print final table ─────────────────────────────────────────────────
    ok_rows     = [r for r in rows_sorted if r["status"] == "ok"]
    improvements = [r["improvement_pct"] for r in ok_rows if r["improvement_pct"] is not None]

    print()
    print("=" * 70)
    print(f"Total: {len(rows_sorted)}  |  OK: {len(ok_rows)}  |  "
          f"Failed: {sum(1 for r in rows_sorted if r['status'] == 'failed')}  |  "
          f"Missing: {sum(1 for r in rows_sorted if r['status'] == 'missing_result')}")

    if improvements:
        print(
            f"Energy improvement:  "
            f"mean={statistics.mean(improvements):+.1f}%  "
            f"median={statistics.median(improvements):+.1f}%  "
            f"best={max(improvements):+.1f}%  "
            f"worst={min(improvements):+.1f}%"
        )

    if ok_rows:
        print()
        hdr = f"  {'Task':<30} {'Base(mJ)':>10} {'Best(mJ)':>10} {'Δenergy%':>10} {'F3evals':>8}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for r in ok_rows[:20]:   # show at most 20 rows
            bm  = r["baseline_mj"]
            bst = r["best_mj"]
            imp = r["improvement_pct"]
            fe  = r["f3_evals"]
            b_s = f"{bm:.3f}"    if bm  is not None else "  n/a"
            s_s = f"{bst:.3f}"   if bst is not None else "  n/a"
            i_s = f"{imp:+.1f}"  if imp is not None else "  n/a"
            f_s = str(fe)        if fe  is not None else "  n/a"
            short = r["task_id"].replace("BigCodeBench/", "BCB/")
            print(f"  {short:<30} {b_s:>10} {s_s:>10} {i_s:>10} {f_s:>8}")
        if len(ok_rows) > 20:
            print(f"  … ({len(ok_rows) - 20} more in CSV)")

    print()
    print(f"Summary CSV : {summary_csv}")
    print(f"Summary JSON: {summary_json}")
    print("=" * 70)

    failed = sum(1 for r in rows_sorted if r["status"] in ("failed", "missing_result"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
