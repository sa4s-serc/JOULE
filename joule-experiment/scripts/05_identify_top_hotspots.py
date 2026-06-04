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

We prefer target_top_functions (functions inside the target file) when
available, falling back to top_functions filtered to project ownership.
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict


def find_hotspot_files(baseline_dir: Path) -> list[Path]:
    """Find all hotspots.json files produced by Phase 4 baseline runs."""
    return list(baseline_dir.glob("*/hotspots.json"))


def parse_hotspot_file(hotspot_file: Path) -> list[dict]:
    """
    Parse a single hotspots.json and return a flat list of hotspot entries.

    Each entry has: function, file, cumulative_time_s, ownership.
    """
    try:
        with open(hotspot_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Warning: could not parse {hotspot_file}: {e}", file=sys.stderr)
        return []

    # Prefer target_top_functions (functions within the profiled target file)
    entries = data.get("target_top_functions") or []

    # Fall back to project-owned functions from top_functions
    if not entries:
        entries = [
            fn for fn in data.get("top_functions", [])
            if fn.get("ownership") == "project"
        ]

    return entries


def aggregate_hotspots(baseline_dir: Path, limit: int = 30) -> list[dict]:
    """
    Walk all baseline subdirectories, aggregate cumulative_time_s per
    (function, file) pair across all workloads, return top `limit` entries.
    """
    hotspot_files = find_hotspot_files(baseline_dir)

    if not hotspot_files:
        print(f"  Warning: no hotspots.json files found in {baseline_dir}", file=sys.stderr)
        print("  Ensure Phase 4 completed successfully.", file=sys.stderr)
        return []

    print(f"  Found {len(hotspot_files)} hotspot files")

    # Keyed by (function_name, file_path) → {total_time, count, line}
    agg: dict[tuple, dict] = defaultdict(lambda: {"total_time": 0.0, "count": 0, "line": 0})

    for hf in hotspot_files:
        entries = parse_hotspot_file(hf)
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
        print("  Warning: no hotspot data aggregated (all entries empty or failed)", file=sys.stderr)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Identify top hotspots from baseline results")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--results-dir", default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    results_dir = Path(args.results_dir) if args.results_dir else script_dir.parent / "results"

    baseline_dir = results_dir / "hotspots" / f"{args.repo}_sample_baselines"
    output_file = results_dir / "final_baselines" / f"{args.repo}_top_hotspots.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not baseline_dir.exists():
        print(f"Error: baseline directory not found: {baseline_dir}", file=sys.stderr)
        print("Run Phase 4 first.", file=sys.stderr)
        sys.exit(1)

    print(f"Aggregating hotspots from: {baseline_dir}")
    top_hotspots = aggregate_hotspots(baseline_dir, args.limit)

    if not top_hotspots:
        print("ERROR: No hotspot data found — Phase 4 may have produced no valid baselines.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Identified {len(top_hotspots)} top hotspots")
    save_top_hotspots(top_hotspots, output_file)
    print(f"Top hotspots written to: {output_file}")

    print("\nTop 10 hotspots:")
    for i, h in enumerate(top_hotspots[:10], 1):
        print(f"  {i:2d}. {h['function_name']}  "
              f"runtime={h['total_runtime']:.3f}s  "
              f"occurrences={h['occurrence_count']}  "
              f"file={Path(h['file_path']).name}")


if __name__ == "__main__":
    main()
