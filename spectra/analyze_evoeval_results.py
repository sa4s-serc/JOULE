#!/usr/bin/env python3
"""
Analyze outputs produced by run_evoeval_benchmarks.py.

By default this script:
1) Builds enriched run-level tables from run_summary + per-run metrics JSON.
2) Writes aggregate analysis CSVs + a markdown report.
3) Generates detailed plots (if matplotlib is available).

Typical usage:
  ./spectra/bin/python analyze_evoeval_results.py \
      --results-root evoeval_results_20260306_123456
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False


@dataclass
class RunRow:
    variant: str
    problem_id: str
    function_name: str
    status: str
    return_code: int | None
    duration_s: float | None
    baseline_mj: float | None
    best_mj: float | None
    improvement_pct: float | None
    f3_evals: int | None
    co2_search_ug: float | None
    wall_s_reported: float | None
    chain_len: int | None
    result_json: str | None
    metrics_json: str | None
    figures_dir: str | None
    command: str


def _problem_sort_key(name: str) -> tuple[int, str]:
    try:
        return (int(name.rsplit("_", 1)[1]), name)
    except Exception:
        return (10**9, name)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "" or s.lower() == "none":
        return None
    try:
        return float(s)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    fv = _to_float(v)
    return int(fv) if fv is not None else None


def _mean_or_none(vals: list[float]) -> float | None:
    return statistics.mean(vals) if vals else None


def _median_or_none(vals: list[float]) -> float | None:
    return statistics.median(vals) if vals else None


def _round_or_none(v: float | None, ndigits: int = 4) -> float | None:
    return round(v, ndigits) if v is not None else None


def _pct(n: float, d: float) -> float | None:
    if d == 0:
        return None
    return n / d * 100.0


def read_run_summary(path: Path) -> list[RunRow]:
    rows: list[RunRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                RunRow(
                    variant=r.get("variant", ""),
                    problem_id=r.get("problem_id", ""),
                    function_name=r.get("function_name", ""),
                    status=r.get("status", ""),
                    return_code=_to_int(r.get("return_code")),
                    duration_s=_to_float(r.get("duration_s")),
                    baseline_mj=_to_float(r.get("baseline_mj")),
                    best_mj=_to_float(r.get("best_mj")),
                    improvement_pct=_to_float(r.get("improvement_pct")),
                    f3_evals=_to_int(r.get("f3_evals")),
                    co2_search_ug=_to_float(r.get("co2_search_ug")),
                    wall_s_reported=_to_float(r.get("wall_s_reported")),
                    chain_len=_to_int(r.get("chain_len")),
                    result_json=(r.get("result_json") or None),
                    metrics_json=(r.get("metrics_json") or None),
                    figures_dir=(r.get("figures_dir") or None),
                    command=r.get("command", ""),
                )
            )
    return rows


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
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def safe_filename(s: str) -> str:
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def collect_run_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    iterations = metrics.get("iterations", []) or []
    total_generated = 0
    total_correct = 0
    total_screened_in = 0
    total_screened_out = 0
    total_f1 = 0
    total_f2 = 0
    total_f3 = 0
    total_confirmed = 0
    llm_generated = 0
    llm_confirmed = 0

    for it in iterations:
        total_generated += int(it.get("n_candidates_generated", 0))
        total_correct += int(it.get("n_correctness_pass", 0))
        total_screened_in += int(it.get("n_surrogate_screened_in", 0))
        total_screened_out += int(it.get("n_surrogate_screened_out", 0))
        for c in it.get("candidates", []) or []:
            is_llm = bool(c.get("is_llm", False))
            if is_llm:
                llm_generated += 1
            if c.get("f1_mj") is not None:
                total_f1 += 1
            if c.get("f2_mj") is not None:
                total_f2 += 1
            if c.get("f3_mj") is not None:
                total_f3 += 1
            if bool(c.get("confirmed_improvement", False)):
                total_confirmed += 1
                if is_llm:
                    llm_confirmed += 1

    return {
        "n_iterations": len(iterations),
        "total_candidates_generated": total_generated,
        "total_correctness_pass": total_correct,
        "total_surrogate_screened_in": total_screened_in,
        "total_surrogate_screened_out": total_screened_out,
        "total_f1_evals": total_f1,
        "total_f2_evals": total_f2,
        "total_f3_evals_from_candidates": total_f3,
        "total_confirmed_candidates": total_confirmed,
        "llm_generated_candidates": llm_generated,
        "llm_confirmed_candidates": llm_confirmed,
    }


def build_enriched_rows(run_rows: list[RunRow]) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    enriched: list[dict[str, Any]] = []
    metrics_cache: dict[tuple[str, str], dict[str, Any]] = {}

    for r in run_rows:
        extra = {
            "n_iterations": None,
            "total_candidates_generated": None,
            "total_correctness_pass": None,
            "total_surrogate_screened_in": None,
            "total_surrogate_screened_out": None,
            "total_f1_evals": None,
            "total_f2_evals": None,
            "total_f3_evals_from_candidates": None,
            "total_confirmed_candidates": None,
            "llm_generated_candidates": None,
            "llm_confirmed_candidates": None,
        }

        metrics_obj = None
        if r.metrics_json:
            metrics_path = Path(r.metrics_json)
            metrics_obj = read_json(metrics_path)
            if metrics_obj:
                extra = collect_run_metrics(metrics_obj)
                metrics_cache[(r.variant, r.problem_id)] = metrics_obj

        row = {
            "variant": r.variant,
            "problem_id": r.problem_id,
            "function_name": r.function_name,
            "status": r.status,
            "return_code": r.return_code,
            "duration_s": r.duration_s,
            "baseline_mj": r.baseline_mj,
            "best_mj": r.best_mj,
            "improvement_pct": r.improvement_pct,
            "f3_evals": r.f3_evals,
            "co2_search_ug": r.co2_search_ug,
            "wall_s_reported": r.wall_s_reported,
            "chain_len": r.chain_len,
            "result_json": r.result_json,
            "metrics_json": r.metrics_json,
            "figures_dir": r.figures_dir,
            "command": r.command,
            **extra,
        }
        enriched.append(row)

    return enriched, metrics_cache


def aggregate_variant_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    variants = sorted({r["variant"] for r in rows})
    out: list[dict[str, Any]] = []
    for v in variants:
        subset = [r for r in rows if r["variant"] == v]
        ok = [r for r in subset if r["status"] == "ok"]
        improvements = [r["improvement_pct"] for r in ok if r["improvement_pct"] is not None]
        durations = [r["duration_s"] for r in ok if r["duration_s"] is not None]
        co2 = [r["co2_search_ug"] for r in ok if r["co2_search_ug"] is not None]
        f3 = [r["f3_evals"] for r in ok if r["f3_evals"] is not None]
        cand = [r["total_candidates_generated"] for r in ok if r["total_candidates_generated"] is not None]
        correct = [r["total_correctness_pass"] for r in ok if r["total_correctness_pass"] is not None]
        confirmed = [r["total_confirmed_candidates"] for r in ok if r["total_confirmed_candidates"] is not None]

        correct_rate_vals = []
        confirm_rate_vals = []
        for r in ok:
            gen = r["total_candidates_generated"]
            cor = r["total_correctness_pass"]
            conf = r["total_confirmed_candidates"]
            if gen not in (None, 0) and cor is not None:
                correct_rate_vals.append(cor / gen * 100.0)
            f3_eval = r["total_f3_evals_from_candidates"]
            if f3_eval not in (None, 0) and conf is not None:
                confirm_rate_vals.append(conf / f3_eval * 100.0)

        out.append(
            {
                "variant": v,
                "runs_total": len(subset),
                "runs_ok": len(ok),
                "runs_failed_or_other": len(subset) - len(ok),
                "success_rate_pct": _round_or_none(_pct(len(ok), len(subset)), 2),
                "mean_improvement_pct": _round_or_none(_mean_or_none(improvements), 4),
                "median_improvement_pct": _round_or_none(_median_or_none(improvements), 4),
                "mean_duration_s": _round_or_none(_mean_or_none(durations), 4),
                "mean_co2_search_ug": _round_or_none(_mean_or_none(co2), 4),
                "sum_co2_search_ug": _round_or_none(sum(co2) if co2 else None, 4),
                "mean_f3_evals": _round_or_none(_mean_or_none([float(x) for x in f3]), 4),
                "mean_candidates_generated": _round_or_none(_mean_or_none([float(x) for x in cand]), 4),
                "mean_correctness_pass": _round_or_none(_mean_or_none([float(x) for x in correct]), 4),
                "mean_confirmed_candidates": _round_or_none(_mean_or_none([float(x) for x in confirmed]), 4),
                "mean_correctness_rate_pct": _round_or_none(_mean_or_none(correct_rate_vals), 4),
                "mean_confirmed_per_f3_pct": _round_or_none(_mean_or_none(confirm_rate_vals), 4),
            }
        )
    return out


def aggregate_operator_and_tier(rows: list[dict[str, Any]], metrics_cache: dict[tuple[str, str], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    op_stats: dict[tuple[str, str], dict[str, Any]] = {}
    tier_stats: dict[tuple[str, str], dict[str, Any]] = {}
    funnel_stats: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for r in rows:
        key = (r["variant"], r["problem_id"])
        m = metrics_cache.get(key)
        if not m:
            continue
        variant = r["variant"]
        for it in m.get("iterations", []) or []:
            funnel_stats[variant]["generated"] += float(it.get("n_candidates_generated", 0))
            funnel_stats[variant]["correct"] += float(it.get("n_correctness_pass", 0))
            funnel_stats[variant]["screened_in"] += float(it.get("n_surrogate_screened_in", 0))
            for c in it.get("candidates", []) or []:
                op = str(c.get("operator", "unknown"))
                tier = str(c.get("tier", "unknown"))
                op_key = (variant, op)
                tier_key = (variant, tier)
                if op_key not in op_stats:
                    op_stats[op_key] = {
                        "variant": variant,
                        "operator": op,
                        "tier": tier,
                        "is_llm": bool(c.get("is_llm", False)),
                        "generated": 0,
                        "correct_pass": 0,
                        "f1": 0,
                        "f2": 0,
                        "f3": 0,
                        "confirmed": 0,
                        "f3_improvements": [],
                    }
                if tier_key not in tier_stats:
                    tier_stats[tier_key] = {
                        "variant": variant,
                        "tier": tier,
                        "generated": 0,
                        "correct_pass": 0,
                        "f1": 0,
                        "f2": 0,
                        "f3": 0,
                        "confirmed": 0,
                        "f3_improvements": [],
                    }
                os = op_stats[op_key]
                ts = tier_stats[tier_key]
                os["generated"] += 1
                ts["generated"] += 1
                if bool(c.get("correctness_pass", False)):
                    os["correct_pass"] += 1
                    ts["correct_pass"] += 1
                if c.get("f1_mj") is not None:
                    os["f1"] += 1
                    ts["f1"] += 1
                if c.get("f2_mj") is not None:
                    os["f2"] += 1
                    ts["f2"] += 1
                if c.get("f3_mj") is not None:
                    os["f3"] += 1
                    ts["f3"] += 1
                    funnel_stats[variant]["f3"] += 1.0
                if bool(c.get("confirmed_improvement", False)):
                    os["confirmed"] += 1
                    ts["confirmed"] += 1
                    funnel_stats[variant]["confirmed"] += 1.0
                if c.get("f3_improvement_pct") is not None:
                    try:
                        v = float(c["f3_improvement_pct"])
                        os["f3_improvements"].append(v)
                        ts["f3_improvements"].append(v)
                    except Exception:
                        pass
                if c.get("f1_mj") is not None:
                    funnel_stats[variant]["f1"] += 1.0
                if c.get("f2_mj") is not None:
                    funnel_stats[variant]["f2"] += 1.0

    op_rows: list[dict[str, Any]] = []
    for s in op_stats.values():
        op_rows.append(
            {
                "variant": s["variant"],
                "operator": s["operator"],
                "tier": s["tier"],
                "is_llm": s["is_llm"],
                "generated": s["generated"],
                "correct_pass": s["correct_pass"],
                "correctness_rate_pct": _round_or_none(_pct(s["correct_pass"], s["generated"]), 4),
                "f1_count": s["f1"],
                "f2_count": s["f2"],
                "f3_count": s["f3"],
                "confirmed_count": s["confirmed"],
                "confirmed_per_f3_pct": _round_or_none(_pct(s["confirmed"], s["f3"]), 4),
                "mean_f3_improvement_pct": _round_or_none(_mean_or_none(s["f3_improvements"]), 4),
                "median_f3_improvement_pct": _round_or_none(_median_or_none(s["f3_improvements"]), 4),
            }
        )

    tier_rows: list[dict[str, Any]] = []
    for s in tier_stats.values():
        tier_rows.append(
            {
                "variant": s["variant"],
                "tier": s["tier"],
                "generated": s["generated"],
                "correct_pass": s["correct_pass"],
                "correctness_rate_pct": _round_or_none(_pct(s["correct_pass"], s["generated"]), 4),
                "f1_count": s["f1"],
                "f2_count": s["f2"],
                "f3_count": s["f3"],
                "confirmed_count": s["confirmed"],
                "confirmed_per_f3_pct": _round_or_none(_pct(s["confirmed"], s["f3"]), 4),
                "mean_f3_improvement_pct": _round_or_none(_mean_or_none(s["f3_improvements"]), 4),
                "median_f3_improvement_pct": _round_or_none(_median_or_none(s["f3_improvements"]), 4),
            }
        )

    funnel_rows: list[dict[str, Any]] = []
    for variant, f in sorted(funnel_stats.items()):
        generated = f.get("generated", 0.0)
        correct = f.get("correct", 0.0)
        screened_in = f.get("screened_in", 0.0)
        f1 = f.get("f1", 0.0)
        f2 = f.get("f2", 0.0)
        f3 = f.get("f3", 0.0)
        confirmed = f.get("confirmed", 0.0)
        funnel_rows.append(
            {
                "variant": variant,
                "generated": int(generated),
                "correct": int(correct),
                "screened_in": int(screened_in),
                "f1": int(f1),
                "f2": int(f2),
                "f3": int(f3),
                "confirmed": int(confirmed),
                "correct_pct_of_generated": _round_or_none(_pct(correct, generated), 4),
                "f3_pct_of_generated": _round_or_none(_pct(f3, generated), 4),
                "confirmed_pct_of_f3": _round_or_none(_pct(confirmed, f3), 4),
            }
        )

    op_rows.sort(key=lambda x: (x["variant"], -(x["confirmed_count"] or 0), -(x["generated"] or 0), x["operator"]))
    tier_rows.sort(key=lambda x: (x["variant"], x["tier"]))
    funnel_rows.sort(key=lambda x: x["variant"])
    return op_rows, tier_rows, funnel_rows


def aggregate_problem_variant(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "problem_id": r["problem_id"],
                "variant": r["variant"],
                "function_name": r["function_name"],
                "status": r["status"],
                "improvement_pct": r["improvement_pct"],
                "best_mj": r["best_mj"],
                "baseline_mj": r["baseline_mj"],
                "co2_search_ug": r["co2_search_ug"],
                "duration_s": r["duration_s"],
                "f3_evals": r["f3_evals"],
                "chain_len": r["chain_len"],
            }
        )
    out.sort(key=lambda x: (_problem_sort_key(x["problem_id"]), x["variant"]))
    return out


def _ensure_plots_available(no_plots: bool) -> None:
    if no_plots:
        return
    if not HAS_MATPLOTLIB:
        raise RuntimeError(
            "matplotlib is not available. Re-run with --no-plots or use ./spectra/bin/python."
        )


def _savefig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def plot_variant_improvement_box(rows: list[dict[str, Any]], out_dir: Path) -> None:
    variants = sorted({r["variant"] for r in rows})
    data = []
    labels = []
    for v in variants:
        vals = [r["improvement_pct"] for r in rows if r["variant"] == v and r["status"] == "ok" and r["improvement_pct"] is not None]
        if vals:
            data.append(vals)
            labels.append(v)
    if not data:
        return
    plt.figure(figsize=(10, 5))
    plt.boxplot(data, tick_labels=labels, patch_artist=True)
    plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
    plt.ylabel("Improvement (%)")
    plt.title("Improvement Distribution by Variant")
    plt.grid(axis="y", alpha=0.25)
    _savefig(out_dir / "variant_improvement_boxplot.png")


def plot_improvement_heatmap(rows: list[dict[str, Any]], out_dir: Path) -> None:
    problems = sorted({r["problem_id"] for r in rows}, key=_problem_sort_key)
    variants = sorted({r["variant"] for r in rows})
    if not problems or not variants:
        return

    matrix = []
    for p in problems:
        row_vals = []
        for v in variants:
            hits = [r for r in rows if r["problem_id"] == p and r["variant"] == v and r["status"] == "ok"]
            val = hits[0]["improvement_pct"] if hits and hits[0]["improvement_pct"] is not None else math.nan
            row_vals.append(val)
        matrix.append(row_vals)

    plt.figure(figsize=(max(8, len(variants) * 1.6), max(5, len(problems) * 0.55)))
    im = plt.imshow(matrix, aspect="auto", interpolation="nearest", cmap="RdYlGn")
    plt.colorbar(im, label="Improvement (%)")
    plt.xticks(range(len(variants)), variants, rotation=30, ha="right")
    plt.yticks(range(len(problems)), problems)
    plt.title("Improvement Heatmap (Problem x Variant)")

    for i in range(len(problems)):
        for j in range(len(variants)):
            v = matrix[i][j]
            txt = "NA" if math.isnan(v) else f"{v:.2f}"
            plt.text(j, i, txt, ha="center", va="center", fontsize=7)
    _savefig(out_dir / "improvement_heatmap.png")


def plot_scatter_improvement_vs_co2(rows: list[dict[str, Any]], out_dir: Path) -> None:
    ok = [r for r in rows if r["status"] == "ok" and r["improvement_pct"] is not None and r["co2_search_ug"] is not None]
    if not ok:
        return
    variants = sorted({r["variant"] for r in ok})
    colors = plt.get_cmap("tab10")
    plt.figure(figsize=(9, 6))
    for i, v in enumerate(variants):
        subset = [r for r in ok if r["variant"] == v]
        xs = [r["co2_search_ug"] for r in subset]
        ys = [r["improvement_pct"] for r in subset]
        plt.scatter(xs, ys, label=v, alpha=0.75, color=colors(i % 10))
    plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
    plt.xlabel("Search CO2 (ug)")
    plt.ylabel("Improvement (%)")
    plt.title("Efficiency Frontier: Improvement vs Search CO2")
    plt.grid(alpha=0.25)
    plt.legend()
    _savefig(out_dir / "improvement_vs_co2_scatter.png")


def plot_variant_bars(variant_rows: list[dict[str, Any]], out_dir: Path) -> None:
    if not variant_rows:
        return
    variants = [r["variant"] for r in variant_rows]
    mean_imp = [r["mean_improvement_pct"] if r["mean_improvement_pct"] is not None else 0.0 for r in variant_rows]
    mean_dur = [r["mean_duration_s"] if r["mean_duration_s"] is not None else 0.0 for r in variant_rows]
    mean_f3 = [r["mean_f3_evals"] if r["mean_f3_evals"] is not None else 0.0 for r in variant_rows]
    success = [r["success_rate_pct"] if r["success_rate_pct"] is not None else 0.0 for r in variant_rows]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    axes[0].bar(variants, mean_imp)
    axes[0].axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
    axes[0].set_title("Mean Improvement (%)")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(variants, mean_dur)
    axes[1].set_title("Mean Runtime per Run (s)")
    axes[1].tick_params(axis="x", rotation=20)

    axes[2].bar(variants, mean_f3)
    axes[2].set_title("Mean F3 Evals")
    axes[2].tick_params(axis="x", rotation=20)

    axes[3].bar(variants, success)
    axes[3].set_title("Success Rate (%)")
    axes[3].tick_params(axis="x", rotation=20)

    for ax in axes:
        ax.grid(axis="y", alpha=0.25)

    plt.suptitle("Variant-Level Summary")
    _savefig(out_dir / "variant_summary_bars.png")


def plot_funnel(funnel_rows: list[dict[str, Any]], out_dir: Path) -> None:
    if not funnel_rows:
        return
    stages = ["generated", "correct", "screened_in", "f1", "f2", "f3", "confirmed"]
    variants = [r["variant"] for r in funnel_rows]
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, v in enumerate(variants):
        vals = [funnel_rows[i][s] for s in stages]
        ax.plot(stages, vals, marker="o", label=v)
    ax.set_title("Candidate Funnel by Variant")
    ax.set_ylabel("Count")
    ax.grid(alpha=0.25)
    ax.legend()
    _savefig(out_dir / "candidate_funnel_by_variant.png")


def plot_top_operators(op_rows: list[dict[str, Any]], out_dir: Path, top_n: int) -> None:
    if not op_rows:
        return
    combined: dict[str, dict[str, Any]] = {}
    for r in op_rows:
        op = r["operator"]
        if op not in combined:
            combined[op] = {
                "operator": op,
                "generated": 0,
                "confirmed": 0,
                "f3": 0,
                "weighted_improvement": 0.0,
                "weight_count": 0,
            }
        c = combined[op]
        c["generated"] += int(r["generated"] or 0)
        c["confirmed"] += int(r["confirmed_count"] or 0)
        c["f3"] += int(r["f3_count"] or 0)
        imp = r["mean_f3_improvement_pct"]
        if imp is not None and r["f3_count"]:
            c["weighted_improvement"] += float(imp) * int(r["f3_count"])
            c["weight_count"] += int(r["f3_count"])

    agg = []
    for c in combined.values():
        mean_imp = (c["weighted_improvement"] / c["weight_count"]) if c["weight_count"] else None
        agg.append(
            {
                "operator": c["operator"],
                "generated": c["generated"],
                "confirmed": c["confirmed"],
                "f3": c["f3"],
                "mean_f3_improvement_pct": mean_imp,
            }
        )
    agg.sort(key=lambda x: (x["confirmed"], x["generated"]), reverse=True)
    agg = agg[:top_n]
    if not agg:
        return
    ops = [x["operator"] for x in agg]
    confirmed = [x["confirmed"] for x in agg]
    mean_imp = [x["mean_f3_improvement_pct"] if x["mean_f3_improvement_pct"] is not None else 0.0 for x in agg]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].barh(ops, confirmed)
    axes[0].invert_yaxis()
    axes[0].set_title("Top Operators by Confirmed Improvements")
    axes[0].set_xlabel("Confirmed Count")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(ops, mean_imp)
    axes[1].invert_yaxis()
    axes[1].set_title("Top Operators by Mean F3 Improvement (%)")
    axes[1].set_xlabel("Mean F3 Improvement (%)")
    axes[1].grid(axis="x", alpha=0.25)
    _savefig(out_dir / "operator_effectiveness.png")


def plot_tier_summary(tier_rows: list[dict[str, Any]], out_dir: Path) -> None:
    if not tier_rows:
        return
    combined: dict[str, dict[str, Any]] = {}
    for r in tier_rows:
        tier = r["tier"]
        if tier not in combined:
            combined[tier] = {"generated": 0, "f3": 0, "confirmed": 0}
        combined[tier]["generated"] += int(r["generated"] or 0)
        combined[tier]["f3"] += int(r["f3_count"] or 0)
        combined[tier]["confirmed"] += int(r["confirmed_count"] or 0)
    tiers = sorted(combined.keys())
    generated = [combined[t]["generated"] for t in tiers]
    f3 = [combined[t]["f3"] for t in tiers]
    confirmed = [combined[t]["confirmed"] for t in tiers]

    x = list(range(len(tiers)))
    width = 0.25
    plt.figure(figsize=(9, 5))
    plt.bar([i - width for i in x], generated, width=width, label="generated")
    plt.bar(x, f3, width=width, label="f3")
    plt.bar([i + width for i in x], confirmed, width=width, label="confirmed")
    plt.xticks(x, tiers)
    plt.title("Tier-Level Outcome Counts")
    plt.ylabel("Count")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    _savefig(out_dir / "tier_outcomes.png")


def plot_problem_trajectories(metrics_cache: dict[tuple[str, str], dict[str, Any]], out_dir: Path) -> int:
    by_problem: dict[str, dict[str, list[float]]] = defaultdict(dict)
    for (variant, problem_id), metrics in metrics_cache.items():
        vals = []
        for it in metrics.get("iterations", []) or []:
            v = it.get("improvement_over_baseline_pct")
            if v is not None:
                try:
                    vals.append(float(v))
                except Exception:
                    pass
        if vals:
            by_problem[problem_id][variant] = vals

    count = 0
    for problem_id in sorted(by_problem.keys(), key=_problem_sort_key):
        variant_map = by_problem[problem_id]
        if not variant_map:
            continue
        plt.figure(figsize=(9, 5))
        for variant in sorted(variant_map.keys()):
            ys = variant_map[variant]
            xs = list(range(1, len(ys) + 1))
            plt.plot(xs, ys, marker="o", label=variant)
        plt.axhline(0.0, color="gray", linestyle="--", linewidth=1.0)
        plt.xlabel("Iteration")
        plt.ylabel("Running Improvement over Baseline (%)")
        plt.title(f"Trajectory: {problem_id}")
        plt.grid(alpha=0.25)
        plt.legend()
        fname = safe_filename(problem_id) + "_trajectory.png"
        _savefig(out_dir / "problem_trajectories" / fname)
        count += 1
    return count


def write_report(
    report_path: Path,
    results_root: Path,
    rows: list[dict[str, Any]],
    variant_rows: list[dict[str, Any]],
    op_rows: list[dict[str, Any]],
    tier_rows: list[dict[str, Any]],
    funnel_rows: list[dict[str, Any]],
    generated_plot_files: list[Path],
) -> None:
    total = len(rows)
    ok = [r for r in rows if r["status"] == "ok"]
    failed = [r for r in rows if r["status"] != "ok"]
    best_run = None
    best_runs = [r for r in ok if r["improvement_pct"] is not None]
    if best_runs:
        best_run = max(best_runs, key=lambda x: float(x["improvement_pct"]))

    best_variant = None
    with_means = [r for r in variant_rows if r["mean_improvement_pct"] is not None]
    if with_means:
        best_variant = max(with_means, key=lambda x: float(x["mean_improvement_pct"]))

    lines = []
    lines.append("# EvoEval Benchmark Analysis")
    lines.append("")
    lines.append(f"- Results root: `{results_root}`")
    lines.append(f"- Total runs: **{total}**")
    lines.append(f"- Successful runs (`status=ok`): **{len(ok)}**")
    lines.append(f"- Non-ok runs: **{len(failed)}**")
    lines.append("")

    if best_variant:
        lines.append("## Best Variant (By Mean Improvement)")
        lines.append(
            f"- `{best_variant['variant']}` with mean improvement "
            f"`{best_variant['mean_improvement_pct']:.4f}%`"
        )
        lines.append("")

    if best_run:
        lines.append("## Best Single Run")
        lines.append(
            f"- `{best_run['variant']}` on `{best_run['problem_id']}` (`{best_run['function_name']}`): "
            f"`{best_run['improvement_pct']:.4f}%` improvement"
        )
        lines.append("")

    lines.append("## Output Files")
    lines.append("- `analysis/enriched_run_summary.csv`")
    lines.append("- `analysis/variant_summary.csv`")
    lines.append("- `analysis/problem_variant_summary.csv`")
    lines.append("- `analysis/operator_summary.csv`")
    lines.append("- `analysis/tier_summary.csv`")
    lines.append("- `analysis/funnel_summary.csv`")
    if generated_plot_files:
        lines.append("- Plot files:")
        for p in sorted(generated_plot_files):
            lines.append(f"  - `{p}`")
    lines.append("")

    lines.append("## Notes")
    lines.append("- `operator_summary.csv` and `tier_summary.csv` aggregate candidate-level signals from metrics JSON.")
    lines.append("- Funnel stages use SPECTRA iteration/candidate traces (generated -> correctness -> screened -> F1/F2/F3 -> confirmed).")
    lines.append("- Per-problem trajectories plot `improvement_over_baseline_pct` over optimization iterations.")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate detailed analysis and plots for EvoEval benchmark runs.")
    parser.add_argument("--results-root", required=True, help="Path to a run_evoeval_benchmarks output root")
    parser.add_argument("--out-dir", default=None, help="Output analysis directory (default: <results-root>/analysis)")
    parser.add_argument("--top-n-operators", type=int, default=12, help="Top N operators to show in operator plot")
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    parser.add_argument(
        "--include-non-ok",
        action="store_true",
        help="Include non-ok runs in numeric summaries (default: summaries use only ok runs where needed)",
    )
    args = parser.parse_args()

    _ensure_plots_available(args.no_plots)

    results_root = Path(args.results_root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (results_root / "analysis")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_summary_csv = results_root / "summaries" / "run_summary.csv"
    if not run_summary_csv.exists():
        raise FileNotFoundError(f"run_summary.csv not found at: {run_summary_csv}")

    run_rows = read_run_summary(run_summary_csv)
    if not run_rows:
        raise ValueError(f"No rows found in {run_summary_csv}")

    enriched_rows, metrics_cache = build_enriched_rows(run_rows)
    selected_rows = enriched_rows if args.include_non_ok else [r for r in enriched_rows if r["status"] == "ok"]
    if not selected_rows:
        raise ValueError("No rows selected for analysis after filtering.")

    variant_rows = aggregate_variant_summary(selected_rows)
    op_rows, tier_rows, funnel_rows = aggregate_operator_and_tier(selected_rows, metrics_cache)
    problem_variant_rows = aggregate_problem_variant(selected_rows)

    write_csv(
        out_dir / "enriched_run_summary.csv",
        enriched_rows,
        fieldnames=list(enriched_rows[0].keys()),
    )
    write_csv(
        out_dir / "variant_summary.csv",
        variant_rows,
        fieldnames=list(variant_rows[0].keys()) if variant_rows else ["variant"],
    )
    write_csv(
        out_dir / "problem_variant_summary.csv",
        problem_variant_rows,
        fieldnames=list(problem_variant_rows[0].keys()) if problem_variant_rows else ["problem_id"],
    )
    write_csv(
        out_dir / "operator_summary.csv",
        op_rows,
        fieldnames=list(op_rows[0].keys()) if op_rows else ["variant", "operator"],
    )
    write_csv(
        out_dir / "tier_summary.csv",
        tier_rows,
        fieldnames=list(tier_rows[0].keys()) if tier_rows else ["variant", "tier"],
    )
    write_csv(
        out_dir / "funnel_summary.csv",
        funnel_rows,
        fieldnames=list(funnel_rows[0].keys()) if funnel_rows else ["variant"],
    )

    plot_files: list[Path] = []
    if not args.no_plots:
        plots_dir = out_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        before = set(plots_dir.rglob("*.png"))
        plot_variant_improvement_box(selected_rows, plots_dir)
        plot_improvement_heatmap(selected_rows, plots_dir)
        plot_scatter_improvement_vs_co2(selected_rows, plots_dir)
        plot_variant_bars(variant_rows, plots_dir)
        plot_funnel(funnel_rows, plots_dir)
        plot_top_operators(op_rows, plots_dir, top_n=max(1, args.top_n_operators))
        plot_tier_summary(tier_rows, plots_dir)
        plot_problem_trajectories(metrics_cache, plots_dir)
        after = set(plots_dir.rglob("*.png"))
        plot_files = sorted(after - before)

    write_report(
        report_path=out_dir / "analysis_report.md",
        results_root=results_root,
        rows=selected_rows,
        variant_rows=variant_rows,
        op_rows=op_rows,
        tier_rows=tier_rows,
        funnel_rows=funnel_rows,
        generated_plot_files=plot_files,
    )

    print(f"Analysis complete: {out_dir}")
    print(f"Rows analyzed: {len(selected_rows)}")
    print(f"Variant summaries: {len(variant_rows)}")
    print(f"Operator summaries: {len(op_rows)}")
    print(f"Tier summaries: {len(tier_rows)}")
    if not args.no_plots:
        print(f"Plot files generated: {len(plot_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
