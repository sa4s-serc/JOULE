#!/usr/bin/env python3
"""
Phase 3.5: Workload Pre-flight Gate.

Dry-runs workload discovery for each function sampled in Phase 3.
Functions with zero qualifying workloads (alignment_score >= threshold)
are filtered out before the expensive Phase 4 baseline run.

Output files:
  results/hotspots/{repo}_preflight.csv         — passed the gate
  results/hotspots/{repo}_preflight_skipped.csv — failed the gate (diagnostics)
"""

import csv
import os
import sys
import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PreflightResult:
    file_path: str
    function_name: str
    qualname: str
    line_start: int
    score: float
    workload_count: int
    max_alignment: float
    passed: bool
    skip_reason: str  # "" | "no_workloads" | "low_alignment" | "discovery_error"


def infer_module(file_path: str, repo_path: Path) -> str:
    """Infer dotted module name from an absolute file path and repo root."""
    p = Path(file_path)
    src_root = repo_path / "src"
    try:
        if p.is_relative_to(src_root):
            rel = p.relative_to(src_root).with_suffix("")
        elif p.is_relative_to(repo_path):
            rel = p.relative_to(repo_path).with_suffix("")
        else:
            return p.stem
    except ValueError:
        return p.stem
    return ".".join(rel.parts)


def preflight_single(
    row: dict,
    repo_path: Path,
    min_workloads: int,
    min_alignment: float,
    workload_limit: int,
) -> PreflightResult:
    """Run workload discovery for a single function and classify pass/fail."""
    from joule.discovery.workloads import discover_pytest_workloads
    from joule.models import TargetSpec

    file_path = row["file_path"]
    function_name = row["function_name"]
    qualname = row.get("qualname", function_name)
    line_start = int(row.get("line_start", 0) or 0)
    score = float(row.get("score", 0) or 0)

    base = PreflightResult(
        file_path=file_path,
        function_name=function_name,
        qualname=qualname,
        line_start=line_start,
        score=score,
        workload_count=0,
        max_alignment=0.0,
        passed=False,
        skip_reason="",
    )

    try:
        spec = TargetSpec(
            project_root=repo_path,
            file_path=Path(file_path),
            module=infer_module(file_path, repo_path),
            function_name=function_name,
            qualname=qualname,
            owner_path=[],
            line_start=line_start,
            line_end=line_start,
            source="",
            is_async=False,
            metadata={},
        )
        workloads = discover_pytest_workloads(repo_path, spec, limit=workload_limit)
    except Exception as e:
        print(f"  Warning: workload discovery error for {function_name}: {e}", file=sys.stderr)
        base.skip_reason = "discovery_error"
        return base

    all_scores = [
        float(w.metadata.get("alignment_score", 0))
        for w in workloads
    ]
    max_score = max(all_scores, default=0.0)
    qualifying = [s for s in all_scores if s >= min_alignment]

    base.max_alignment = max_score
    base.workload_count = len(qualifying)

    if len(qualifying) >= min_workloads:
        base.passed = True
        base.skip_reason = ""
    else:
        base.passed = False
        base.skip_reason = "no_workloads" if len(workloads) == 0 else "low_alignment"

    return base


def run_preflight(
    sample_csv: Path,
    repo_path: Path,
    min_workloads: int,
    min_alignment: float,
    workload_limit: int,
) -> tuple[list[PreflightResult], list[PreflightResult]]:
    """Process all rows in sample_csv and split into passed/skipped lists."""
    passed: list[PreflightResult] = []
    skipped: list[PreflightResult] = []

    with open(sample_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  Running pre-flight on {len(rows)} functions...")
    for i, row in enumerate(rows, 1):
        result = preflight_single(row, repo_path, min_workloads, min_alignment, workload_limit)
        status = "✓" if result.passed else "✗"
        reason = (
            f" ({result.skip_reason})"
            if not result.passed
            else f" (workloads={result.workload_count}, max_align={result.max_alignment:.1f})"
        )
        print(f"  [{i:3d}/{len(rows)}] {status} {result.function_name}{reason}")
        if result.passed:
            passed.append(result)
        else:
            skipped.append(result)

    return passed, skipped


_PASSED_COLS = [
    "file_path", "function_name", "qualname", "line_start",
    "score", "workload_count", "max_alignment",
]
_SKIPPED_COLS = _PASSED_COLS + ["skip_reason"]


def save_preflight_results(
    passed: list[PreflightResult],
    skipped: list[PreflightResult],
    passed_file: Path,
    skipped_file: Path,
) -> None:
    passed_file.parent.mkdir(parents=True, exist_ok=True)

    with open(passed_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_PASSED_COLS)
        w.writeheader()
        for r in passed:
            w.writerow({k: getattr(r, k) for k in _PASSED_COLS})

    with open(skipped_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_SKIPPED_COLS)
        w.writeheader()
        for r in skipped:
            w.writerow({k: getattr(r, k) for k in _SKIPPED_COLS})


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3.5: Workload pre-flight gate")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument(
        "--min-workloads", type=int,
        default=int(os.environ.get("MIN_WORKLOADS_PREFLIGHT", "1")),
    )
    parser.add_argument(
        "--min-alignment", type=float,
        default=float(os.environ.get("MIN_ALIGNMENT_PREFLIGHT", "3.0")),
    )
    parser.add_argument(
        "--workload-limit", type=int,
        default=int(os.environ.get("WORKLOAD_DISCOVERY_LIMIT", "20")),
    )
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
    sample_csv = results_dir / "hotspots" / f"{args.repo}_sample_targets.csv"
    passed_file = results_dir / "hotspots" / f"{args.repo}_preflight.csv"
    skipped_file = results_dir / "hotspots" / f"{args.repo}_preflight_skipped.csv"

    if not repo_path.exists():
        print(f"Error: repo directory not found: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if not sample_csv.exists():
        print(f"Error: sample targets CSV not found: {sample_csv}", file=sys.stderr)
        print("Run Phase 3 first.", file=sys.stderr)
        sys.exit(1)

    print(f"=== Phase 3.5: Workload Pre-flight for {args.repo} ===")
    print(
        f"  min_workloads={args.min_workloads}, min_alignment={args.min_alignment}, "
        f"workload_limit={args.workload_limit}"
    )

    passed, skipped = run_preflight(
        sample_csv, repo_path,
        args.min_workloads, args.min_alignment, args.workload_limit,
    )

    save_preflight_results(passed, skipped, passed_file, skipped_file)

    total = len(passed) + len(skipped)
    print(f"\n  Pre-flight complete: {len(passed)}/{total} passed, {len(skipped)} skipped")
    if skipped:
        from collections import Counter
        reasons = Counter(r.skip_reason for r in skipped)
        for reason, count in reasons.most_common():
            print(f"    {reason}: {count}")

    print(f"  Passed  → {passed_file}")
    print(f"  Skipped → {skipped_file}")

    if not passed:
        print(
            "  WARNING: No functions passed pre-flight — Phase 4 will have nothing to run.",
            file=sys.stderr,
        )
        # Exit 0: let the orchestrator handle the empty case gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
