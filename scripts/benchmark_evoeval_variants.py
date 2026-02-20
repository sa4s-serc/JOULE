#!/usr/bin/env python3
"""
Benchmark EvoEval code variants with GreenGymRunner.

This script discovers multiple baseline/variant implementations in this repo,
runs each implementation against the corresponding EvoEval tests, and reports
time/energy metrics with denoising repeats.

Two denoising knobs are available:
- samples: measured iterations inside GreenGymRunner (aggregated per run)
- runs: repeated full evaluations per variant (aggregated across runs)

Example:
    python scripts/benchmark_evoeval_variants.py \
      --sources benchmark,llm,optimized,single_prompt \
      --runs 5 --samples 7 --warmup-iterations 5 --base-seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from src.infrastructure.execution.runner import GreenGymRunner
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Could not import HEDGE runtime dependencies. "
        "Run this script with the project virtualenv, for example: "
        "'.venv/bin/python scripts/benchmark_evoeval_variants.py ...'"
    ) from exc

try:
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    plt = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = {"benchmark", "llm", "optimized", "single_prompt"}
PROBLEM_DIR_PATTERN = re.compile(r"EvoEval_difficult_(\d+)$")
SINGLE_PROMPT_PATTERN = re.compile(r"evo_eval_(\d+)\.py$")
PROBLEM_RANGE_PATTERN = re.compile(r"(\d+)\s*-\s*(\d+)$")


@dataclass(frozen=True)
class Variant:
    problem_id: int
    source_kind: str
    source_name: str
    code_path: Path
    test_path: Path

    @property
    def problem_name(self) -> str:
        return f"EvoEval_difficult_{self.problem_id}"

    @property
    def variant_label(self) -> str:
        if self.source_name and self.source_name != self.source_kind:
            return f"{self.source_kind}:{self.source_name}"
        return self.source_kind


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Systematically benchmark EvoEval code variants with GreenGymRunner.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  .venv/bin/python scripts/benchmark_evoeval_variants.py --baseline-only -p 4\n"
            "  .venv/bin/python scripts/benchmark_evoeval_variants.py --problem 4,16 --runs 10 --samples 7\n"
            "  .venv/bin/python scripts/benchmark_evoeval_variants.py --dry-run --sources benchmark,llm\n"
        ),
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="benchmark,llm,optimized,single_prompt",
        help=(
            "Comma-separated source groups to discover variants from. "
            f"Supported: {','.join(sorted(SUPPORTED_SOURCES))}"
        ),
    )
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help=(
            "Shortcut for --sources benchmark,llm,single_prompt "
            "(excludes prior optimized outputs)."
        ),
    )
    parser.add_argument(
        "--results-glob",
        type=str,
        default="evoeval_results*",
        help="Glob for optimized run directories (used when sources include 'optimized').",
    )
    parser.add_argument(
        "--problems",
        nargs="*",
        default=[],
        help=(
            "Optional problem filters, e.g. 4 16 52 or EvoEval_difficult_4. "
            "If omitted, all discovered problems are used."
        ),
    )
    parser.add_argument(
        "--problem",
        "-p",
        action="append",
        default=[],
        help=(
            "Problem filter (repeatable). Supports: 4, EvoEval_difficult_4, "
            "comma lists (4,16), and ranges (4-16)."
        ),
    )
    parser.add_argument(
        "--runs",
        "-r",
        type=int,
        default=5,
        help="Repeated full evaluations per variant for denoising (default: 5).",
    )
    parser.add_argument(
        "--samples",
        "-n",
        type=int,
        default=3,
        help="Measured iterations per evaluation inside GreenGymRunner (default: 3).",
    )
    parser.add_argument(
        "--warmup-iterations",
        "-w",
        type=int,
        default=5,
        help="Warmup iterations before each measured sample (default: 5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds per measured sample (default: 30).",
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=None,
        help="Base seed for deterministic runs. If set, each run gets a deterministic seed.",
    )
    parser.add_argument(
        "--seed-stride",
        type=int,
        default=None,
        help="Seed increment between repeated runs (default: samples).",
    )
    parser.add_argument(
        "--max-variants",
        type=int,
        default=None,
        help="Optional cap on number of discovered variants (after filtering).",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop repeated runs for a variant after the first failed run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only discover and print variants, do not execute benchmarks.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Alias for --dry-run.",
    )
    parser.add_argument(
        "--energy-mode",
        choices=["strict", "estimate"],
        default="strict",
        help=(
            "Energy handling when runner returns zero/missing energy:\n"
            "  strict   -> keep energy as unavailable\n"
            "  estimate -> estimate as wall_clock_seconds * assumed_power_watts"
        ),
    )
    parser.add_argument(
        "--assumed-power-watts",
        type=float,
        default=65.0,
        help="Power used for --energy-mode estimate (default: 65.0 W).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Disable plot generation (enabled by default).",
    )
    parser.add_argument(
        "--plot-format",
        choices=["png", "svg"],
        default="png",
        help="Output format for plots (default: png).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help=(
            "Output directory for results. "
            "Default: benchmark_results/evoeval_variant_bench_<timestamp>"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _parse_single_problem_token(token: str) -> List[int]:
    cleaned = token.strip()
    if not cleaned:
        return []
    if cleaned.isdigit():
        return [int(cleaned)]

    name_match = PROBLEM_DIR_PATTERN.match(cleaned)
    if name_match:
        return [int(name_match.group(1))]

    range_match = PROBLEM_RANGE_PATTERN.match(cleaned)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
        if start > end:
            start, end = end, start
        return list(range(start, end + 1))

    raise ValueError(
        f"Invalid problem token '{token}'. "
        "Use values like 4, EvoEval_difficult_4, 4,16, or 4-16."
    )


def parse_problem_filters(raw_filters: Sequence[str]) -> Set[int]:
    parsed: Set[int] = set()
    for item in raw_filters:
        if not item:
            continue
        for token in item.split(","):
            for problem_id in _parse_single_problem_token(token):
                parsed.add(problem_id)
    return parsed


def parse_sources(sources_arg: str) -> Set[str]:
    sources = {item.strip() for item in sources_arg.split(",") if item.strip()}
    invalid = sources - SUPPORTED_SOURCES
    if invalid:
        raise ValueError(
            f"Unsupported sources: {sorted(invalid)}. Supported: {sorted(SUPPORTED_SOURCES)}"
        )
    if not sources:
        raise ValueError("No valid sources provided.")
    return sources


def parse_problem_id_from_path(path: Path) -> Optional[int]:
    for part in path.parts:
        match = PROBLEM_DIR_PATTERN.match(part)
        if match:
            return int(match.group(1))

    match = SINGLE_PROMPT_PATTERN.match(path.name)
    if match:
        return int(match.group(1))
    return None


def resolve_test_path(repo_root: Path, problem_id: int) -> Optional[Path]:
    problem_name = f"EvoEval_difficult_{problem_id}"
    candidates = [
        repo_root / "evoeval_benchmark" / problem_name / "test_target.py",
        repo_root / "llm" / problem_name / "test_target.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_variant(
    repo_root: Path, code_path: Path, source_kind: str, source_name: str
) -> Optional[Variant]:
    problem_id = parse_problem_id_from_path(code_path)
    if problem_id is None:
        logger.warning("Could not infer problem id from %s; skipping", code_path)
        return None

    test_path = resolve_test_path(repo_root, problem_id)
    if test_path is None:
        logger.warning("Missing test_target.py for problem %s; skipping %s", problem_id, code_path)
        return None

    return Variant(
        problem_id=problem_id,
        source_kind=source_kind,
        source_name=source_name,
        code_path=code_path,
        test_path=test_path,
    )


def discover_variants(
    repo_root: Path,
    sources: Set[str],
    results_glob: str,
    problem_filters: Set[int],
    max_variants: Optional[int],
) -> List[Variant]:
    variants: List[Variant] = []

    if "benchmark" in sources:
        for code_path in sorted((repo_root / "evoeval_benchmark").glob("EvoEval_difficult_*/target.py")):
            variant = build_variant(repo_root, code_path, "benchmark", "benchmark")
            if variant:
                variants.append(variant)

    if "llm" in sources:
        for code_path in sorted((repo_root / "llm").glob("EvoEval_difficult_*/target.py")):
            variant = build_variant(repo_root, code_path, "llm", "llm")
            if variant:
                variants.append(variant)

    if "optimized" in sources:
        for results_dir in sorted(repo_root.glob(results_glob)):
            if not results_dir.is_dir():
                continue
            for code_path in sorted(results_dir.glob("EvoEval_difficult_*/optimized_target.py")):
                variant = build_variant(repo_root, code_path, "optimized", results_dir.name)
                if variant:
                    variants.append(variant)

    if "single_prompt" in sources:
        for code_path in sorted((repo_root / "single_prompt").glob("*/evo_eval_*.py")):
            variant = build_variant(repo_root, code_path, "single_prompt", code_path.parent.name)
            if variant:
                variants.append(variant)

    if problem_filters:
        variants = [variant for variant in variants if variant.problem_id in problem_filters]

    # Stable ordering for reproducibility.
    variants.sort(
        key=lambda item: (
            item.problem_id,
            item.source_kind,
            item.source_name,
            str(item.code_path),
        )
    )

    # De-duplicate exact repeats if any.
    deduped: List[Variant] = []
    seen: Set[Tuple[int, str, str, str]] = set()
    for variant in variants:
        key = (
            variant.problem_id,
            variant.source_kind,
            variant.source_name,
            str(variant.code_path.resolve()),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(variant)

    if max_variants is not None:
        deduped = deduped[: max(0, max_variants)]

    return deduped


def summarize_values(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "mean": None,
            "median": None,
            "stdev": None,
            "min": None,
            "max": None,
        }

    summary: Dict[str, Optional[float]] = {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }
    return summary


def _pick_metric(run_record: Dict[str, Any], name: str) -> Optional[float]:
    value = run_record.get(name)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _run_candidate_collect_metrics(
    runner: GreenGymRunner, code_str: str, test_code_str: str
) -> Tuple[bool, Dict[str, float], str, int]:
    """
    Execute one benchmark run while preserving numeric metrics even if tests fail.

    GreenGymRunner.run() drops metrics when any sample fails; for analysis we keep
    whatever metrics the harness emitted, then still report pass/fail separately.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        candidate_path = os.path.join(tmpdir, "candidate.py")
        with open(candidate_path, "w", encoding="utf-8") as handle:
            handle.write(code_str)

        harness_code = runner._get_harness_code(test_code_str, tmpdir)  # type: ignore[attr-defined]
        harness_path = os.path.join(tmpdir, "harness.py")
        with open(harness_path, "w", encoding="utf-8") as handle:
            handle.write(harness_code)

        all_metrics: Dict[str, List[float]] = {}
        success_count = 0
        last_output = ""

        for sample_index in range(runner.samples):
            iteration_seed: Optional[int] = None
            if runner.base_seed is not None:
                iteration_seed = runner.base_seed + sample_index

            success, metrics, output = runner._run_single_sample(  # type: ignore[attr-defined]
                harness_path,
                tmpdir,
                iteration_index=sample_index,
                iteration_seed=iteration_seed,
            )
            last_output = output
            if success:
                success_count += 1

            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    all_metrics.setdefault(key, []).append(float(value))

        overall_success = success_count == runner.samples
        aggregated = {key: sum(values) for key, values in all_metrics.items()}
        return overall_success, aggregated, last_output, success_count


def evaluate_variant(
    variant: Variant,
    runs: int,
    samples: int,
    warmup_iterations: int,
    timeout_seconds: int,
    base_seed: Optional[int],
    seed_stride: int,
    fail_fast: bool,
    energy_mode: str,
    assumed_power_watts: float,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    code_str = variant.code_path.read_text(encoding="utf-8")
    test_code_str = variant.test_path.read_text(encoding="utf-8")

    run_records: List[Dict[str, Any]] = []

    for run_index in range(runs):
        run_seed: Optional[int] = None
        if base_seed is not None:
            run_seed = base_seed + (run_index * seed_stride)

        runner = GreenGymRunner(
            timeout_seconds=timeout_seconds,
            samples=samples,
            warmup_iterations=warmup_iterations,
            base_seed=run_seed,
        )

        wall_start = time.perf_counter()
        success, metrics, output, sample_passes = _run_candidate_collect_metrics(
            runner,
            code_str,
            test_code_str,
        )
        wall_seconds = time.perf_counter() - wall_start

        record: Dict[str, Any] = {
            "run_index": run_index,
            "seed": run_seed,
            "success": success,
            "sample_passes": sample_passes,
            "sample_total": runner.samples,
            "wall_clock_seconds": wall_seconds,
        }
        record.update(metrics)

        if not success:
            record["output_tail"] = output[-800:]
        run_records.append(record)

        if fail_fast and not success:
            break

    successful_runs = [record for record in run_records if record.get("success")]
    success_count = len(successful_runs)
    attempted_runs = len(run_records)
    success_rate = (success_count / attempted_runs) if attempted_runs else 0.0

    if success_count == attempted_runs and attempted_runs == runs:
        status = "pass"
    elif success_count == 0:
        status = "fail"
    else:
        status = "flaky"

    measured_duration_values = [
        value
        for value in (_pick_metric(record, "duration_seconds") for record in run_records)
        if value is not None and value > 0
    ]
    if measured_duration_values:
        duration_values = measured_duration_values
        duration_source = "runner"
    else:
        duration_values = [record["wall_clock_seconds"] for record in run_records]
        duration_source = "wall_clock_fallback"

    measured_energy_values = [
        value
        for value in (_pick_metric(record, "energy_joules") for record in run_records)
        if value is not None and value > 0
    ]
    if measured_energy_values:
        energy_values = measured_energy_values
        energy_source = "runner"
    elif energy_mode == "estimate":
        energy_values = [record["wall_clock_seconds"] * assumed_power_watts for record in run_records]
        energy_source = f"estimated_{assumed_power_watts:.1f}W_wall_clock"
        for record in run_records:
            record["energy_joules_estimated"] = record["wall_clock_seconds"] * assumed_power_watts
    else:
        energy_values = []
        energy_source = "unavailable"

    emissions_values = [
        value
        for value in (_pick_metric(record, "emissions_kg") for record in run_records)
        if value is not None
    ]
    wall_values = [record["wall_clock_seconds"] for record in run_records]

    duration_summary = summarize_values(duration_values)
    energy_summary = summarize_values(energy_values)
    emissions_summary = summarize_values(emissions_values)
    wall_summary = summarize_values(wall_values)

    summary: Dict[str, Any] = {
        "problem_id": variant.problem_id,
        "problem_name": variant.problem_name,
        "variant_label": variant.variant_label,
        "source_kind": variant.source_kind,
        "source_name": variant.source_name,
        "code_path": str(variant.code_path),
        "test_path": str(variant.test_path),
        "status": status,
        "requested_runs": runs,
        "attempted_runs": attempted_runs,
        "successful_runs": success_count,
        "success_rate": success_rate,
        "samples_per_run": samples,
        "warmup_iterations": warmup_iterations,
        "timeout_seconds": timeout_seconds,
        "seed_stride": seed_stride,
        "duration_source": duration_source,
        "energy_source": energy_source,
        "energy_available": energy_source != "unavailable",
        "metrics_on_failed_runs": any(
            (not record.get("success")) and (
                _pick_metric(record, "duration_seconds") is not None
                or _pick_metric(record, "energy_joules") is not None
            )
            for record in run_records
        ),
    }

    for prefix, metric_summary in (
        ("duration_seconds", duration_summary),
        ("energy_joules", energy_summary),
        ("emissions_kg", emissions_summary),
        ("wall_clock_seconds", wall_summary),
    ):
        for stat_name, stat_value in metric_summary.items():
            summary[f"{prefix}_{stat_name}"] = stat_value

    return summary, run_records


def write_summary_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        with path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["no_data"])
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_output_dir(repo_root: Path, output_dir: Optional[Path]) -> Path:
    if output_dir is not None:
        target = output_dir if output_dir.is_absolute() else (repo_root / output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = repo_root / "benchmark_results" / f"evoeval_variant_bench_{timestamp}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def format_float(value: Optional[float], precision: int = 6) -> str:
    if value is None:
        return "NA"
    return f"{value:.{precision}f}"


def print_discovery_summary(variants: Sequence[Variant]) -> None:
    if not variants:
        print("No variants discovered.")
        return

    problems = sorted({variant.problem_id for variant in variants})
    print(f"Discovered {len(variants)} variants across {len(problems)} problem(s): {problems}")
    for variant in variants:
        print(
            f"- {variant.problem_name:>22} | {variant.variant_label:<32} | "
            f"{variant.code_path}"
        )


def print_result_summary(rows: Sequence[Dict[str, Any]], output_dir: Path) -> None:
    if not rows:
        print("No benchmark rows to summarize.")
        return

    print("\nBenchmark summary:")
    print(
        "problem | variant | status | success | duration_mean_s | energy_mean_j | energy_src | wall_mean_s"
    )
    for row in rows:
        success = f"{row['successful_runs']}/{row['attempted_runs']}"
        print(
            f"{row['problem_name']:<20} | {row['variant_label']:<28} | {row['status']:<5} | "
            f"{success:<7} | {format_float(row['duration_seconds_mean'], 6):>14} | "
            f"{format_float(row['energy_joules_mean'], 6):>13} | {row.get('energy_source', 'NA'):<20} | "
            f"{format_float(row['wall_clock_seconds_mean'], 6):>11}"
        )

    pass_rows = [row for row in rows if row.get("status") == "pass"]
    unavailable_energy = [row for row in rows if row.get("energy_source") == "unavailable"]
    print(f"\nPassing variants: {len(pass_rows)}/{len(rows)}")
    if unavailable_energy:
        print(f"Energy unavailable for {len(unavailable_energy)} variant(s).")
    print(f"Results written to: {output_dir}")


def _make_variant_name(row: Dict[str, Any]) -> str:
    return f"{row.get('problem_name', 'problem')}|{row.get('variant_label', 'variant')}"


def _safe_plot_values(
    rows: Sequence[Dict[str, Any]], metric_key: str
) -> List[Tuple[str, float, Dict[str, Any]]]:
    pairs: List[Tuple[str, float, Dict[str, Any]]] = []
    for row in rows:
        value = row.get(metric_key)
        if isinstance(value, (int, float)):
            pairs.append((_make_variant_name(row), float(value), row))
    return pairs


def _plot_sorted_barh(
    pairs: Sequence[Tuple[str, float, Dict[str, Any]]],
    title: str,
    xlabel: str,
    output_path: Path,
) -> None:
    if not pairs or not MATPLOTLIB_AVAILABLE:
        return
    sorted_pairs = sorted(pairs, key=lambda item: item[1])
    labels = [item[0] for item in sorted_pairs]
    values = [item[1] for item in sorted_pairs]

    fig_height = max(6, min(26, 0.35 * len(labels)))
    plt.figure(figsize=(14, fig_height))
    plt.barh(labels, values)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def _plot_pareto(rows: Sequence[Dict[str, Any]], output_path: Path) -> None:
    if not MATPLOTLIB_AVAILABLE:
        return

    points: List[Tuple[float, float, str, str]] = []
    for row in rows:
        duration = row.get("duration_seconds_mean")
        energy = row.get("energy_joules_mean")
        if isinstance(duration, (int, float)) and isinstance(energy, (int, float)):
            points.append(
                (
                    float(duration),
                    float(energy),
                    str(row.get("source_kind", "unknown")),
                    str(row.get("problem_id", "")),
                )
            )

    if not points:
        return

    source_kinds = sorted({point[2] for point in points})
    color_cycle = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
    ]
    source_colors = {
        source: color_cycle[idx % len(color_cycle)] for idx, source in enumerate(source_kinds)
    }

    plt.figure(figsize=(11, 8))
    for source in source_kinds:
        xs = [duration for duration, _, src, _ in points if src == source]
        ys = [energy for _, energy, src, _ in points if src == source]
        plt.scatter(xs, ys, s=52, alpha=0.85, label=source, color=source_colors[source])

    plt.title("Duration vs Energy (Lower is Better)")
    plt.xlabel("Duration (seconds)")
    plt.ylabel("Energy (joules)")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def _plot_source_summary(rows: Sequence[Dict[str, Any]], output_path: Path) -> None:
    if not MATPLOTLIB_AVAILABLE:
        return

    source_order = sorted({str(row.get("source_kind", "unknown")) for row in rows})
    if not source_order:
        return

    duration_means: List[float] = []
    energy_means: List[float] = []
    for source in source_order:
        source_rows = [row for row in rows if str(row.get("source_kind", "unknown")) == source]
        duration_values = [
            float(value)
            for value in (row.get("duration_seconds_mean") for row in source_rows)
            if isinstance(value, (int, float))
        ]
        energy_values = [
            float(value)
            for value in (row.get("energy_joules_mean") for row in source_rows)
            if isinstance(value, (int, float))
        ]
        duration_means.append(statistics.mean(duration_values) if duration_values else 0.0)
        energy_means.append(statistics.mean(energy_values) if energy_values else 0.0)

    x_positions = list(range(len(source_order)))
    width = 0.36
    plt.figure(figsize=(12, 6))
    plt.bar([x - width / 2 for x in x_positions], duration_means, width=width, label="Duration mean (s)")
    plt.bar([x + width / 2 for x in x_positions], energy_means, width=width, label="Energy mean (J)")
    plt.xticks(x_positions, source_order, rotation=20, ha="right")
    plt.title("Average Metrics by Source Type")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def generate_plots(
    rows: Sequence[Dict[str, Any]], output_dir: Path, plot_format: str
) -> Tuple[bool, List[Path]]:
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("matplotlib not available; skipping plot generation.")
        return False, []
    if not rows:
        return True, []

    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    generated: List[Path] = []

    duration_pairs = _safe_plot_values(rows, "duration_seconds_mean")
    duration_path = plots_dir / f"duration_by_variant.{plot_format}"
    _plot_sorted_barh(
        duration_pairs,
        "Duration by Variant (mean across runs)",
        "Duration (seconds)",
        duration_path,
    )
    if duration_pairs:
        generated.append(duration_path)

    energy_pairs = _safe_plot_values(rows, "energy_joules_mean")
    energy_path = plots_dir / f"energy_by_variant.{plot_format}"
    _plot_sorted_barh(
        energy_pairs,
        "Energy by Variant (mean across runs)",
        "Energy (joules)",
        energy_path,
    )
    if energy_pairs:
        generated.append(energy_path)

    pareto_path = plots_dir / f"pareto_duration_energy.{plot_format}"
    _plot_pareto(rows, pareto_path)
    if pareto_path.exists():
        generated.append(pareto_path)

    source_path = plots_dir / f"source_kind_summary.{plot_format}"
    _plot_source_summary(rows, source_path)
    if source_path.exists():
        generated.append(source_path)

    return True, generated


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)
    if args.list_only:
        args.dry_run = True

    if args.runs <= 0:
        raise ValueError("--runs must be >= 1")
    if args.samples <= 0:
        raise ValueError("--samples must be >= 1")
    if args.warmup_iterations < 0:
        raise ValueError("--warmup-iterations must be >= 0")
    if args.timeout <= 0:
        raise ValueError("--timeout must be >= 1")
    if args.assumed_power_watts <= 0:
        raise ValueError("--assumed-power-watts must be > 0")

    sources = parse_sources(args.sources)
    if args.baseline_only:
        sources = {"benchmark", "llm", "single_prompt"}

    raw_problem_filters = list(args.problems) + list(args.problem)
    problem_filters = parse_problem_filters(raw_problem_filters)
    seed_stride = args.seed_stride if args.seed_stride is not None else args.samples
    if seed_stride <= 0:
        raise ValueError("--seed-stride must be >= 1")

    repo_root = REPO_ROOT
    os.chdir(repo_root)
    output_dir = ensure_output_dir(repo_root, args.output_dir)

    variants = discover_variants(
        repo_root=repo_root,
        sources=sources,
        results_glob=args.results_glob,
        problem_filters=problem_filters,
        max_variants=args.max_variants,
    )
    print_discovery_summary(variants)

    metadata = {
        "generated_at": datetime.now().isoformat(),
        "repo_root": str(repo_root),
        "config": {
            "sources": sorted(sources),
            "baseline_only": args.baseline_only,
            "results_glob": args.results_glob,
            "problems": sorted(problem_filters),
            "runs": args.runs,
            "samples": args.samples,
            "warmup_iterations": args.warmup_iterations,
            "timeout_seconds": args.timeout,
            "base_seed": args.base_seed,
            "seed_stride": seed_stride,
            "energy_mode": args.energy_mode,
            "assumed_power_watts": args.assumed_power_watts,
            "plots_enabled": not args.no_plots,
            "plot_format": args.plot_format,
            "max_variants": args.max_variants,
            "fail_fast": args.fail_fast,
            "dry_run": args.dry_run,
        },
        "discovered_variants": [asdict(variant) for variant in variants],
    }

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    if args.dry_run:
        print(f"Dry run only. Metadata written to: {metadata_path}")
        return 0

    summary_rows: List[Dict[str, Any]] = []
    raw_variant_results: List[Dict[str, Any]] = []

    total_variants = len(variants)
    for index, variant in enumerate(variants, start=1):
        print(
            f"\n[{index}/{total_variants}] Running {variant.problem_name} "
            f"({variant.variant_label})"
        )
        summary, run_records = evaluate_variant(
            variant=variant,
            runs=args.runs,
            samples=args.samples,
            warmup_iterations=args.warmup_iterations,
            timeout_seconds=args.timeout,
            base_seed=args.base_seed,
            seed_stride=seed_stride,
            fail_fast=args.fail_fast,
            energy_mode=args.energy_mode,
            assumed_power_watts=args.assumed_power_watts,
        )
        summary_rows.append(summary)
        raw_variant_results.append(
            {
                "problem_id": variant.problem_id,
                "problem_name": variant.problem_name,
                "variant_label": variant.variant_label,
                "source_kind": variant.source_kind,
                "source_name": variant.source_name,
                "code_path": str(variant.code_path),
                "test_path": str(variant.test_path),
                "summary": summary,
                "runs": run_records,
            }
        )

    summary_json_path = output_dir / "summary.json"
    raw_json_path = output_dir / "raw_runs.json"
    summary_csv_path = output_dir / "summary.csv"

    summary_payload = {
        "generated_at": datetime.now().isoformat(),
        "total_variants": len(summary_rows),
        "rows": summary_rows,
    }
    summary_json_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    raw_json_path.write_text(
        json.dumps({"generated_at": datetime.now().isoformat(), "variants": raw_variant_results}, indent=2),
        encoding="utf-8",
    )
    write_summary_csv(summary_csv_path, summary_rows)

    generated_plots: List[Path] = []
    plots_requested = not args.no_plots
    if plots_requested:
        plots_generated, generated_plots = generate_plots(
            summary_rows,
            output_dir,
            args.plot_format,
        )
        if not plots_generated:
            print("Plot generation skipped (matplotlib not available).")

    print_result_summary(summary_rows, output_dir)
    print(f"Summary JSON: {summary_json_path}")
    print(f"Raw runs JSON: {raw_json_path}")
    print(f"Summary CSV:  {summary_csv_path}")
    for plot_path in generated_plots:
        print(f"Plot:        {plot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
