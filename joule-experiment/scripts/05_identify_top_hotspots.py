#!/usr/bin/env python3
"""
Phase 5: Identify Top Hotspots from Baseline Results.

Parses the hotspots.json artifact produced by `joule baseline --hotspots`
for each sampled function and aggregates cumulative runtime across all
workloads to surface the highest-impact functions.

hotspots.json schema (schema_version 2):
  {
    "by_workload": [ { "workload_id": ..., "top_functions": [...], ... } ],
    "top_functions": [ { "file": ..., "function": ..., "cumulative_time_s": ..., ... } ],
    "target_top_functions": [ ... ],
    ...
  }

Noise filtering removes:
  - <module> execution traces
  - entries originating from test directories
  - third-party callees outside repo_path
  - single-occurrence entries below MIN_SINGLE_OCCURRENCE_RUNTIME
"""

import json
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict


# ── Noise filters ─────────────────────────────────────────────────────────────

def is_test_path(fpath: Path) -> bool:
    """Return True if any path component looks like a test directory."""
    for part in fpath.parts:
        if part in {"tests", "test", "testing"}:
            return True
        if part.startswith("test_"):
            return True
    return False


def filter_hotspot_entries(
    entries: list[dict],
    repo_path: Path,
    min_single_occurrence_runtime: float = 0.05,
) -> list[dict]:
    """
    Remove noise entries from a raw hotspot list.

    Rules (applied in order):
      1. Drop entries where function == "<module>"
      2. Drop entries whose file path is under a test directory
      3. Drop entries whose file path is not relative to repo_path (third-party)
      Note: rule 4 (single-occurrence runtime threshold) is applied after
            aggregation in aggregate_hotspots, not here on individual entries.
    """
    filtered = []
    for entry in entries:
        func = entry.get("function", "")
        fpath_str = entry.get("file", "")

        # Rule 1: drop module-level execution traces
        if func == "<module>":
            continue

        fpath = Path(fpath_str) if fpath_str else None

        # Rule 2: drop test-infrastructure entries
        if fpath and is_test_path(fpath):
            continue

        # Rule 3: drop third-party callees
        if fpath and fpath_str:
            try:
                fpath.relative_to(repo_path)
            except ValueError:
                continue

        filtered.append(entry)
    return filtered


# ── File I/O ──────────────────────────────────────────────────────────────────

def find_hotspot_files(baseline_dir: Path) -> list[Path]:
    """Find all hotspots.json files produced by Phase 4 baseline runs."""
    return list(baseline_dir.glob("*/hotspots.json"))


def parse_hotspot_file(hotspot_file: Path, repo_path: Path | None = None) -> list[dict]:
    """
    Parse a single hotspots.json and return a flat list of hotspot entries.

    Prefers target_top_functions (functions within the profiled target file).
    Falls back to top_functions filtered by file path under repo_path (rather
    than the ownership enum string, which misclassifies some repos like sympy).
    """
    try:
        with open(hotspot_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Warning: could not parse {hotspot_file}: {e}", file=sys.stderr)
        return []

    # Prefer target_top_functions (functions within the profiled target file)
    entries = data.get("target_top_functions") or []

    # Fall back: use path-based ownership check instead of the "ownership" enum
    # string, which may not correctly classify repos like sympy with
    # monkeypatched modules.
    if not entries and repo_path is not None:
        entries = []
        for fn in data.get("top_functions", []):
            fpath_str = fn.get("file", "")
            if not fpath_str:
                continue
            try:
                Path(fpath_str).relative_to(repo_path)
                entries.append(fn)
            except ValueError:
                pass
    elif not entries:
        # Legacy fallback when repo_path not provided
        entries = [
            fn for fn in data.get("top_functions", [])
            if fn.get("ownership") == "project"
        ]

    return entries


# ── Aggregation ───────────────────────────────────────────────────────────────

def aggregate_hotspots(
    baseline_dir: Path,
    repo_path: Path,
    limit: int = 30,
) -> list[dict]:
    """
    Walk all baseline subdirectories, aggregate cumulative_time_s per
    (function, file) pair, apply noise filters, return top `limit` entries.
    """
    min_single = float(os.environ.get("MIN_SINGLE_OCCURRENCE_RUNTIME", "0.05"))

    hotspot_files = find_hotspot_files(baseline_dir)
    if not hotspot_files:
        print(f"  Warning: no hotspots.json files found in {baseline_dir}", file=sys.stderr)
        print("  Ensure Phase 4 completed successfully.", file=sys.stderr)
        return []

    print(f"  Found {len(hotspot_files)} hotspot files")

    # Keyed by (function_name, file_path) → {total_time, count, line}
    agg: dict[tuple, dict] = defaultdict(lambda: {"total_time": 0.0, "count": 0, "line": 0})

    for hf in hotspot_files:
        raw_entries = parse_hotspot_file(hf, repo_path)
        entries = filter_hotspot_entries(raw_entries, repo_path)
        for entry in entries:
            func = entry.get("function", "unknown")
            fpath = entry.get("file", "")
            t = float(entry.get("cumulative_time_s", 0.0))
            line = entry.get("line", 0)
            key = (func, fpath)
            agg[key]["total_time"] += t
            agg[key]["count"] += 1
            if not agg[key]["line"]:
                agg[key]["line"] = line

    if not agg:
        print("  Warning: no hotspot data aggregated (all entries empty or filtered)", file=sys.stderr)
        return []

    # Rule 4: drop single-occurrence entries below the runtime threshold
    agg = {
        k: v for k, v in agg.items()
        if not (v["count"] == 1 and v["total_time"] < min_single)
    }

    if not agg:
        print("  Warning: all entries dropped by single-occurrence runtime filter", file=sys.stderr)
        return []

    # Sort by total cumulative time descending
    sorted_entries = sorted(agg.items(), key=lambda x: x[1]["total_time"], reverse=True)

    top = []
    for (func_name, file_path), stats in sorted_entries[:limit]:
        top.append({
            "function_name": func_name,
            "file_path": file_path,
            "line": stats["line"],
            "total_runtime": stats["total_time"],
            "occurrence_count": stats["count"],
        })

    return top


def save_top_hotspots(top_hotspots: list[dict], output_file: Path) -> None:
    with open(output_file, "w") as f:
        f.write("file_path,function_name,line,total_runtime,occurrence_count\n")
        for h in top_hotspots:
            f.write(
                f"{h['file_path']},{h['function_name']},{h['line']},"
                f"{h['total_runtime']:.6f},{h['occurrence_count']}\n"
            )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Identify top hotspots from baseline results")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--repos-dir", default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    results_dir = (
        Path(args.results_dir) if args.results_dir else script_dir.parent / "results"
    )
    repos_dir = (
        Path(args.repos_dir) if args.repos_dir else script_dir.parent / "repos"
    )

    repo_path = repos_dir / args.repo
    baseline_dir = results_dir / "hotspots" / f"{args.repo}_sample_baselines"
    output_file = results_dir / "final_baselines" / f"{args.repo}_top_hotspots.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not baseline_dir.exists():
        print(f"Error: baseline directory not found: {baseline_dir}", file=sys.stderr)
        print("Run Phase 4 first.", file=sys.stderr)
        sys.exit(1)

    if not repo_path.exists():
        print(f"Warning: repo directory not found: {repo_path} — path filtering disabled", file=sys.stderr)
        repo_path = Path("/nonexistent")  # filter will drop all third-party; safe fallback

    print(f"Aggregating hotspots from: {baseline_dir}")
    print(f"Repository root (for ownership filter): {repo_path}")
    top_hotspots = aggregate_hotspots(baseline_dir, repo_path, args.limit)

    if not top_hotspots:
        print(
            "WARNING: No hotspot data found after filtering — writing empty output.",
            file=sys.stderr,
        )
        save_top_hotspots([], output_file)
        print(f"Empty top hotspots written to: {output_file}")
        # Exit 0 so the orchestrator can continue to phase 6 with an empty input
        sys.exit(0)

    print(f"Identified {len(top_hotspots)} top hotspots")
    save_top_hotspots(top_hotspots, output_file)
    print(f"Top hotspots written to: {output_file}")

    print("\nTop 10 hotspots:")
    for i, h in enumerate(top_hotspots[:10], 1):
        print(
            f"  {i:2d}. {h['function_name']}  "
            f"runtime={h['total_runtime']:.3f}s  "
            f"occurrences={h['occurrence_count']}  "
            f"file={Path(h['file_path']).name}"
        )


if __name__ == "__main__":
    main()
