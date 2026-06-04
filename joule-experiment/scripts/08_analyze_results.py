#!/usr/bin/env python3
"""
Phase 8: Results Analysis and Evaluation.

Aggregates optimization results across all repositories and produces a
structured JSON summary with per-repo and overall metrics.

Expected artifacts per optimization run (in results/optimizations/<repo>/<func>/):
  joule_optimize.log  — raw JSON output from `joule run`
  run_summary.json    — optional summary artifact from the joule run directory
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# ── Artifact parsers ──────────────────────────────────────────────────────────

def parse_joule_output(log_file: Path) -> dict | None:
    """
    Parse the joule_optimize.log (raw JSON from `joule run --output json`).
    Returns None if the file is missing, empty, or not valid JSON.
    """
    if not log_file.exists():
        return None
    try:
        with open(log_file) as f:
            content = f.read().strip()
        if not content:
            return None
        return json.loads(content)
    except Exception as e:
        print(f"  Warning: could not parse {log_file}: {e}", file=sys.stderr)
        return None


def parse_run_summary(func_dir: Path) -> dict | None:
    """
    Parse an optional run_summary.json copied from the joule run directory.
    """
    summary_file = func_dir / "run_summary.json"
    if not summary_file.exists():
        return None
    try:
        with open(summary_file) as f:
            return json.load(f)
    except Exception:
        return None


def extract_metrics(func_dir: Path) -> dict | None:
    """
    Extract outcome and improvement metrics from a function's optimization dir.

    Tries joule_optimize.log first (authoritative), then run_summary.json.
    Returns None if neither can be parsed.
    """
    data = parse_joule_output(func_dir / "joule_optimize.log")
    if data is None:
        data = parse_run_summary(func_dir)
    if data is None:
        return None
    return data


# ── Per-repo analysis ─────────────────────────────────────────────────────────

def analyze_repo_results(repo_name: str, results_dir: Path) -> dict:
    opt_dir = results_dir / "optimizations" / f"{repo_name}_optimizations"

    base = {
        "repo": repo_name,
        "total_runs": 0,
        "successful_optimizations": 0,
        "failed_optimizations": 0,
        "skipped_optimizations": 0,
        "optimizations": [],
        "avg_energy_improvement": 0.0,
        "avg_latency_improvement": 0.0,
        "avg_memory_improvement": 0.0,
        "operator_effectiveness": {},
        "common_failure_reasons": {},
    }

    if not opt_dir.exists():
        base["error"] = f"Optimization directory not found: {opt_dir}"
        return base

    func_dirs = [d for d in opt_dir.iterdir() if d.is_dir()]
    base["total_runs"] = len(func_dirs)

    energy_imps, latency_imps, memory_imps = [], [], []
    op_counts: dict = defaultdict(int)
    fail_reasons: dict = defaultdict(int)

    for func_dir in func_dirs:
        func_name = func_dir.name
        result = extract_metrics(func_dir)

        if result is None:
            base["failed_optimizations"] += 1
            fail_reasons["parse_error"] += 1
            continue

        outcome = result.get("outcome", "unknown")

        if outcome == "accepted":
            base["successful_optimizations"] += 1

            energy_imp = float(result.get("energy_improvement", 0))
            latency_imp = float(result.get("latency_improvement", 0))
            memory_imp = float(result.get("memory_improvement", 0))

            energy_imps.append(energy_imp)
            latency_imps.append(latency_imp)
            memory_imps.append(memory_imp)

            base["optimizations"].append({
                "function": func_name,
                "energy_improvement": energy_imp,
                "latency_improvement": latency_imp,
                "memory_improvement": memory_imp,
                "outcome": outcome,
                "operators_used": result.get("operators_used", []),
            })

            for op in result.get("operators_used", []):
                op_counts[op] += 1

        elif outcome == "skipped":
            base["skipped_optimizations"] += 1
        else:
            base["failed_optimizations"] += 1
            reason = result.get("failure_reason") or result.get("reason") or outcome or "unknown"
            fail_reasons[reason] += 1

    # Averages
    if energy_imps:
        base["avg_energy_improvement"] = sum(energy_imps) / len(energy_imps)
    if latency_imps:
        base["avg_latency_improvement"] = sum(latency_imps) / len(latency_imps)
    if memory_imps:
        base["avg_memory_improvement"] = sum(memory_imps) / len(memory_imps)

    base["operator_effectiveness"] = dict(op_counts)
    base["common_failure_reasons"] = dict(fail_reasons)

    return base


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_all_results(results_dir: Path, repos: list[str]) -> dict:
    all_results: dict = {
        "timestamp": datetime.now().isoformat(),
        "repos": [],
        "summary": {
            "total_repos": len(repos),
            "total_runs": 0,
            "total_successful": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "overall_success_rate": 0.0,
        },
    }

    total_runs = total_successful = total_failed = total_skipped = 0

    for repo in repos:
        metrics = analyze_repo_results(repo, results_dir)
        all_results["repos"].append(metrics)
        total_runs += metrics["total_runs"]
        total_successful += metrics["successful_optimizations"]
        total_failed += metrics["failed_optimizations"]
        total_skipped += metrics.get("skipped_optimizations", 0)

    all_results["summary"].update({
        "total_runs": total_runs,
        "total_successful": total_successful,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "overall_success_rate": (total_successful / total_runs) if total_runs > 0 else 0.0,
    })

    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze JOULE experiment results")
    parser.add_argument("--repos", default="black networkx sympy",
                        help="Space-separated list of repositories")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    results_dir = Path(args.results_dir) if args.results_dir else script_dir.parent / "results"
    output_file = (Path(args.output) if args.output
                   else results_dir / "analysis" / "aggregated_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    repos = args.repos.split()
    print(f"Aggregating results for: {repos}")
    print(f"Results directory: {results_dir}")

    all_results = aggregate_all_results(results_dir, repos)

    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAggregated results written to: {output_file}")

    s = all_results["summary"]
    print(f"\n{'='*50}")
    print(f"Total repos:            {s['total_repos']}")
    print(f"Total optimization runs:{s['total_runs']}")
    print(f"Successful:             {s['total_successful']}")
    print(f"Failed:                 {s['total_failed']}")
    print(f"Skipped:                {s['total_skipped']}")
    print(f"Overall success rate:   {s['overall_success_rate']:.1%}")

    for r in all_results["repos"]:
        print(f"\n── {r['repo']} ──")
        print(f"  Runs:       {r['total_runs']}")
        print(f"  Successful: {r['successful_optimizations']}")
        print(f"  Failed:     {r['failed_optimizations']}")
        if r["successful_optimizations"] > 0:
            print(f"  Avg energy improvement:  {r['avg_energy_improvement']:.2%}")
            print(f"  Avg latency improvement: {r['avg_latency_improvement']:.2%}")
            print(f"  Avg memory improvement:  {r['avg_memory_improvement']:.2%}")
        if r.get("common_failure_reasons"):
            print(f"  Failure reasons: {r['common_failure_reasons']}")
        if r.get("operator_effectiveness"):
            top_ops = sorted(r["operator_effectiveness"].items(),
                             key=lambda x: x[1], reverse=True)[:5]
            print(f"  Top operators: {top_ops}")


if __name__ == "__main__":
    main()
