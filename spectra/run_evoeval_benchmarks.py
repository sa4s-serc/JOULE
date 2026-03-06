#!/usr/bin/env python3
"""
Run SPECTRA across EvoEval benchmark problems and collect artifacts systematically.

Outputs are written under a timestamped directory:
  evoeval_results_YYYYMMDD_HHMMSS/
    runs/<variant>/<problem_id>/
      command.txt
      run.log
      artifacts/<function_name>/*  (SPECTRA JSON/CSV/figures)
    summaries/
      run_summary.csv
      run_summary.json
      ablation_summary.csv
      best_variant_per_problem.csv

Example:
  python3 run_evoeval_benchmarks.py --ablation --budget 10 --ei-top-k 2
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Variant:
    name: str
    budget: int
    ei_top_k: int
    no_llm: bool


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _problem_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"_(\d+)$", path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (10**9, path.name)


def discover_problems(benchmark_dir: Path) -> list[Path]:
    return sorted(
        [p for p in benchmark_dir.glob("EvoEval_difficult_*") if p.is_dir()],
        key=_problem_sort_key,
    )


def parse_entry_point_from_readme(readme_path: Path) -> str | None:
    if not readme_path.exists():
        return None
    text = readme_path.read_text(encoding="utf-8")
    match = re.search(r"^\*\*Entry Point\*\*:\s*([A-Za-z_]\w*)\s*$", text, re.M)
    return match.group(1) if match else None


def detect_first_function(source_path: Path) -> str:
    src = source_path.read_text(encoding="utf-8")
    mod = ast.parse(src)
    funcs = [n.name for n in mod.body if isinstance(n, ast.FunctionDef)]
    if not funcs:
        raise ValueError(f"No top-level function found in {source_path}")
    return funcs[0]


def resolve_function_name(problem_dir: Path) -> str:
    readme_name = parse_entry_point_from_readme(problem_dir / "README.md")
    if readme_name:
        return readme_name
    return detect_first_function(problem_dir / "target.py")


def build_variants(
    ablation: bool, budget: int, ei_top_k: int, no_llm: bool
) -> list[Variant]:
    if not ablation:
        return [Variant(name="main", budget=budget, ei_top_k=ei_top_k, no_llm=no_llm)]

    half_budget = max(1, budget // 2)
    variants = [
        Variant(name="default", budget=budget, ei_top_k=ei_top_k, no_llm=False),
        Variant(name="no_llm", budget=budget, ei_top_k=ei_top_k, no_llm=True),
        Variant(name=f"budget_{half_budget}", budget=half_budget, ei_top_k=ei_top_k, no_llm=False),
        Variant(name="ei_top_k_1", budget=budget, ei_top_k=1, no_llm=False),
    ]

    seen: set[tuple[int, int, bool]] = set()
    deduped: list[Variant] = []
    for v in variants:
        key = (v.budget, v.ei_top_k, v.no_llm)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)
    return deduped


def run_and_tee(cmd: list[str], log_path: Path, cwd: Path, quiet: bool) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            logf.write(line)
            if not quiet:
                print(line, end="")
        return proc.wait()


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_by_variant(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    variants = sorted({r["variant"] for r in rows})
    for name in variants:
        subset = [r for r in rows if r["variant"] == name]
        ok = [r for r in subset if r["status"] == "ok"]
        improvements = [r["improvement_pct"] for r in ok if r["improvement_pct"] is not None]
        co2_vals = [r["co2_search_ug"] for r in ok if r["co2_search_ug"] is not None]
        f3_vals = [r["f3_evals"] for r in ok if r["f3_evals"] is not None]
        out.append(
            {
                "variant": name,
                "runs_total": len(subset),
                "runs_ok": len(ok),
                "runs_failed": len(subset) - len(ok),
                "mean_improvement_pct": round(statistics.mean(improvements), 4) if improvements else None,
                "median_improvement_pct": round(statistics.median(improvements), 4) if improvements else None,
                "sum_co2_search_ug": round(sum(co2_vals), 4) if co2_vals else None,
                "mean_f3_evals": round(statistics.mean(f3_vals), 4) if f3_vals else None,
            }
        )
    return out


def best_variant_per_problem(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    problem_ids = sorted({r["problem_id"] for r in rows}, key=lambda x: _problem_sort_key(Path(x)))
    for pid in problem_ids:
        ok = [r for r in rows if r["problem_id"] == pid and r["status"] == "ok" and r["improvement_pct"] is not None]
        if not ok:
            out.append(
                {
                    "problem_id": pid,
                    "best_variant": None,
                    "best_improvement_pct": None,
                    "function_name": None,
                }
            )
            continue
        best = max(ok, key=lambda r: float(r["improvement_pct"]))
        out.append(
            {
                "problem_id": pid,
                "best_variant": best["variant"],
                "best_improvement_pct": best["improvement_pct"],
                "function_name": best["function_name"],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SPECTRA on EvoEval benchmark with systematic artifact collection and simple ablations."
    )
    parser.add_argument("--benchmark-dir", default="evoeval_benchmark", help="Benchmark root directory")
    parser.add_argument("--spectra-script", default="spectra.py", help="Path to spectra.py")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--out-root", default=None, help="Output root (default: evoeval_results_<timestamp>)")
    parser.add_argument("--budget", type=int, default=10, help="SPECTRA F3 budget")
    parser.add_argument("--ei-top-k", type=int, default=2, help="SPECTRA EI top-k")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM usage for non-ablation run")
    parser.add_argument("--ablation", action="store_true", help="Run preset ablation variants")
    parser.add_argument(
        "--problems",
        default="",
        help="Comma-separated problem directory names (e.g. EvoEval_difficult_4,EvoEval_difficult_16)",
    )
    parser.add_argument("--max-problems", type=int, default=0, help="Limit number of problems (0 means all)")
    parser.add_argument("--resume", action="store_true", help="Skip runs with existing result JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--quiet", action="store_true", help="Suppress SPECTRA stdout streaming")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    benchmark_dir = (repo_root / args.benchmark_dir).resolve()
    spectra_script = (repo_root / args.spectra_script).resolve()
    if not benchmark_dir.exists():
        raise FileNotFoundError(f"Benchmark directory not found: {benchmark_dir}")
    if not spectra_script.exists():
        raise FileNotFoundError(f"SPECTRA script not found: {spectra_script}")
    if args.budget < 1:
        raise ValueError("--budget must be >= 1")
    if args.ei_top_k < 1:
        raise ValueError("--ei-top-k must be >= 1")

    out_root = (
        Path(args.out_root).resolve()
        if args.out_root
        else (repo_root / f"evoeval_results_{_now_stamp()}").resolve()
    )
    summaries_dir = out_root / "summaries"
    runs_root = out_root / "runs"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    runs_root.mkdir(parents=True, exist_ok=True)

    problems = discover_problems(benchmark_dir)
    if args.problems:
        wanted = {x.strip() for x in args.problems.split(",") if x.strip()}
        problems = [p for p in problems if p.name in wanted]
    if args.max_problems > 0:
        problems = problems[: args.max_problems]
    if not problems:
        raise ValueError("No benchmark problems selected.")

    variants = build_variants(
        ablation=args.ablation, budget=args.budget, ei_top_k=args.ei_top_k, no_llm=args.no_llm
    )

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "benchmark_dir": str(benchmark_dir),
        "spectra_script": str(spectra_script),
        "output_root": str(out_root),
        "variants": [v.__dict__ for v in variants],
        "problems": [p.name for p in problems],
        "dry_run": args.dry_run,
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    rows: list[dict[str, Any]] = []

    total_runs = len(variants) * len(problems)
    run_idx = 0
    for variant in variants:
        for problem_dir in problems:
            run_idx += 1
            problem_id = problem_dir.name
            target = problem_dir / "target.py"
            tests = problem_dir / "test_target.py"
            func_name = resolve_function_name(problem_dir)

            run_dir = runs_root / variant.name / problem_id
            artifacts_out = run_dir / "artifacts"
            log_path = run_dir / "run.log"
            command_path = run_dir / "command.txt"
            result_json = artifacts_out / func_name / f"{func_name}_result.json"
            metrics_json = artifacts_out / func_name / f"{func_name}_metrics.json"
            figures_dir = artifacts_out / func_name / f"{func_name}_figures"

            cmd = [
                args.python,
                str(spectra_script),
                "--source",
                str(target),
                "--tests",
                str(tests),
                "--func",
                func_name,
                "--budget",
                str(variant.budget),
                "--ei-top-k",
                str(variant.ei_top_k),
                "--out-dir",
                str(artifacts_out),
            ]
            if variant.no_llm:
                cmd.append("--no-llm")

            run_dir.mkdir(parents=True, exist_ok=True)
            command_path.write_text(shlex.join(cmd) + "\n", encoding="utf-8")

            if args.resume and result_json.exists():
                print(f"[{run_idx}/{total_runs}] SKIP {variant.name}/{problem_id} (existing result)")
                result = read_json(result_json)
                row = {
                    "variant": variant.name,
                    "problem_id": problem_id,
                    "function_name": func_name,
                    "status": "ok" if result else "missing_result",
                    "return_code": 0 if result else None,
                    "duration_s": 0.0,
                    "baseline_mj": result.get("baseline_mj") if result else None,
                    "best_mj": result.get("best_mj") if result else None,
                    "improvement_pct": result.get("improvement_pct") if result else None,
                    "f3_evals": result.get("f3_evals") if result else None,
                    "co2_search_ug": result.get("co2_search_ug") if result else None,
                    "wall_s_reported": result.get("wall_s") if result else None,
                    "chain_len": len(result.get("chain", [])) if result else None,
                    "result_json": str(result_json) if result_json.exists() else None,
                    "metrics_json": str(metrics_json) if metrics_json.exists() else None,
                    "figures_dir": str(figures_dir) if figures_dir.exists() else None,
                    "command": shlex.join(cmd),
                }
                rows.append(row)
                continue

            print(f"[{run_idx}/{total_runs}] RUN  {variant.name}/{problem_id}")
            start = time.perf_counter()
            if args.dry_run:
                print("  " + shlex.join(cmd))
                rc = 0
            else:
                rc = run_and_tee(cmd, log_path=log_path, cwd=repo_root, quiet=args.quiet)
            duration = time.perf_counter() - start

            result = read_json(result_json)
            if args.dry_run:
                status = "planned"
            else:
                status = "ok" if rc == 0 and result else ("failed" if rc != 0 else "missing_result")
            row = {
                "variant": variant.name,
                "problem_id": problem_id,
                "function_name": func_name,
                "status": status,
                "return_code": rc,
                "duration_s": round(duration, 3),
                "baseline_mj": result.get("baseline_mj") if result else None,
                "best_mj": result.get("best_mj") if result else None,
                "improvement_pct": result.get("improvement_pct") if result else None,
                "f3_evals": result.get("f3_evals") if result else None,
                "co2_search_ug": result.get("co2_search_ug") if result else None,
                "wall_s_reported": result.get("wall_s") if result else None,
                "chain_len": len(result.get("chain", [])) if result else None,
                "result_json": str(result_json) if result_json.exists() else None,
                "metrics_json": str(metrics_json) if metrics_json.exists() else None,
                "figures_dir": str(figures_dir) if figures_dir.exists() else None,
                "command": shlex.join(cmd),
            }
            rows.append(row)

    rows_sorted = sorted(rows, key=lambda r: (r["variant"], _problem_sort_key(Path(r["problem_id"]))))
    run_summary_csv = summaries_dir / "run_summary.csv"
    run_summary_json = summaries_dir / "run_summary.json"
    write_csv(
        run_summary_csv,
        rows_sorted,
        fieldnames=[
            "variant",
            "problem_id",
            "function_name",
            "status",
            "return_code",
            "duration_s",
            "baseline_mj",
            "best_mj",
            "improvement_pct",
            "f3_evals",
            "co2_search_ug",
            "wall_s_reported",
            "chain_len",
            "result_json",
            "metrics_json",
            "figures_dir",
            "command",
        ],
    )
    run_summary_json.write_text(json.dumps(rows_sorted, indent=2), encoding="utf-8")

    ablation_rows = summarize_by_variant(rows_sorted)
    ablation_csv = summaries_dir / "ablation_summary.csv"
    write_csv(
        ablation_csv,
        ablation_rows,
        fieldnames=[
            "variant",
            "runs_total",
            "runs_ok",
            "runs_failed",
            "mean_improvement_pct",
            "median_improvement_pct",
            "sum_co2_search_ug",
            "mean_f3_evals",
        ],
    )

    best_rows = best_variant_per_problem(rows_sorted)
    best_csv = summaries_dir / "best_variant_per_problem.csv"
    write_csv(
        best_csv,
        best_rows,
        fieldnames=["problem_id", "best_variant", "best_improvement_pct", "function_name"],
    )

    ok_count = sum(1 for r in rows_sorted if r["status"] == "ok")
    planned_count = sum(1 for r in rows_sorted if r["status"] == "planned")
    fail_count = len(rows_sorted) - ok_count - planned_count
    print("\nBenchmark run complete.")
    print(f"Output root: {out_root}")
    print(f"Runs: {len(rows_sorted)} total, {ok_count} ok, {planned_count} planned, {fail_count} failed/missing")
    print(f"Run summary CSV: {run_summary_csv}")
    print(f"Ablation CSV: {ablation_csv}")
    print(f"Best-per-problem CSV: {best_csv}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
