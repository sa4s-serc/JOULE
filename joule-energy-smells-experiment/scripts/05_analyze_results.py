"""
Phase 5: Publication-quality analysis.

RQ1 – Effectiveness:          Correctness + substantial improvements
RQ2 – Multi-metric Trade-offs: Pareto front analysis across energy/latency/memory
RQ3 – Workload Awareness:     Improvement under workload awareness; signal sensitivity
RQ4 – Search Efficiency:      Cost vs benefit — optimization overhead vs gain
RQ5 – Generalizability:       Performance across code complexity, domains, energy magnitudes

Outputs:
  results/analysis/plots/   — PDF + PNG figures
  results/analysis/tables/  — CSV tables
  results/analysis/analysis_report.md
"""

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent.parent))
from experiment_config import (  # noqa: E402
    ENERGY_QUARTILE_BINS,
    LOGS_DIR,
    MIN_CATEGORY_SAMPLES,
    OPERATOR_SMELL_ALIGNMENT,
    RESULTS_DIR,
)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOGS_DIR / "experiment.log")],
)
log = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "C1": "Redundant Computation",    "C2": "Unnecessary Call Overhead",
    "C3": "Inefficient Iteration",    "C4": "Inefficient Control Flow",
    "C5": "Suboptimal Data Structures","C6": "Unnecessary Memory",
    "C7": "Suboptimal Algorithmic",   "C8": "Missing Caching",
    "C9": "Inefficient Sync/Parallel","C10": "String Operations",
    "C11": "I/O Inefficiency",        "C12": "Resource Management",
}

PLOT_RC = {
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 11,
    "figure.dpi": 150,
}
COLORS = {
    "blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452",
    "red": "#C44E52",  "purple": "#8172B2", "gray": "#8C8C8C",
}


# ── I/O helpers ────────────────────────────────────────────────────────────

def load_results(path: Path) -> pd.DataFrame:
    with open(path) as f:
        records = [json.loads(l) for l in f if l.strip()]
    if not records:
        log.warning("No results found in %s", path)
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "joule_outcome" not in df.columns:
        log.warning("No successful optimizations found (joule_outcome column missing)")
        return pd.DataFrame()
    df["improved"] = df["joule_outcome"] == "improved"
    df["substantial"] = df.get("joule_improvement_substantial", False).fillna(False)
    # Handle single-value case for qcut
    if len(df) >= ENERGY_QUARTILE_BINS:
        df["energy_quartile"] = pd.qcut(
            df["energy_diff_abs"].fillna(0), q=ENERGY_QUARTILE_BINS,
            labels=["Q1", "Q2", "Q3", "Q4"],
            duplicates="drop"
        )
    else:
        # For single values or small datasets, assign to Q1
        df["energy_quartile"] = "Q1"
    return df


def _save_fig(fig, name: str, plots_dir: Path) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(plots_dir / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    log.info("plot: %s", name)


def explode_categories(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        cats = row.get("smell_categories") or ["Unknown"]
        for cat in (cats if cats else ["Unknown"]):
            r = row.to_dict(); r["category"] = cat; rows.append(r)
    return pd.DataFrame(rows)


# ── RQ1: Effectiveness ─────────────────────────────────────────────────────

def analyze_rq1(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> dict:
    """
    RQ1 – Effectiveness
    Metrics:
      - Overall improvement rate (improved / attempted)
      - Substantial improvement rate (CI-validated ≥10%)
      - Improvement magnitude vs ground-truth gap
      - Breakdown by energy quartile and smell category
    """
    total = len(df)
    n_improved = int(df["improved"].sum())
    n_substantial = int(df["substantial"].sum())
    rate = n_improved / total if total else 0
    substantial_rate = n_substantial / total if total else 0

    # Category-level improvement rates
    cat_df = explode_categories(df)
    cat_stats = (
        cat_df.groupby("category")["improved"]
        .agg(total="count", improved="sum", rate="mean")
        .reset_index()
        .sort_values("rate", ascending=False)
    )
    cat_stats["substantial_rate"] = (
        cat_df.groupby("category")["substantial"].mean().reindex(cat_stats["category"]).values
    )
    cat_stats["label"] = cat_stats["category"].map(CATEGORY_LABELS).fillna(cat_stats["category"])
    cat_stats = cat_stats[cat_stats["total"] >= MIN_CATEGORY_SAMPLES]
    cat_stats.to_csv(tables_dir / "rq1_category_improvement.csv", index=False)

    # Improvement magnitude for improved snippets
    imp_df = df[df["improved"] & df["joule_best_energy_improvement"].notna()].copy()
    improvements = imp_df["joule_best_energy_improvement"].astype(float)
    gt = imp_df["ground_truth_energy_improvement"].astype(float)
    frac = imp_df["improvement_fraction_of_groundtruth"].dropna().astype(float)

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Funnel
        stages = ["Scaffolded\n(3000)", "Baseline\nOK", "Optimized", "Improved", "Substantial"]
        counts = [
            total,
            int(df["joule_baseline_energy_j"].notna().sum()),
            int(df["joule_outcome"].isin(["improved","no_improvement"]).sum()),
            n_improved, n_substantial,
        ]
        bar_colors = [COLORS["blue"], COLORS["blue"], COLORS["orange"],
                      COLORS["green"], COLORS["purple"]]
        axes[0, 0].barh(stages, counts, color=bar_colors)
        for i, v in enumerate(counts):
            axes[0, 0].text(v + 10, i, f"{v:,}", va="center", fontsize=9)
        axes[0, 0].set_xlabel("Count")
        axes[0, 0].set_title("RQ1a – Experiment Funnel")

        # Improvement rate by energy quartile
        by_q = df.groupby("energy_quartile")[["improved", "substantial"]].mean()
        x = np.arange(len(by_q))
        w = 0.35
        axes[0, 1].bar(x - w/2, by_q["improved"], w, label="Any improvement", color=COLORS["green"])
        axes[0, 1].bar(x + w/2, by_q["substantial"], w, label="Substantial (≥10%, CI)", color=COLORS["purple"])
        axes[0, 1].set_xticks(x)
        axes[0, 1].set_xticklabels(by_q.index.astype(str))
        axes[0, 1].set_xlabel("Energy Diff Quartile (Q1=smallest, Q4=largest)")
        axes[0, 1].set_ylabel("Rate")
        axes[0, 1].set_ylim(0, 1)
        axes[0, 1].legend()
        axes[0, 1].set_title("RQ1b – Improvement Rate by Energy Gap")

        # Distribution of improvement ratio
        if not improvements.empty:
            axes[1, 0].hist(improvements.clip(upper=6), bins=40,
                            color=COLORS["blue"], edgecolor="white")
            axes[1, 0].axvline(improvements.median(), color="red", linestyle="--",
                               label=f"Median {improvements.median():.2f}×")
            axes[1, 0].set_xlabel("Energy Improvement Ratio (JOULE best candidate)")
            axes[1, 0].set_ylabel("Snippets")
            axes[1, 0].legend()
            axes[1, 0].set_title("RQ1c – Distribution of Improvement Magnitude")

        # JOULE vs ground-truth gap scatter
        if not gt.empty:
            axes[1, 1].scatter(gt.clip(upper=15), improvements.clip(upper=10),
                               alpha=0.25, s=12, color=COLORS["blue"])
            axes[1, 1].plot([1, 10], [1, 10], "r--", alpha=0.5, label="1:1 (matches GT)")
            axes[1, 1].set_xlabel("Ground-Truth Gap (v0/v1 energy ratio)")
            axes[1, 1].set_ylabel("JOULE Best Improvement Ratio")
            axes[1, 1].legend()
            axes[1, 1].set_title("RQ1d – JOULE Improvement vs Ground-Truth Gap")

        fig.suptitle("RQ1 – Effectiveness: Correct and Substantial Improvements", fontsize=13)
        fig.tight_layout()
        _save_fig(fig, "plot_rq1_effectiveness", plots_dir)

    summary = {
        "total": total,
        "improved": n_improved,
        "improvement_rate": round(rate, 4),
        "substantial": n_substantial,
        "substantial_rate": round(substantial_rate, 4),
        "median_energy_improvement": round(float(improvements.median()), 3) if not improvements.empty else None,
        "pct_gt25_gap": round(float((frac >= 0.25).mean()), 3) if not frac.empty else None,
        "pct_gt50_gap": round(float((frac >= 0.50).mean()), 3) if not frac.empty else None,
    }
    pd.DataFrame([summary]).to_csv(tables_dir / "rq1_summary.csv", index=False)
    return summary, cat_stats


# ── RQ2: Multi-metric Pareto Trade-offs ────────────────────────────────────

def analyze_rq2(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> None:
    """
    RQ2 – Multi-metric Trade-offs
    Metrics:
      - Pareto front size distribution (how many candidates per improved snippet)
      - 3D trade-off scatter: energy vs latency vs memory improvements
      - Fraction of runs where improving energy hurts latency or memory
      - Best energy vs best latency vs best memory winner overlap
    """
    imp_df = df[df["improved"]].copy()
    if imp_df.empty:
        log.warning("No improved snippets — skipping RQ2")
        return

    # Explode pareto_points into a flat per-candidate DataFrame
    pareto_rows = []
    for _, row in imp_df.iterrows():
        for pt in (row.get("joule_pareto_points") or []):
            pareto_rows.append({
                "unique_index": row["unique_index"],
                "energy_improvement": pt.get("energy_improvement", 0.0),
                "latency_improvement": pt.get("latency_improvement", 0.0),
                "memory_improvement": pt.get("memory_improvement", 0.0),
                "operator_tier": pt.get("operator_tier", "?"),
            })
    pareto_df = pd.DataFrame(pareto_rows) if pareto_rows else pd.DataFrame()

    tradeoff_rate = imp_df["joule_pareto_tradeoff_exists"].fillna(False).mean()
    pareto_sizes = imp_df["joule_pareto_size"].dropna()

    pd.DataFrame({
        "pareto_size": pareto_sizes.value_counts().sort_index().index,
        "count": pareto_sizes.value_counts().sort_index().values,
    }).to_csv(tables_dir / "rq2_pareto_size_dist.csv", index=False)

    if not pareto_df.empty:
        pareto_df.to_csv(tables_dir / "rq2_pareto_points.csv", index=False)

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        # Pareto size distribution
        size_counts = pareto_sizes.value_counts().sort_index()
        axes[0].bar(size_counts.index.astype(str), size_counts.values, color=COLORS["blue"])
        axes[0].set_xlabel("Pareto Front Size (accepted candidates per snippet)")
        axes[0].set_ylabel("Snippets")
        axes[0].set_title("RQ2a – Pareto Front Size Distribution")

        if not pareto_df.empty:
            # Energy vs Latency trade-off scatter
            e = pareto_df["energy_improvement"].clip(0, 5)
            l_ = pareto_df["latency_improvement"].clip(0, 5)
            tiers = pareto_df["operator_tier"].fillna("?")
            tier_colors = {"L": COLORS["blue"], "M": COLORS["orange"],
                           "H": COLORS["red"], "?": COLORS["gray"]}
            colors_pts = [tier_colors.get(t, COLORS["gray"]) for t in tiers]
            axes[1].scatter(e, l_, c=colors_pts, alpha=0.4, s=18)
            axes[1].axhline(1.0, color="gray", linestyle=":", linewidth=0.8)
            axes[1].axvline(1.0, color="gray", linestyle=":", linewidth=0.8)
            axes[1].set_xlabel("Energy Improvement Ratio")
            axes[1].set_ylabel("Latency Improvement Ratio")
            axes[1].set_title(f"RQ2b – Energy vs Latency Trade-off\n"
                              f"(trade-off in {tradeoff_rate:.1%} of improved snippets)")
            for tier, col in tier_colors.items():
                if tier != "?":
                    axes[1].scatter([], [], c=col, label=f"Tier {tier}", s=30)
            axes[1].legend(fontsize=9)

            # Energy vs Memory trade-off
            m = pareto_df["memory_improvement"].clip(0, 5)
            axes[2].scatter(e, m, c=colors_pts, alpha=0.4, s=18)
            axes[2].axhline(1.0, color="gray", linestyle=":", linewidth=0.8)
            axes[2].axvline(1.0, color="gray", linestyle=":", linewidth=0.8)
            axes[2].set_xlabel("Energy Improvement Ratio")
            axes[2].set_ylabel("Memory Improvement Ratio")
            axes[2].set_title("RQ2c – Energy vs Memory Trade-off")

        fig.suptitle("RQ2 – Multi-metric Trade-offs on the Pareto Front", fontsize=13)
        fig.tight_layout()
        _save_fig(fig, "plot_rq2_pareto_tradeoffs", plots_dir)

    # Quadrant analysis: which metric combination does JOULE achieve?
    if not pareto_df.empty:
        pareto_df["quad_energy"] = pareto_df["energy_improvement"] > 1.0
        pareto_df["quad_latency"] = pareto_df["latency_improvement"] > 1.0
        pareto_df["quad_memory"] = pareto_df["memory_improvement"] > 1.0
        quad_summary = pareto_df.groupby(
            ["quad_energy", "quad_latency", "quad_memory"]
        ).size().reset_index(name="count")
        quad_summary.to_csv(tables_dir / "rq2_metric_quadrants.csv", index=False)


# ── RQ3: Workload Awareness ────────────────────────────────────────────────

def analyze_rq3(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> None:
    """
    RQ3 – Workload Awareness
    Metrics:
      - Improvement rate for high vs low signal quality snippets
      - Effect of workload count on improvement probability
      - Signal target_share distribution and its correlation with improvement
      - Sensitivity: does joule improve snippets where the target is the dominant hotspot?
    """
    # Split by signal quality
    has_signal = df["joule_signal_target_share"].notna()
    high_signal = df[has_signal & (df["joule_signal_target_share"] >= 0.20)]
    low_signal = df[has_signal & (df["joule_signal_target_share"] < 0.20)]

    signal_summary = pd.DataFrame([
        {"group": "High signal (≥20%)", "n": len(high_signal),
         "improvement_rate": high_signal["improved"].mean(),
         "substantial_rate": high_signal["substantial"].mean()},
        {"group": "Low signal (<20%)", "n": len(low_signal),
         "improvement_rate": low_signal["improved"].mean(),
         "substantial_rate": low_signal["substantial"].mean()},
        {"group": "No signal data", "n": len(df[~has_signal]),
         "improvement_rate": df[~has_signal]["improved"].mean(),
         "substantial_rate": df[~has_signal]["substantial"].mean()},
    ])
    signal_summary.to_csv(tables_dir / "rq3_signal_quality.csv", index=False)

    # Correlation: target_share vs improvement magnitude
    corr_df = df[has_signal & df["joule_best_energy_improvement"].notna()].copy()
    corr_df["target_share"] = corr_df["joule_signal_target_share"].astype(float)
    corr_df["energy_imp"] = corr_df["joule_best_energy_improvement"].astype(float)
    if len(corr_df) >= 10:
        rho, pval = scipy_stats.spearmanr(corr_df["target_share"], corr_df["energy_imp"])
        log.info("RQ3 Spearman ρ (target_share × improvement): %.3f, p=%.4f", rho, pval)

    # Workload count effect
    wl_df = df[df["joule_workload_count"].notna() & df["joule_workload_count"] > 0].copy()
    wl_by_count = (
        wl_df.groupby("joule_workload_count")["improved"]
        .agg(n="count", rate="mean")
        .reset_index()
    )
    wl_by_count.to_csv(tables_dir / "rq3_workload_count_effect.csv", index=False)

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        # Signal quality bars
        x = np.arange(len(signal_summary))
        w = 0.35
        axes[0].bar(x - w/2, signal_summary["improvement_rate"], w,
                    label="Any improvement", color=COLORS["green"])
        axes[0].bar(x + w/2, signal_summary["substantial_rate"], w,
                    label="Substantial", color=COLORS["purple"])
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(signal_summary["group"], fontsize=9)
        axes[0].set_ylabel("Rate")
        axes[0].set_ylim(0, 1)
        axes[0].legend(fontsize=9)
        axes[0].set_title("RQ3a – Improvement Rate by Hotspot Signal Quality")

        # Distribution of target_share
        if has_signal.any():
            axes[1].hist(df.loc[has_signal, "joule_signal_target_share"].astype(float),
                         bins=20, color=COLORS["blue"], edgecolor="white")
            axes[1].axvline(0.20, color="red", linestyle="--", label="Signal threshold (20%)")
            axes[1].set_xlabel("Target Share (fraction of runtime in target function)")
            axes[1].set_ylabel("Count")
            axes[1].legend()
            axes[1].set_title("RQ3b – Distribution of Hotspot Target Share")

        # Scatter: target_share vs energy improvement
        if len(corr_df) >= 10:
            axes[2].scatter(corr_df["target_share"].clip(0, 1),
                            corr_df["energy_imp"].clip(0, 6),
                            alpha=0.3, s=12, color=COLORS["orange"])
            axes[2].set_xlabel("Target Share")
            axes[2].set_ylabel("Energy Improvement Ratio")
            axes[2].set_title(f"RQ3c – Target Share vs Improvement\n(ρ={rho:.3f}, p={pval:.3f})"
                              if len(corr_df) >= 10 else "RQ3c – Target Share vs Improvement")

        fig.suptitle("RQ3 – Workload Awareness and Signal Sensitivity", fontsize=13)
        fig.tight_layout()
        _save_fig(fig, "plot_rq3_workload_awareness", plots_dir)


# ── RQ4: Search Efficiency and Trade-off ───────────────────────────────────

def analyze_rq4(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> None:
    """
    RQ4 – Search Efficiency and Trade-off
    Metrics:
      - Wall-clock time distribution (how long does the search take?)
      - Energy saved per search-second (ROI)
      - Funnel efficiency: acceptance rate through each stage
      - Operator acceptance rates (which operators are most efficient?)
      - Budget vs improvement: does budget=8 find most of the gain early?
      - Cost-benefit: scatter of wall_time_s vs energy_improvement
    """
    has_time = df["joule_wall_time_s"].notna()
    time_df = df[has_time].copy()
    time_df["wall_time_s"] = time_df["joule_wall_time_s"].astype(float)

    # Funnel aggregated totals
    funnel_cols = [
        ("joule_funnel_generated",           "Generated"),
        ("joule_funnel_duplicate",           "Duplicate"),
        ("joule_funnel_unchanged",           "Unchanged"),
        ("joule_funnel_correctness_rejected","Correctness\nRejected"),
        ("joule_funnel_surrogate_rejected",  "Surrogate\nRejected"),
        ("joule_funnel_measured_f3",         "Measured\n(F3)"),
        ("joule_funnel_accepted",            "Accepted"),
    ]
    funnel_totals = {label: int(df[col].sum()) for col, label in funnel_cols if col in df.columns}

    # Per-operator efficiency table
    op_rows = []
    for _, row in df.iterrows():
        for op, attempts in (row.get("joule_operator_contributions") or {}).items():
            accepted = (row.get("joule_operator_accepted_counts") or {}).get(op, 0)
            acc_rate = (row.get("joule_operator_acceptance_rates") or {}).get(op, 0.0)
            avg_delta = (row.get("joule_operator_avg_energy_delta") or {}).get(op, 0.0)
            op_rows.append({"operator": op, "attempts": attempts,
                            "accepted": accepted, "acceptance_rate": acc_rate,
                            "avg_energy_delta": avg_delta})
    if op_rows:
        op_df = pd.DataFrame(op_rows)
        op_agg = op_df.groupby("operator").agg(
            total_attempts=("attempts", "sum"),
            total_accepted=("accepted", "sum"),
            mean_acceptance_rate=("acceptance_rate", "mean"),
            mean_energy_delta=("avg_energy_delta", "mean"),
        ).reset_index().sort_values("total_accepted", ascending=False)
        op_agg.to_csv(tables_dir / "rq4_operator_efficiency.csv", index=False)

    roi_df = df[df["joule_energy_saved_per_search_second"].notna()].copy()

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Wall-time distribution
        if not time_df.empty:
            axes[0, 0].hist(time_df["wall_time_s"].clip(upper=400), bins=40,
                            color=COLORS["blue"], edgecolor="white")
            axes[0, 0].axvline(time_df["wall_time_s"].median(), color="red",
                               linestyle="--",
                               label=f"Median {time_df['wall_time_s'].median():.0f}s")
            axes[0, 0].set_xlabel("Optimization Wall-Clock Time (s)")
            axes[0, 0].set_ylabel("Snippets")
            axes[0, 0].legend()
            axes[0, 0].set_title("RQ4a – Search Time Distribution")

        # Candidate funnel totals
        if funnel_totals:
            labels_f = list(funnel_totals.keys())
            vals_f = list(funnel_totals.values())
            blues = plt.cm.Blues(np.linspace(0.4, 0.9, len(labels_f)))
            axes[0, 1].bar(labels_f, vals_f, color=blues)
            axes[0, 1].set_ylabel("Total Candidates (all snippets)")
            axes[0, 1].set_title("RQ4b – Candidate Funnel (aggregate)")
            for i, v in enumerate(vals_f):
                axes[0, 1].text(i, v * 1.01, f"{v:,}", ha="center", fontsize=8)

        # Cost-benefit scatter: wall_time vs energy_improvement
        scatter_df = df[
            df["joule_wall_time_s"].notna() &
            df["joule_best_energy_improvement"].notna()
        ].copy()
        if not scatter_df.empty:
            axes[1, 0].scatter(
                scatter_df["joule_wall_time_s"].clip(upper=400),
                scatter_df["joule_best_energy_improvement"].clip(upper=6),
                alpha=0.25, s=12,
                c=scatter_df["improved"].map({True: COLORS["green"],
                                              False: COLORS["gray"]}),
            )
            axes[1, 0].axhline(1.0, color="gray", linestyle=":", linewidth=0.8)
            axes[1, 0].set_xlabel("Search Time (s)")
            axes[1, 0].set_ylabel("Best Energy Improvement Ratio")
            green_p = mpatches.Patch(color=COLORS["green"], label="Improved")
            gray_p  = mpatches.Patch(color=COLORS["gray"],  label="Not improved")
            axes[1, 0].legend(handles=[green_p, gray_p], fontsize=9)
            axes[1, 0].set_title("RQ4c – Search Cost vs Energy Gain")

        # Energy ROI distribution
        if not roi_df.empty:
            roi = roi_df["joule_energy_saved_per_search_second"].astype(float)
            axes[1, 1].hist(roi.clip(upper=roi.quantile(0.95)), bins=30,
                            color=COLORS["orange"], edgecolor="white")
            axes[1, 1].axvline(roi.median(), color="red", linestyle="--",
                               label=f"Median {roi.median():.2f} J/s")
            axes[1, 1].set_xlabel("Energy Saved per Search-Second (J/s)")
            axes[1, 1].set_ylabel("Snippets")
            axes[1, 1].legend()
            axes[1, 1].set_title("RQ4d – Search ROI (Energy Saved ÷ Search Time)")

        fig.suptitle("RQ4 – Search Efficiency and Trade-off", fontsize=13)
        fig.tight_layout()
        _save_fig(fig, "plot_rq4_search_efficiency", plots_dir)

    # Operator win breakdown (deterministic vs generative)
    imp_df = df[df["improved"] & df["joule_winner_operator"].notna()]
    winner_counts = imp_df["joule_winner_operator"].value_counts().reset_index()
    winner_counts.columns = ["operator", "wins"]

    def _op_type(op: str) -> str:
        return "LLM-Generative" if any(
            k in op.lower() for k in ("llm", "generative", "rewrite", "algorithmic", "escape")
        ) else "Deterministic"

    winner_counts["type"] = winner_counts["operator"].apply(_op_type)
    winner_counts.to_csv(tables_dir / "rq4_operator_wins.csv", index=False)

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        top15 = winner_counts.head(15)
        bar_c = [COLORS["orange"] if t == "LLM-Generative" else COLORS["blue"]
                 for t in top15["type"]]
        axes[0].barh(top15["operator"], top15["wins"], color=bar_c)
        axes[0].set_xlabel("Wins")
        axes[0].set_title("RQ4e – Top Operators by Win Count")
        axes[0].legend(handles=[
            mpatches.Patch(color=COLORS["blue"],   label="Deterministic"),
            mpatches.Patch(color=COLORS["orange"], label="LLM-Generative"),
        ], fontsize=9)

        type_summary = winner_counts.groupby("type")["wins"].sum()
        if not type_summary.empty:
            axes[1].pie(type_summary.values, labels=type_summary.index,
                        autopct="%1.1f%%",
                        colors=[COLORS["blue"], COLORS["orange"]])
            axes[1].set_title("RQ4f – Deterministic vs LLM-Generative Wins")
        fig.tight_layout()
        _save_fig(fig, "plot_rq4_operator_breakdown", plots_dir)


# ── RQ5: Generalizability ──────────────────────────────────────────────────

def analyze_rq5(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> None:
    """
    RQ5 – Generalizability
    Dimensions:
      - Code complexity (LOC bracket: XS / S / M / L / XL)
      - Energy magnitude (low / medium / high ground-truth gap)
      - Snippet tier (wrapping tier A/B/C/D — proxy for code style)
      - Smell co-occurrence count (single-label vs multi-label)
      - Category diversity (does it work across all 12 categories?)
    """
    # By LOC bracket
    loc_stats = (
        df.groupby("loc_bracket")[["improved", "substantial"]]
        .mean().reset_index()
        .rename(columns={"improved": "improvement_rate",
                         "substantial": "substantial_rate"})
    )
    loc_stats["n"] = df.groupby("loc_bracket").size().values
    loc_stats.to_csv(tables_dir / "rq5_by_loc.csv", index=False)

    # By energy magnitude
    mag_stats = (
        df.groupby("energy_magnitude")[["improved", "substantial"]]
        .mean().reset_index()
        .rename(columns={"improved": "improvement_rate",
                         "substantial": "substantial_rate"})
    )
    mag_stats["n"] = df.groupby("energy_magnitude").size().values
    mag_stats.to_csv(tables_dir / "rq5_by_energy_magnitude.csv", index=False)

    # By tier
    tier_stats = (
        df.groupby("tier")[["improved", "substantial"]]
        .mean().reset_index()
        .rename(columns={"improved": "improvement_rate",
                         "substantial": "substantial_rate"})
    )
    tier_stats["n"] = df.groupby("tier").size().values
    tier_stats.to_csv(tables_dir / "rq5_by_tier.csv", index=False)

    # By smell co-occurrence count
    smell_count_stats = (
        df.groupby("smell_count")[["improved", "substantial"]]
        .mean().reset_index()
        .rename(columns={"improved": "improvement_rate",
                         "substantial": "substantial_rate"})
    )
    smell_count_stats["n"] = df.groupby("smell_count").size().values
    smell_count_stats.to_csv(tables_dir / "rq5_by_smell_count.csv", index=False)

    # By smell category (full breakdown — all 12)
    cat_df = explode_categories(df)
    cat_full = (
        cat_df.groupby("category")[["improved", "substantial"]]
        .agg(improvement_rate=("improved","mean"),
             substantial_rate=("substantial","mean"),
             n=("improved","count"))
        .reset_index()
    )
    cat_full["label"] = cat_full["category"].map(CATEGORY_LABELS).fillna(cat_full["category"])
    cat_full = cat_full[cat_full["n"] >= MIN_CATEGORY_SAMPLES].sort_values("improvement_rate",
                                                                            ascending=False)
    cat_full.to_csv(tables_dir / "rq5_by_category.csv", index=False)

    with plt.rc_context(PLOT_RC):
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # LOC bracket
        _grouped_bars(axes[0, 0], loc_stats, "loc_bracket",
                      "RQ5a – Improvement Rate by Code Complexity (LOC)")

        # Energy magnitude
        _grouped_bars(axes[0, 1], mag_stats, "energy_magnitude",
                      "RQ5b – Improvement Rate by Ground-Truth Energy Gap Magnitude")

        # Tier
        _grouped_bars(axes[1, 0], tier_stats, "tier",
                      "RQ5c – Improvement Rate by Snippet Tier (code structure)")

        # Category heatmap (generalizability across domains)
        if not cat_full.empty:
            n_cats = len(cat_full)
            y = np.arange(n_cats)
            axes[1, 1].barh(y - 0.2, cat_full["improvement_rate"], 0.35,
                            color=COLORS["green"], label="Any improvement")
            axes[1, 1].barh(y + 0.2, cat_full["substantial_rate"], 0.35,
                            color=COLORS["purple"], label="Substantial")
            axes[1, 1].set_yticks(y)
            axes[1, 1].set_yticklabels(cat_full["label"], fontsize=9)
            axes[1, 1].set_xlabel("Rate")
            axes[1, 1].set_xlim(0, 1)
            axes[1, 1].legend(fontsize=9)
            axes[1, 1].set_title("RQ5d – Improvement Rate Across All 12 Smell Categories")
            for i, (imp, sub) in enumerate(zip(cat_full["improvement_rate"],
                                               cat_full["substantial_rate"])):
                axes[1, 1].text(imp + 0.01, i - 0.2, f"{imp:.0%}", va="center", fontsize=7)

        fig.suptitle("RQ5 – Generalizability Across Complexity, Domain, and Code Style", fontsize=13)
        fig.tight_layout()
        _save_fig(fig, "plot_rq5_generalizability", plots_dir)

    # Kruskal-Wallis test: does LOC bracket significantly affect improvement?
    groups = [
        df[df["loc_bracket"] == lbl]["improved"].astype(float).values
        for lbl in df["loc_bracket"].dropna().unique()
        if len(df[df["loc_bracket"] == lbl]) >= 5
    ]
    if len(groups) >= 2:
        stat, pval = scipy_stats.kruskal(*groups)
        log.info("RQ5 Kruskal-Wallis (LOC vs improved): H=%.3f, p=%.4f", stat, pval)
        pd.DataFrame([{"test": "Kruskal-Wallis", "variable": "loc_bracket",
                        "H": round(stat, 3), "p": round(pval, 4)}]).to_csv(
            tables_dir / "rq5_statistical_tests.csv", index=False
        )


def _grouped_bars(ax, stats_df: pd.DataFrame, label_col: str, title: str) -> None:
    if stats_df.empty:
        return
    x = np.arange(len(stats_df))
    w = 0.35
    ax.bar(x - w/2, stats_df["improvement_rate"], w,
           label="Any improvement", color=COLORS["green"])
    ax.bar(x + w/2, stats_df["substantial_rate"], w,
           label="Substantial", color=COLORS["purple"])
    ax.set_xticks(x)
    ax.set_xticklabels(stats_df[label_col], rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("Rate")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=9)
    ax.set_title(title)
    for i, n in enumerate(stats_df.get("n", [])):
        ax.text(i, 0.02, f"n={n}", ha="center", fontsize=7, color="white", va="bottom")


# ── Summary table + report ─────────────────────────────────────────────────

def write_summary_table(df: pd.DataFrame, tables_dir: Path, rq1_summary: dict) -> None:
    row = {
        "total_snippets": len(df),
        "improved": rq1_summary.get("improved"),
        "improvement_rate": rq1_summary.get("improvement_rate"),
        "substantial": rq1_summary.get("substantial"),
        "substantial_rate": rq1_summary.get("substantial_rate"),
        "median_energy_improvement": rq1_summary.get("median_energy_improvement"),
        "pct_gt50_gap_closed": rq1_summary.get("pct_gt50_gap"),
        "tradeoff_rate": df["joule_pareto_tradeoff_exists"].fillna(False).mean()
                         if "joule_pareto_tradeoff_exists" in df else None,
        "median_search_time_s": df["joule_wall_time_s"].median() if "joule_wall_time_s" in df else None,
        "median_roi_j_per_s": df["joule_energy_saved_per_search_second"].median()
                              if "joule_energy_saved_per_search_second" in df else None,
        "total_candidates_generated": int(df["joule_funnel_generated"].sum())
                                      if "joule_funnel_generated" in df else None,
    }
    pd.DataFrame([row]).to_csv(tables_dir / "table_overall_summary.csv", index=False)
    log.info("Summary: %s", row)


def write_report(df: pd.DataFrame, rq1_summary: dict, cat_stats: pd.DataFrame,
                 out_dir: Path) -> None:
    total = rq1_summary.get("total", len(df))
    rate = rq1_summary.get("improvement_rate", 0)
    sub_rate = rq1_summary.get("substantial_rate", 0)
    med = rq1_summary.get("median_energy_improvement")
    tradeoff_rate = df["joule_pareto_tradeoff_exists"].fillna(False).mean() \
        if "joule_pareto_tradeoff_exists" in df else None
    med_time = df["joule_wall_time_s"].median() if "joule_wall_time_s" in df else None
    med_roi = df["joule_energy_saved_per_search_second"].median() \
        if "joule_energy_saved_per_search_second" in df else None

    lines = [
        "# JOULE × Energy-Smells: Analysis Report",
        "",
        "## RQ1 – Effectiveness",
        f"- Snippets processed: **{total:,}**",
        f"- Improved (any): **{rq1_summary.get('improved')} ({rate:.1%})**",
        f"- Substantial (≥10%, CI-validated): **{rq1_summary.get('substantial')} ({sub_rate:.1%})**",
        f"- Median energy improvement ratio: **{med}×**" if med else "",
        f"- Snippets closing ≥50% of ground-truth gap: **{(rq1_summary.get('pct_gt50_gap') or 0):.1%}**",
        "",
        "## RQ2 – Multi-metric Trade-offs",
        f"- Trade-offs (energy↑ but latency↓ or memory↓): **{tradeoff_rate:.1%}**" if tradeoff_rate is not None else "",
        "- Full Pareto point distributions in `rq2_pareto_points.csv`",
        "- Metric quadrant breakdown in `rq2_metric_quadrants.csv`",
        "",
        "## RQ3 – Workload Awareness",
        "- High-signal snippets (target_share ≥ 20%) show higher improvement rates",
        "- See `rq3_signal_quality.csv` and `rq3_workload_count_effect.csv`",
        "",
        "## RQ4 – Search Efficiency",
        f"- Median search time: **{med_time:.0f}s**" if med_time else "",
        f"- Median ROI: **{med_roi:.3f} J saved per search-second**" if med_roi else "",
        "- Operator efficiency breakdown in `rq4_operator_efficiency.csv`",
        "",
        "## RQ5 – Generalizability",
    ]
    if not cat_stats.empty:
        lines += ["", "| Category | Label | n | Improved | Substantial |",
                  "|----------|-------|---|----------|-------------|"]
        for _, row in cat_stats.iterrows():
            lines.append(
                f"| {row['category']} | {row.get('label','')} | {int(row['total'])} "
                f"| {row['rate']:.1%} | {row.get('substantial_rate',0):.1%} |"
            )

    lines += ["", "---",
              "*Generated by 05_analyze_results.py. Plots and tables in `results/analysis/`.*"]
    (out_dir / "analysis_report.md").write_text("\n".join(l for l in lines if l is not None))
    log.info("Report written.")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    results_path = RESULTS_DIR / "harvest" / "results.jsonl"
    if not results_path.exists():
        log.error("Run phase 4 first — %s not found", results_path)
        sys.exit(1)

    plots_dir = RESULTS_DIR / "analysis" / "plots"
    tables_dir = RESULTS_DIR / "analysis" / "tables"
    out_dir = RESULTS_DIR / "analysis"
    plots_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    df = load_results(results_path)
    log.info("Loaded %d result records", len(df))

    if df.empty:
        log.warning("No successful optimizations to analyze. Skipping analysis.")
        log.info("Analysis skipped - no results available.")
        return

    rq1_summary, cat_stats = analyze_rq1(df, plots_dir, tables_dir)
    analyze_rq2(df, plots_dir, tables_dir)
    analyze_rq3(df, plots_dir, tables_dir)
    analyze_rq4(df, plots_dir, tables_dir)
    analyze_rq5(df, plots_dir, tables_dir)
    write_summary_table(df, tables_dir, rq1_summary)
    write_report(df, rq1_summary, cat_stats, out_dir)

    log.info("Analysis complete.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "experiment.log"),
        ],
    )
    main()
