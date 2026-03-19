#!/usr/bin/env python3
"""
Run HEDGE on EvoEval problems 4, 61, 63, 90 in standard mode.

Features for this run:
  - Proxy filter DISABLED  (--no-proxy-filter)
  - All mutations & generated code stored in mutations_log.json
  - Gemini multi-key rotation active via GEMINI_API_KEYS in .env

Usage:
    python scripts/run_standard_four.py [options]

After the run, use the analysis script to calibrate proxy thresholds:
    python scripts/analyze_proxy_metrics.py <run_dir>/<problem>
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

def _parse_results(problem_output: Path) -> Optional[Dict[str, Any]]:
    """Read pareto_results.json and results.json to extract energy/time metrics."""
    pareto_file = problem_output / "pareto_results.json"
    results_file = problem_output / "results.json"

    parsed: Dict[str, Any] = {}

    # Baseline from results.json
    if results_file.exists():
        try:
            with open(results_file) as f:
                results = json.load(f)
            baseline = results.get("baseline_metrics", {})
            parsed["baseline_energy_joules"] = baseline.get("energy_joules", 0.0)
            parsed["baseline_duration_seconds"] = baseline.get("duration_seconds", 0.0)
        except Exception:
            pass

    # Best from pareto_results.json
    if pareto_file.exists():
        try:
            with open(pareto_file) as f:
                pareto_data = json.load(f)
            if not isinstance(pareto_data, list):
                pareto_data = [pareto_data]
            if pareto_data:
                best = min(
                    pareto_data,
                    key=lambda x: x.get("metrics", {}).get("energy_joules", float("inf")),
                )
                m = best.get("metrics", {})
                parsed["best_energy_joules"] = m.get("energy_joules", 0.0)
                parsed["best_duration_seconds"] = m.get("duration_seconds", 0.0)
                parsed["best_mutation"] = best.get("mutation", "unknown")
                parsed["best_generation"] = best.get("generation", -1)
                parsed["pareto_solutions"] = len(pareto_data)

                baseline_e = parsed.get("baseline_energy_joules", 0.0)
                best_e = parsed["best_energy_joules"]
                if baseline_e > 0:
                    parsed["energy_improvement_pct"] = (baseline_e - best_e) / baseline_e * 100
                baseline_t = parsed.get("baseline_duration_seconds", 0.0)
                best_t = parsed["best_duration_seconds"]
                if baseline_t > 0:
                    parsed["time_improvement_pct"] = (baseline_t - best_t) / baseline_t * 100

                # Check optimized file was saved
                optimized_files = list(problem_output.glob("optimized_*.py"))
                parsed["optimized_file"] = optimized_files[0].name if optimized_files else None
        except Exception:
            pass

    return parsed if parsed else None


PROBLEMS = [
    "EvoEval_difficult_4",
    "EvoEval_difficult_61",
    "EvoEval_difficult_63",
    "EvoEval_difficult_90",
]


def run_single(
    problem_name: str,
    output_dir: Path,
    *,
    level: str,
    generations: int,
    population_size: int,
    llm_provider: str,
    test_iterations: int,
    test_warmup_iterations: int,
    test_seed: int,
    harness_repetitions: int,
    visualize: bool,
    timeout: int,
) -> Dict[str, Any]:
    problem_dir = Path("evoeval_benchmark") / problem_name
    target_file = problem_dir / "target.py"
    test_file   = problem_dir / "test_target.py"

    if not target_file.exists() or not test_file.exists():
        return {"status": "error", "error": f"Files not found in {problem_dir}"}

    problem_output = output_dir / problem_name
    problem_output.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "hedge.py", "optimize",
        str(target_file),
        str(test_file),
        "--level",                  level,
        "--generations",            str(generations),
        "--population-size",        str(population_size),
        "--out-dir",                str(problem_output),
        "--test-iterations",        str(test_iterations),
        "--test-warmup-iterations", str(test_warmup_iterations),
        "--test-seed",              str(test_seed),
        "--harness-repetitions",    str(harness_repetitions),
        "--no-proxy-filter",        # key requirement: store all mutations without filtering
        "--llm",                    llm_provider,
    ]
    if visualize:
        cmd.append("--visualize")

    print(f"\n  Command: {' '.join(cmd)}")
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            ret: Dict[str, Any] = {"status": "success", "elapsed_s": elapsed, "output_dir": str(problem_output)}
            parsed = _parse_results(problem_output)
            if parsed:
                ret.update(parsed)
            return ret
        else:
            return {
                "status": "failed",
                "elapsed_s": elapsed,
                "error": result.stderr[-1000:] if result.stderr else "unknown",
                "stdout_tail": result.stdout[-500:] if result.stdout else "",
            }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "elapsed_s": timeout}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(
        description="Run HEDGE on EvoEval problems 4, 61, 63, 90 (standard mode, no proxy filter)"
    )
    parser.add_argument("--level",               default="standard",
                        choices=["micro", "basic", "standard", "advanced", "aggressive"])
    parser.add_argument("--generations",         type=int, default=10)
    parser.add_argument("--population-size",     type=int, default=8)
    parser.add_argument("--llm",                 default="gemini")
    parser.add_argument("--test-iterations",     type=int, default=3)
    parser.add_argument("--test-warmup-iterations", type=int, default=5)
    parser.add_argument("--test-seed",           type=int, default=42)
    parser.add_argument("--harness-repetitions", type=int, default=500,
                        help="Repetitions of test function inside one monitored window "
                             "(default: 500 -- gives ~115ms for 0.23ms EvoEval functions)")
    parser.add_argument("--output-dir",          type=str, default=None)
    parser.add_argument("--no-visualize",        action="store_true")
    parser.add_argument("--timeout",             type=int, default=30000,
                        help="Per-problem timeout in seconds (default: 2700 = 45 min)")
    parser.add_argument("--problems",            nargs="+", default=None,
                        help="Override default problem list (e.g. EvoEval_difficult_4)")
    args = parser.parse_args()

    problems: List[str] = args.problems if args.problems else PROBLEMS

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir_name = args.output_dir or f"evoeval_standard_four_{timestamp}"
    output_dir = Path(out_dir_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("HEDGE — EvoEval Standard Run (proxy filter disabled)")
    print("=" * 65)
    print(f"Problems   : {', '.join(problems)}")
    print(f"Level      : {args.level}")
    print(f"Generations: {args.generations}  |  Population: {args.population_size}")
    print(f"LLM        : {args.llm}")
    print(f"Output dir : {output_dir}")
    print(f"Proxy filter: DISABLED (all mutations measured)")
    print(f"Harness reps: {args.harness_repetitions}")
    print()

    run_results: Dict[str, Any] = {}
    total_start = time.time()

    for i, problem in enumerate(problems, 1):
        print(f"[{i}/{len(problems)}] {problem}")
        result = run_single(
            problem,
            output_dir,
            level=args.level,
            generations=args.generations,
            population_size=args.population_size,
            llm_provider=args.llm,
            test_iterations=args.test_iterations,
            test_warmup_iterations=args.test_warmup_iterations,
            test_seed=args.test_seed,
            harness_repetitions=args.harness_repetitions,
            visualize=not args.no_visualize,
            timeout=args.timeout,
        )
        run_results[problem] = result
        status_icon = "✓" if result["status"] == "success" else "✗"
        elapsed_str = f"{result.get('elapsed_s', 0):.1f}s"
        print(f"  {status_icon} {result['status'].upper()}  ({elapsed_str})")
        if result["status"] == "success":
            b_e = result.get("baseline_energy_joules")
            best_e = result.get("best_energy_joules")
            e_imp = result.get("energy_improvement_pct")
            t_imp = result.get("time_improvement_pct")
            if b_e is not None and best_e is not None:
                print(f"    Energy  : baseline={b_e*1000:.3f}mJ  best={best_e*1000:.3f}mJ", end="")
                if e_imp is not None:
                    print(f"  ({e_imp:+.1f}%)", end="")
                print()
            if t_imp is not None:
                b_t = result.get("baseline_duration_seconds", 0)
                best_t = result.get("best_duration_seconds", 0)
                print(f"    Time    : baseline={b_t*1000:.3f}ms  best={best_t*1000:.3f}ms  ({t_imp:+.1f}%)")
            mutation = result.get("best_mutation")
            pareto_n = result.get("pareto_solutions")
            opt_file = result.get("optimized_file")
            if mutation:
                print(f"    Best    : {mutation}  (gen {result.get('best_generation', '?')})")
            if pareto_n is not None:
                print(f"    Pareto  : {pareto_n} solution(s)")
            if opt_file:
                print(f"    Saved   : {opt_file}")
        else:
            print(f"  Error: {result.get('error', '')[:200]}")

    total_elapsed = time.time() - total_start

    print()
    print("=" * 65)
    print(f"Completed in {total_elapsed:.1f}s")
    successful = [p for p, r in run_results.items() if r["status"] == "success"]
    print(f"Successful: {len(successful)}/{len(problems)}")

    # Per-problem energy summary table
    problems_with_energy = [
        p for p in successful
        if run_results[p].get("baseline_energy_joules") is not None
    ]
    if problems_with_energy:
        print()
        print(f"  {'Problem':<30} {'Base(mJ)':>10} {'Best(mJ)':>10} {'Energy%':>9} {'Time%':>8}")
        print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*9} {'-'*8}")
        for p in problems_with_energy:
            r = run_results[p]
            b_e = (r.get("baseline_energy_joules") or 0) * 1000
            best_e = (r.get("best_energy_joules") or 0) * 1000
            e_imp = r.get("energy_improvement_pct", float("nan"))
            t_imp = r.get("time_improvement_pct", float("nan"))
            e_str = f"{e_imp:+.1f}" if e_imp == e_imp else "  n/a"
            t_str = f"{t_imp:+.1f}" if t_imp == t_imp else "  n/a"
            short = p.replace("EvoEval_difficult_", "Problem_")
            print(f"  {short:<30} {b_e:>10.3f} {best_e:>10.3f} {e_str:>9} {t_str:>8}")

    print("=" * 65)

    # Save summary
    summary = {
        "config": {
            "problems": problems,
            "level": args.level,
            "generations": args.generations,
            "population_size": args.population_size,
            "llm_provider": args.llm,
            "test_iterations": args.test_iterations,
            "test_warmup_iterations": args.test_warmup_iterations,
            "test_seed": args.test_seed,
            "harness_repetitions": args.harness_repetitions,
            "proxy_filter": False,
            "timestamp": timestamp,
        },
        "results": run_results,
        "total_elapsed_s": total_elapsed,
    }
    summary_path = output_dir / "run_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")
    print()
    print("Next step — calibrate proxy thresholds from this run:")
    for problem in successful:
        print(f"  python scripts/analyze_proxy_metrics.py {output_dir / problem}")


if __name__ == "__main__":
    main()
