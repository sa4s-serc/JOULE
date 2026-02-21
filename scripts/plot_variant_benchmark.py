#!/usr/bin/env python3
"""
Generate a detailed, insightful plot suite from a benchmark_evoeval_variants run.

Usage:
    python scripts/plot_variant_benchmark.py <path/to/summary.json>
    python scripts/plot_variant_benchmark.py          # auto-finds latest run

Outputs all plots to <summary_dir>/insight_plots/  and prints a summary to stdout.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np

# ---------------------------------------------------------------------------
# Palette & labels
# ---------------------------------------------------------------------------

VARIANT_ORDER = [
    "benchmark",
    "optimized:evoeval_results_20260219_225745",
    "single_prompt:gemini",
    "single_prompt:gemini_code_exe",
]

VARIANT_SHORT = {
    "benchmark":                                    "Baseline",
    "optimized:evoeval_results_20260219_225745":    "Hedge\n(Optimized)",
    "single_prompt:gemini":                         "Gemini\nSingle-Prompt",
    "single_prompt:gemini_code_exe":                "Gemini\nCode-Exe",
}

VARIANT_COLOR = {
    "benchmark":                                    "#6c757d",
    "optimized:evoeval_results_20260219_225745":    "#0d6efd",
    "single_prompt:gemini":                         "#198754",
    "single_prompt:gemini_code_exe":                "#fd7e14",
}

METRICS = {
    "duration_seconds_mean":    ("Exec Duration",       "seconds",  False),
    "energy_joules_mean":       ("Energy Consumed",     "joules",   False),
    "emissions_kg_mean":        ("CO₂ Emissions",       "kg",       False),
    "wall_clock_seconds_mean":  ("Wall-Clock Time",     "seconds",  False),
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.alpha": 0.3,
    "figure.dpi": 150,
})


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_data(summary_path: Path) -> list[dict]:
    with open(summary_path) as f:
        data = json.load(f)
    return data["rows"]


def as_df(rows: list[dict]):
    """Return a dict-of-lists view, sorted by problem_id then variant."""
    problems = sorted(set(r["problem_id"] for r in rows))
    variants = [v for v in VARIANT_ORDER if any(r["variant_label"] == v for r in rows)]
    # index: (problem_id, variant_label) -> row
    idx = {(r["problem_id"], r["variant_label"]): r for r in rows}
    return problems, variants, idx


def pct_change(new_val: float, base_val: float) -> float:
    """Positive = improvement (lower is better)."""
    if base_val == 0:
        return 0.0
    return (base_val - new_val) / base_val * 100.0


# ---------------------------------------------------------------------------
# 1. Grouped bar chart – raw metrics per problem
# ---------------------------------------------------------------------------

def plot_grouped_bars(problems, variants, idx, out_dir: Path):
    metric_keys = list(METRICS.keys())
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle("Raw Metric Values by Problem & Variant", fontsize=15, fontweight="bold", y=1.01)

    x = np.arange(len(problems))
    n = len(variants)
    width = 0.18
    offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * width

    for ax, mk in zip(axes.flat, metric_keys):
        label, unit, _ = METRICS[mk]
        stdev_key = mk.replace("_mean", "_stdev")
        for i, var in enumerate(variants):
            vals, errs = [], []
            for pid in problems:
                row = idx.get((pid, var))
                vals.append(row[mk] if row else float("nan"))
                errs.append(row.get(stdev_key, 0) if row else 0)
            bars = ax.bar(
                x + offsets[i], vals, width,
                label=VARIANT_SHORT[var].replace("\n", " "),
                color=VARIANT_COLOR[var], alpha=0.85,
                yerr=errs, capsize=3, error_kw={"elinewidth": 1.2}
            )
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.set_xlabel("Problem ID")
        ax.set_ylabel(unit)
        ax.set_xticks(x)
        ax.set_xticklabels([f"P{p}" for p in problems], fontsize=9)
        ax.legend(fontsize=8, loc="upper right")

    fig.tight_layout()
    out = out_dir / "01_grouped_bars_raw_metrics.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 2. Improvement heatmap vs baseline
# ---------------------------------------------------------------------------

def plot_improvement_heatmap(problems, variants, idx, out_dir: Path):
    non_baseline = [v for v in variants if v != "benchmark"]
    metric_keys = list(METRICS.keys())

    # Build matrix: rows = (variant × metric), cols = problems
    row_labels = []
    matrix = []

    for var in non_baseline:
        for mk in metric_keys:
            label, _, _ = METRICS[mk]
            row_labels.append(f"{VARIANT_SHORT[var].replace(chr(10),' ')} | {label}")
            vals = []
            for pid in problems:
                base = idx.get((pid, "benchmark"))
                row = idx.get((pid, var))
                if base and row:
                    vals.append(pct_change(row[mk], base[mk]))
                else:
                    vals.append(float("nan"))
            matrix.append(vals)

    mat = np.array(matrix)
    fig, ax = plt.subplots(figsize=(14, max(6, len(row_labels) * 0.55 + 1.5)))
    vmax = max(abs(np.nanmin(mat)), abs(np.nanmax(mat)), 5)
    im = ax.imshow(mat, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(problems)))
    ax.set_xticklabels([f"P{p}" for p in problems], fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8)

    # Annotate cells
    for i in range(len(row_labels)):
        for j in range(len(problems)):
            val = mat[i, j]
            if not math.isnan(val):
                sign = "+" if val >= 0 else ""
                ax.text(j, i, f"{sign}{val:.1f}%", ha="center", va="center",
                        fontsize=7, color="black" if abs(val) < vmax * 0.6 else "white")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("% improvement vs baseline\n(positive = better)", fontsize=9)

    # Draw separator lines between variant groups
    for k in range(1, len(non_baseline)):
        ax.axhline(k * len(metric_keys) - 0.5, color="white", linewidth=2)

    ax.set_title("% Improvement vs Baseline — All Variants × Metrics × Problems",
                 fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    out = out_dir / "02_improvement_heatmap.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 3. Pareto front – Energy vs Duration with error ellipses
# ---------------------------------------------------------------------------

def plot_pareto(problems, variants, idx, out_dir: Path):
    fig, ax = plt.subplots(figsize=(11, 7))

    for var in variants:
        xs, ys, labels = [], [], []
        xerrs, yerrs = [], []
        for pid in problems:
            row = idx.get((pid, var))
            if row:
                xs.append(row["duration_seconds_mean"])
                ys.append(row["energy_joules_mean"])
                xerrs.append(row.get("duration_seconds_stdev", 0))
                yerrs.append(row.get("energy_joules_stdev", 0))
                labels.append(f"P{pid}")

        ax.errorbar(
            xs, ys, xerr=xerrs, yerr=yerrs,
            fmt="o", color=VARIANT_COLOR[var],
            label=VARIANT_SHORT[var].replace("\n", " "),
            capsize=4, markersize=8, alpha=0.8, elinewidth=1.2
        )
        for x, y, lbl in zip(xs, ys, labels):
            ax.annotate(lbl, (x, y), textcoords="offset points",
                        xytext=(5, 4), fontsize=7, color=VARIANT_COLOR[var])

    ax.set_xlabel("Execution Duration (seconds)", fontsize=11)
    ax.set_ylabel("Energy Consumed (joules)", fontsize=11)
    ax.set_title("Pareto Space: Execution Duration vs Energy\n(lower-left = better)",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=9, loc="upper left")

    # Arrow annotation
    ax.annotate("", xy=(ax.get_xlim()[0] * 1.02, ax.get_ylim()[0] * 1.02),
                xytext=(ax.get_xlim()[0] * 1.12, ax.get_ylim()[0] * 1.12),
                arrowprops=dict(arrowstyle="->", color="gray"))
    ax.text(ax.get_xlim()[0] * 1.13, ax.get_ylim()[0] * 1.02, "Better", color="gray", fontsize=9)

    fig.tight_layout()
    out = out_dir / "03_pareto_duration_energy.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 4. Box/violin of % improvements per variant across problems
# ---------------------------------------------------------------------------

def plot_improvement_distributions(problems, variants, idx, out_dir: Path):
    non_baseline = [v for v in variants if v != "benchmark"]
    metric_keys = list(METRICS.keys())

    fig, axes = plt.subplots(1, len(metric_keys), figsize=(18, 6), sharey=False)
    fig.suptitle("Distribution of % Improvement vs Baseline Across Problems",
                 fontsize=13, fontweight="bold")

    for ax, mk in zip(axes, metric_keys):
        label, unit, _ = METRICS[mk]
        data_per_var = []
        colors = []
        for var in non_baseline:
            vals = []
            for pid in problems:
                base = idx.get((pid, "benchmark"))
                row = idx.get((pid, var))
                if base and row:
                    vals.append(pct_change(row[mk], base[mk]))
            data_per_var.append(vals)
            colors.append(VARIANT_COLOR[var])

        parts = ax.violinplot(data_per_var, positions=range(len(non_baseline)),
                              showmeans=True, showmedians=True)
        for pc, col in zip(parts["bodies"], colors):
            pc.set_facecolor(col)
            pc.set_alpha(0.6)
        for line_key in ("cmeans", "cmedians", "cbars", "cmins", "cmaxes"):
            if line_key in parts:
                parts[line_key].set_color("black")
                parts[line_key].set_linewidth(1.2)

        # Overlay scatter
        for i, (var, vals) in enumerate(zip(non_baseline, data_per_var)):
            jitter = np.random.default_rng(42).uniform(-0.08, 0.08, len(vals))
            ax.scatter(np.full(len(vals), i) + jitter, vals,
                       color=VARIANT_COLOR[var], s=40, zorder=3, alpha=0.9)

        ax.axhline(0, color="gray", linestyle="--", linewidth=1.2, alpha=0.7)
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_ylabel("% improvement (positive = better)")
        ax.set_xticks(range(len(non_baseline)))
        ax.set_xticklabels(
            [VARIANT_SHORT[v].replace("\n", " ") for v in non_baseline],
            fontsize=8, rotation=15, ha="right"
        )

    fig.tight_layout()
    out = out_dir / "04_improvement_violin.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 5. Per-problem small multiples – all metrics, all variants
# ---------------------------------------------------------------------------

def plot_per_problem_multiples(problems, variants, idx, out_dir: Path):
    metric_keys = list(METRICS.keys())
    n_prob = len(problems)
    n_met = len(metric_keys)
    fig, axes = plt.subplots(n_prob, n_met, figsize=(n_met * 4.5, n_prob * 2.8),
                             sharex=False, sharey=False)
    fig.suptitle("Per-Problem Detail: All Metrics × All Variants", fontsize=14,
                 fontweight="bold", y=1.002)

    x = np.arange(len(variants))
    width = 0.6

    for r, pid in enumerate(problems):
        for c, mk in enumerate(metric_keys):
            ax = axes[r, c]
            label, unit, _ = METRICS[mk]
            stdev_key = mk.replace("_mean", "_stdev")
            vals = [idx[(pid, v)][mk] if (pid, v) in idx else float("nan") for v in variants]
            errs = [idx[(pid, v)].get(stdev_key, 0) if (pid, v) in idx else 0 for v in variants]
            colors = [VARIANT_COLOR[v] for v in variants]

            bars = ax.bar(x, vals, width, color=colors, alpha=0.85,
                          yerr=errs, capsize=3, error_kw={"elinewidth": 1})

            # Mark baseline with dashed line
            base_val = idx.get((pid, "benchmark"), {}).get(mk)
            if base_val:
                ax.axhline(base_val, color="#6c757d", linestyle="--",
                           linewidth=1.2, alpha=0.7)

            if r == 0:
                ax.set_title(label, fontsize=9, fontweight="bold")
            if c == 0:
                ax.set_ylabel(f"P{pid}\n{unit}", fontsize=8)
            else:
                ax.set_ylabel(unit, fontsize=7)
            ax.set_xticks([])
            ax.tick_params(axis="y", labelsize=7)

    # Legend
    patches = [mpatches.Patch(color=VARIANT_COLOR[v],
                               label=VARIANT_SHORT[v].replace("\n", " "))
               for v in variants]
    fig.legend(handles=patches, loc="lower center", ncol=len(variants),
               fontsize=9, bbox_to_anchor=(0.5, -0.02))

    fig.tight_layout()
    out = out_dir / "05_per_problem_multiples.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 6. Win-rate: per metric, how often each variant beats baseline
# ---------------------------------------------------------------------------

def plot_win_rate(problems, variants, idx, out_dir: Path):
    non_baseline = [v for v in variants if v != "benchmark"]
    metric_keys = list(METRICS.keys())

    win_counts = {mk: {v: 0 for v in non_baseline} for mk in metric_keys}
    best_counts = {mk: {v: 0 for v in non_baseline} for mk in metric_keys}

    for pid in problems:
        for mk in metric_keys:
            base_row = idx.get((pid, "benchmark"))
            if not base_row:
                continue
            base_val = base_row[mk]
            non_base_rows = {v: idx.get((pid, v)) for v in non_baseline}
            non_base_vals = {v: r[mk] for v, r in non_base_rows.items() if r}

            # Beat baseline
            for v, val in non_base_vals.items():
                if val < base_val:
                    win_counts[mk][v] += 1

            # Best among all variants
            all_vals = {v: val for v, val in non_base_vals.items()}
            all_vals["benchmark"] = base_val
            best_var = min(all_vals, key=all_vals.get)
            if best_var in non_baseline:
                best_counts[mk][best_var] += 1

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Variant Win-Rate Analysis", fontsize=13, fontweight="bold")

    x = np.arange(len(metric_keys))
    n = len(non_baseline)
    width = 0.18
    offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * width

    for ax, counts, title in [
        (axes[0], win_counts, "Beats Baseline (count of problems)"),
        (axes[1], best_counts, "Best Overall — incl. baseline (count of problems)"),
    ]:
        for i, var in enumerate(non_baseline):
            vals = [counts[mk][var] for mk in metric_keys]
            ax.bar(x + offsets[i], vals, width,
                   label=VARIANT_SHORT[var].replace("\n", " "),
                   color=VARIANT_COLOR[var], alpha=0.85)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels([METRICS[mk][0] for mk in metric_keys], fontsize=9, rotation=12)
        ax.set_ylabel(f"# problems (out of {len(problems)})")
        ax.set_ylim(0, len(problems) + 0.5)
        ax.axhline(len(problems) / 2, color="gray", linestyle=":", alpha=0.7)
        ax.legend(fontsize=8)

    fig.tight_layout()
    out = out_dir / "06_win_rate.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 7. Variability (stdev) comparison — consistency analysis
# ---------------------------------------------------------------------------

def plot_variability(problems, variants, idx, out_dir: Path):
    metric_keys = ["duration_seconds_stdev", "energy_joules_stdev"]
    display = {"duration_seconds_stdev": "Duration Stdev (s)",
               "energy_joules_stdev":    "Energy Stdev (J)"}

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Measurement Variability (Stdev) — Lower = More Reliable",
                 fontsize=13, fontweight="bold")

    x = np.arange(len(problems))
    n = len(variants)
    width = 0.18
    offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * width

    for ax, sk in zip(axes, metric_keys):
        for i, var in enumerate(variants):
            vals = [idx[(pid, var)].get(sk, 0) if (pid, var) in idx else float("nan")
                    for pid in problems]
            ax.bar(x + offsets[i], vals, width,
                   label=VARIANT_SHORT[var].replace("\n", " "),
                   color=VARIANT_COLOR[var], alpha=0.85)
        ax.set_title(display[sk], fontsize=11)
        ax.set_xlabel("Problem ID")
        ax.set_ylabel(display[sk])
        ax.set_xticks(x)
        ax.set_xticklabels([f"P{p}" for p in problems], fontsize=9)
        ax.legend(fontsize=8)

    fig.tight_layout()
    out = out_dir / "07_variability_stdev.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 8. Cumulative / aggregate comparison
# ---------------------------------------------------------------------------

def plot_aggregate_totals(problems, variants, idx, out_dir: Path):
    metric_keys = list(METRICS.keys())
    fig, axes = plt.subplots(1, len(metric_keys), figsize=(18, 5))
    fig.suptitle("Aggregate Totals Across All Problems (sum of means)",
                 fontsize=13, fontweight="bold")

    for ax, mk in zip(axes, metric_keys):
        label, unit, _ = METRICS[mk]
        totals = []
        colors = []
        var_labels = []
        for var in variants:
            total = sum(
                idx[(pid, var)][mk] for pid in problems if (pid, var) in idx
            )
            totals.append(total)
            colors.append(VARIANT_COLOR[var])
            var_labels.append(VARIANT_SHORT[var].replace("\n", " "))

        bars = ax.bar(range(len(variants)), totals, color=colors, alpha=0.85, width=0.55)

        # Value labels on bars
        for bar, val in zip(bars, totals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=8)

        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_ylabel(unit)
        ax.set_xticks(range(len(variants)))
        ax.set_xticklabels(var_labels, fontsize=8, rotation=15, ha="right")

    fig.tight_layout()
    out = out_dir / "08_aggregate_totals.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 9. Speed-Energy improvement scatter (per problem, per variant)
# ---------------------------------------------------------------------------

def plot_speed_energy_scatter(problems, variants, idx, out_dir: Path):
    non_baseline = [v for v in variants if v != "benchmark"]
    fig, ax = plt.subplots(figsize=(10, 7))

    for var in non_baseline:
        speed_imps, energy_imps = [], []
        prob_labels = []
        for pid in problems:
            base = idx.get((pid, "benchmark"))
            row = idx.get((pid, var))
            if base and row:
                speed_imps.append(pct_change(row["duration_seconds_mean"], base["duration_seconds_mean"]))
                energy_imps.append(pct_change(row["energy_joules_mean"], base["energy_joules_mean"]))
                prob_labels.append(f"P{pid}")
        sc = ax.scatter(speed_imps, energy_imps, color=VARIANT_COLOR[var],
                        s=90, label=VARIANT_SHORT[var].replace("\n", " "),
                        alpha=0.85, zorder=3)
        for x, y, lbl in zip(speed_imps, energy_imps, prob_labels):
            ax.annotate(lbl, (x, y), textcoords="offset points",
                        xytext=(6, 3), fontsize=8, color=VARIANT_COLOR[var])

    ax.axhline(0, color="gray", linestyle="--", linewidth=1, alpha=0.7)
    ax.axvline(0, color="gray", linestyle="--", linewidth=1, alpha=0.7)
    ax.fill_betweenx([-100, 100], 0, 100, alpha=0.04, color="green")
    ax.fill_betweenx([-100, 100], -100, 0, alpha=0.04, color="red")

    ax.set_xlabel("Speed Improvement vs Baseline (%)", fontsize=11)
    ax.set_ylabel("Energy Improvement vs Baseline (%)", fontsize=11)
    ax.set_title("Speed vs Energy Improvement per Problem & Variant\n"
                 "(top-right quadrant = wins on both axes)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)

    # Quadrant labels
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    ax.text(xlim[1] * 0.7, ylim[1] * 0.85, "Faster &\nGreener", fontsize=9,
            color="green", ha="center", style="italic")
    ax.text(xlim[0] * 0.7, ylim[0] * 0.85, "Slower &\nDirtier", fontsize=9,
            color="red", ha="center", style="italic")

    fig.tight_layout()
    out = out_dir / "09_speed_energy_scatter.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 10. Radar chart – aggregate normalised performance per variant
# ---------------------------------------------------------------------------

def plot_radar(problems, variants, idx, out_dir: Path):
    metric_keys = list(METRICS.keys())
    labels = [METRICS[mk][0] for mk in metric_keys]
    N = len(metric_keys)

    # Compute per-variant mean across problems, then normalise so best=1.0
    agg = {}
    for var in variants:
        agg[var] = []
        for mk in metric_keys:
            vals = [idx[(pid, var)][mk] for pid in problems if (pid, var) in idx]
            agg[var].append(np.mean(vals) if vals else float("nan"))

    # Normalise per metric: best (min) → 1, worst → 0 (inverted: lower is better)
    norm = {}
    for i, mk in enumerate(metric_keys):
        col = [agg[v][i] for v in variants]
        mn, mx = min(col), max(col)
        for v in variants:
            if v not in norm:
                norm[v] = []
            if mx == mn:
                norm[v].append(1.0)
            else:
                norm[v].append(1.0 - (agg[v][i] - mn) / (mx - mn))

    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    for var in variants:
        values = norm[var] + norm[var][:1]
        ax.plot(angles, values, color=VARIANT_COLOR[var], linewidth=2,
                label=VARIANT_SHORT[var].replace("\n", " "))
        ax.fill(angles, values, color=VARIANT_COLOR[var], alpha=0.12)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100% (best)"], fontsize=7)
    ax.set_title("Normalised Multi-Metric Radar\n(outer edge = best performer per metric)",
                 fontsize=12, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9)

    fig.tight_layout()
    out = out_dir / "10_radar_normalised.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 11. Success rate & reliability table plot
# ---------------------------------------------------------------------------

def plot_reliability_table(problems, variants, idx, out_dir: Path):
    fig, ax = plt.subplots(figsize=(14, max(4, len(variants) * 0.8 + 2)))
    ax.axis("off")

    col_labels = ["Variant", "# Problems", "All Pass", "Mean Success Rate",
                  "Avg Duration (s)", "Avg Energy (J)", "Avg Emissions (kg)"]
    table_data = []
    for var in variants:
        rows = [idx[(pid, var)] for pid in problems if (pid, var) in idx]
        n = len(rows)
        all_pass = all(r["status"] == "pass" for r in rows)
        mean_sr = np.mean([r["success_rate"] for r in rows]) if rows else float("nan")
        mean_dur = np.mean([r["duration_seconds_mean"] for r in rows]) if rows else float("nan")
        mean_eng = np.mean([r["energy_joules_mean"] for r in rows]) if rows else float("nan")
        mean_em = np.mean([r["emissions_kg_mean"] for r in rows]) if rows else float("nan")
        table_data.append([
            VARIANT_SHORT[var].replace("\n", " "),
            str(n),
            "✓" if all_pass else "✗",
            f"{mean_sr:.1%}",
            f"{mean_dur:.4f}",
            f"{mean_eng:.2f}",
            f"{mean_em:.2e}",
        ])

    tbl = ax.table(cellText=table_data, colLabels=col_labels,
                   loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1.2, 1.8)

    # Header style
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#343a40")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # Row zebra
    for i in range(1, len(table_data) + 1):
        var = variants[i - 1]
        bg = VARIANT_COLOR[var] + "33"
        for j in range(len(col_labels)):
            tbl[i, j].set_facecolor(bg)

    ax.set_title("Variant Reliability & Aggregate Summary", fontsize=13,
                 fontweight="bold", pad=12)
    fig.tight_layout()
    out = out_dir / "11_reliability_table.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# 12. Improvement waterfall per variant (averaged across problems)
# ---------------------------------------------------------------------------

def plot_waterfall_improvements(problems, variants, idx, out_dir: Path):
    non_baseline = [v for v in variants if v != "benchmark"]
    metric_keys = list(METRICS.keys())

    fig, axes = plt.subplots(1, len(non_baseline), figsize=(5 * len(non_baseline), 6), sharey=False)
    if len(non_baseline) == 1:
        axes = [axes]
    fig.suptitle("Mean % Improvement vs Baseline (averaged across all problems)",
                 fontsize=13, fontweight="bold")

    for ax, var in zip(axes, non_baseline):
        imps = []
        for mk in metric_keys:
            vals = []
            for pid in problems:
                base = idx.get((pid, "benchmark"))
                row = idx.get((pid, var))
                if base and row:
                    vals.append(pct_change(row[mk], base[mk]))
            imps.append(np.mean(vals) if vals else 0.0)

        colors = ["#198754" if v >= 0 else "#dc3545" for v in imps]
        bars = ax.bar(range(len(metric_keys)), imps, color=colors, alpha=0.85, width=0.55)

        for bar, val in zip(bars, imps):
            sign = "+" if val >= 0 else ""
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + (0.3 if val >= 0 else -0.8),
                    f"{sign}{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

        ax.axhline(0, color="black", linewidth=1)
        ax.set_title(VARIANT_SHORT[var].replace("\n", " "), fontsize=11, fontweight="bold",
                     color=VARIANT_COLOR[var])
        ax.set_xticks(range(len(metric_keys)))
        ax.set_xticklabels([METRICS[mk][0] for mk in metric_keys], fontsize=9,
                           rotation=20, ha="right")
        ax.set_ylabel("Mean % improvement")

    fig.tight_layout()
    out = out_dir / "12_waterfall_improvements.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(out_dir: Path, summary_path: Path):
    plots = sorted(out_dir.glob("*.png"))
    lines = [
        "<!DOCTYPE html><html><head>",
        "<meta charset='utf-8'>",
        "<title>Benchmark Insight Report</title>",
        "<style>",
        "body{font-family:sans-serif;background:#f8f9fa;margin:0;padding:20px}",
        "h1{color:#343a40}h2{color:#495057}",
        ".grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}",
        ".card{background:white;border-radius:8px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.12)}",
        "img{width:100%;border-radius:4px}",
        "</style></head><body>",
        f"<h1>Benchmark Insight Report</h1>",
        f"<p><b>Source:</b> {summary_path}</p>",
        "<div class='grid'>",
    ]
    for p in plots:
        title = p.stem.replace("_", " ").title()
        lines.append(f"<div class='card'><h2>{title}</h2><img src='{p.name}'/></div>")
    lines += ["</div></body></html>"]
    out = out_dir / "report.html"
    out.write_text("\n".join(lines))
    print(f"  Saved: {out.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_latest_summary() -> Path:
    results_dir = Path(__file__).resolve().parents[1] / "benchmark_results"
    candidates = sorted(results_dir.glob("*/summary.json"))
    if not candidates:
        raise FileNotFoundError("No summary.json found under benchmark_results/")
    return candidates[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="?", type=Path,
                        help="Path to summary.json (default: latest run)")
    parser.add_argument("--out-dir", type=Path,
                        help="Output directory for plots (default: <summary_dir>/insight_plots)")
    args = parser.parse_args()

    summary_path = args.summary or find_latest_summary()
    if not summary_path.exists():
        sys.exit(f"ERROR: {summary_path} does not exist")

    out_dir = args.out_dir or summary_path.parent / "insight_plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nLoading: {summary_path}")
    rows = load_data(summary_path)
    problems, variants, idx = as_df(rows)

    print(f"  Problems : {problems}")
    print(f"  Variants : {variants}")
    print(f"\nGenerating plots → {out_dir}/")

    np.random.seed(42)

    plot_grouped_bars(problems, variants, idx, out_dir)
    plot_improvement_heatmap(problems, variants, idx, out_dir)
    plot_pareto(problems, variants, idx, out_dir)
    plot_improvement_distributions(problems, variants, idx, out_dir)
    plot_per_problem_multiples(problems, variants, idx, out_dir)
    plot_win_rate(problems, variants, idx, out_dir)
    plot_variability(problems, variants, idx, out_dir)
    plot_aggregate_totals(problems, variants, idx, out_dir)
    plot_speed_energy_scatter(problems, variants, idx, out_dir)
    plot_radar(problems, variants, idx, out_dir)
    plot_reliability_table(problems, variants, idx, out_dir)
    plot_waterfall_improvements(problems, variants, idx, out_dir)
    generate_html_report(out_dir, summary_path)

    print(f"\nDone. Open {out_dir / 'report.html'} to browse all plots.\n")


if __name__ == "__main__":
    main()
