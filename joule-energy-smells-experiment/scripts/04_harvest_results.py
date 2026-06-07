"""Phase 4: Harvest results → master results.jsonl with all RQ fields."""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from experiment_config import (  # noqa: E402
    ENERGY_MAGNITUDE_LABELS, LOC_BRACKETS, LOGS_DIR, RESULTS_DIR, WORKSPACES_DIR,
)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(LOGS_DIR / "experiment.log")],
)
log = logging.getLogger(__name__)


# ── tiny helpers ───────────────────────────────────────────────────────────

def _latest_run_dir(ws: Path) -> Path | None:
    d = ws / ".joule" / "runs"
    if not d.exists():
        return None
    dirs = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[0] if dirs else None


def _rj(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _loc_bracket(loc: int | None) -> str:
    if loc is None:
        return "unknown"
    for lo, hi, label in LOC_BRACKETS:
        if lo <= loc <= hi:
            return label
    return "XL (>200)"


def _energy_magnitude(diff: float | None) -> str:
    if diff is None:
        return "unknown"
    for label, (lo, hi) in ENERGY_MAGNITUDE_LABELS.items():
        if lo <= diff < hi:
            return label
    return "high"



def _events_wall_time(run_dir: Path) -> float | None:
    p = run_dir / "events.jsonl"
    if not p.exists():
        return None
    try:
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        if len(lines) < 2:
            return None
        t0 = datetime.fromisoformat(json.loads(lines[0])["timestamp"])
        t1 = datetime.fromisoformat(json.loads(lines[-1])["timestamp"])
        return round((t1 - t0).total_seconds(), 3)
    except Exception:
        return None


# ── RQ1 + RQ2: run_summary ─────────────────────────────────────────────────

def _extract_run_summary(run_dir: Path) -> dict:
    s = _rj(run_dir / "run_summary.json")
    if not s:
        return {}
    candidates = s.get("candidates", [])
    accepted = [c for c in candidates if not c.get("rejected")]
    best_ref = s.get("best_candidate")
    best, best_id = None, None
    if isinstance(best_ref, dict):
        best, best_id = best_ref, best_ref.get("candidate_id")
    elif isinstance(best_ref, str):
        best_id = best_ref
        best = next((c for c in candidates if c.get("candidate_id") == best_id), None)
    elif accepted:
        best, best_id = accepted[0], accepted[0].get("candidate_id")
    imp = (best or {}).get("improvement_summary", {})
    pareto_points = []
    for c in accepted:
        ci = c.get("improvement_summary", {})
        pareto_points.append({
            "candidate_id": c.get("candidate_id"),
            "operator_name": c.get("operator_name"),
            "operator_tier": c.get("operator_tier"),
            "energy_improvement": ci.get("energy", 0.0),
            "latency_improvement": ci.get("latency", 0.0),
            "memory_improvement": ci.get("memory", 0.0),
        })
    tradeoff = any(
        p["energy_improvement"] > 1.0
        and (p["latency_improvement"] < 1.0 or p["memory_improvement"] < 1.0)
        for p in pareto_points
    )
    return {
        "joule_outcome": "improved" if accepted else "no_improvement",
        "joule_total_candidates": len(candidates),
        "joule_accepted_count": len(accepted),
        "joule_best_energy_improvement": imp.get("energy"),
        "joule_best_latency_improvement": imp.get("latency"),
        "joule_best_memory_improvement": imp.get("memory"),
        "joule_winner_operator": (best or {}).get("operator_name"),
        "joule_winner_tier": (best or {}).get("operator_tier"),
        "joule_winner_tier_descriptor": (best or {}).get("operator_tier_descriptor"),
        "joule_winner_candidate_id": best_id,
        "joule_run_id": s.get("run_id"),
        "joule_pareto_size": len(accepted),
        "joule_pareto_points": pareto_points,
        "joule_pareto_tradeoff_exists": tradeoff,
    }

# ── RQ3 + RQ4: optimization_analysis ──────────────────────────────────────

def _extract_opt_analysis(run_dir: Path) -> dict:
    a = _rj(run_dir / "optimization_analysis.json")
    if not a:
        return {}
    search = a.get("search", {})
    funnel = search.get("funnel", {})
    timings = search.get("stage_timings_s", {})
    operators = a.get("operators", [])
    generated = funnel.get("generated", 0)
    corr_rej = funnel.get("correctness_rejected", 0)
    dup = funnel.get("duplicate", 0)
    unch = funnel.get("unchanged", 0)
    passed_corr = max(generated - corr_rej - dup - unch, 0)
    corr_rate = round(passed_corr / generated, 4) if generated > 0 else None
    op_contrib = {o["operator_name"]: o.get("attempts", 0)
                  for o in operators if isinstance(o, dict)}
    op_accepted = {o["operator_name"]: o.get("accepted", 0)
                   for o in operators if isinstance(o, dict) and o.get("accepted", 0) > 0}
    op_acc_rate = {o["operator_name"]: round(o.get("acceptance_rate", 0.0), 4)
                   for o in operators if isinstance(o, dict)}
    op_e_delta = {o["operator_name"]: o.get("avg_energy_delta", 0.0)
                  for o in operators if isinstance(o, dict)}
    hs = a.get("hotspots") or {}
    sq = hs.get("signal_quality", {}) if hs else {}
    wl_count = len(hs.get("by_workload", {})) if hs else 0
    return {
        "joule_funnel_generated": generated,
        "joule_funnel_duplicate": dup,
        "joule_funnel_unchanged": unch,
        "joule_funnel_correctness_rejected": corr_rej,
        "joule_funnel_surrogate_rejected": funnel.get("surrogate_rejected", 0),
        "joule_funnel_measured_f1": funnel.get("measured_f1", 0),
        "joule_funnel_measured_f2": funnel.get("measured_f2", 0),
        "joule_funnel_measured_f3": funnel.get("measured_f3", 0),
        "joule_funnel_accepted": funnel.get("accepted", 0),
        "joule_correctness_pass_rate": corr_rate,
        "joule_stage_time_correctness_s": timings.get("correctness"),
        "joule_stage_time_surrogate_s": timings.get("surrogate"),
        "joule_stage_time_measurement_s": timings.get("measurement"),
        "joule_operator_contributions": op_contrib,
        "joule_operator_accepted_counts": op_accepted,
        "joule_operator_acceptance_rates": op_acc_rate,
        "joule_operator_avg_energy_delta": op_e_delta,
        "joule_operators_used": list(op_contrib.keys()),
        "joule_workload_count": wl_count,
        "joule_signal_low": sq.get("low_signal"),
        "joule_signal_target_share": sq.get("target_share"),
        "joule_signal_project_share": sq.get("project_share"),
    }


# ── RQ3: baseline ──────────────────────────────────────────────────────────

def _extract_baseline(run_dir: Path) -> dict:
    bl = _rj(run_dir / "baseline_analysis.json")
    if not bl:
        return {}
    agg = bl.get("baseline", {}).get("aggregate", {})
    return {
        "joule_baseline_energy_j": agg.get("mean_energy_j"),
        "joule_baseline_energy_ci95": agg.get("energy_ci95"),
        "joule_baseline_time_s": agg.get("mean_wall_time_s"),
        "joule_baseline_time_ci95": agg.get("wall_time_ci95"),
        "joule_baseline_memory_bytes": agg.get("mean_peak_memory_bytes"),
        "joule_baseline_memory_ci95": agg.get("peak_memory_ci95"),
        "joule_baseline_repetitions": agg.get("repetitions"),
        "joule_baseline_success_rate": agg.get("success_rate"),
    }


# ── base fields carried from prepared_records ──────────────────────────────

def _base_fields(rec: dict) -> dict:
    return {
        "unique_index": rec["unique_index"],
        "problem_id": rec.get("problem_id"),
        "tier": rec.get("tier"),
        "target_version": rec.get("target_version"),
        "target_function_name": rec.get("target_function_name"),
        "loc": rec.get("loc"),
        "energy_diff_abs": rec.get("energy_diff_abs"),
        "ground_truth_energy_improvement": rec.get("ground_truth_energy_improvement"),
        "result_energy_v0": rec.get("result_energy_v0"),
        "result_energy_v1": rec.get("result_energy_v1"),
        "result_time_v0": rec.get("result_time_v0"),
        "result_time_v1": rec.get("result_time_v1"),
        "result_memory_v0": rec.get("result_memory_v0"),
        "result_memory_v1": rec.get("result_memory_v1"),
        "final_classification": rec.get("final_classification", []),
        "smell_categories": sorted({
            c.get("category_id") for c in rec.get("final_classification", [])
            if c.get("category_id")
        }),
        "smell_subcategories": sorted({
            c.get("subcategory_id") for c in rec.get("final_classification", [])
            if c.get("subcategory_id")
        }),
        "smell_count": len(rec.get("final_classification", [])),
    }


# ── per-record harvest ─────────────────────────────────────────────────────

def harvest_one(rec: dict) -> tuple[dict | None, dict | None]:
    idx = rec["unique_index"]
    ws = WORKSPACES_DIR / str(idx)

    opt_path = RESULTS_DIR / "optimizations" / str(idx) / "run_status.json"
    if not opt_path.exists():
        return None, {"unique_index": idx, "reason": "no_optimization_run"}

    opt_status = _rj(opt_path)
    phase_status = opt_status.get("status", "unknown")
    if phase_status not in ("improved", "no_improvement"):
        return None, {"unique_index": idx, "reason": phase_status}

    run_dir = _latest_run_dir(ws)
    if not run_dir:
        return {**_base_fields(rec), "joule_outcome": phase_status,
                "joule_phase_status": phase_status}, None

    result: dict = {
        **_base_fields(rec),
        "joule_phase_status": phase_status,
        "joule_wall_time_s": _events_wall_time(run_dir) or opt_status.get("elapsed_s"),
        **_extract_baseline(run_dir),
        **_extract_run_summary(run_dir),
        **_extract_opt_analysis(run_dir),
    }

    if not result.get("joule_outcome"):
        result["joule_outcome"] = phase_status

    # RQ1: gap fraction + substantiality
    gt_imp = rec.get("ground_truth_energy_improvement")
    j_imp = result.get("joule_best_energy_improvement") or 0.0
    result["improvement_fraction_of_groundtruth"] = (
        round((j_imp - 1.0) / (gt_imp - 1.0), 4)
        if gt_imp and gt_imp > 1.0 and j_imp > 1.0 else None
    )
    b_e = result.get("joule_baseline_energy_j") or 0.0
    ci95 = result.get("joule_baseline_energy_ci95") or 0.0
    if j_imp > 1.1 and b_e > 0:
        result["joule_improvement_substantial"] = bool(
            (b_e - b_e / j_imp) > 2 * ci95
        )
    else:
        result["joule_improvement_substantial"] = False

    # RQ2: absolute post-opt values for Pareto scatter
    b_t = result.get("joule_baseline_time_s") or 0.0
    b_m = result.get("joule_baseline_memory_bytes") or 0.0
    l_imp = result.get("joule_best_latency_improvement") or 0.0
    m_imp = result.get("joule_best_memory_improvement") or 0.0
    result["joule_best_energy_j_after"] = (
        round(b_e / j_imp, 4) if j_imp > 0 and b_e > 0 else None)
    result["joule_best_latency_s_after"] = (
        round(b_t / l_imp, 4) if l_imp > 0 and b_t > 0 else None)
    result["joule_best_memory_bytes_after"] = (
        round(b_m / m_imp, 0) if m_imp > 0 and b_m > 0 else None)

    # RQ4: search efficiency
    wall_s = result.get("joule_wall_time_s") or 0.0
    n_c = result.get("joule_total_candidates") or 0
    result["joule_candidates_per_second"] = (
        round(n_c / wall_s, 3) if wall_s > 0 and n_c > 0 else None)
    result["joule_energy_saved_per_search_second"] = (
        round((b_e - b_e / j_imp) / wall_s, 4)
        if wall_s > 0 and j_imp > 1.0 and b_e > 0 else None)

    # RQ5: stratification
    result["loc_bracket"] = _loc_bracket(rec.get("loc"))
    result["energy_magnitude"] = _energy_magnitude(rec.get("energy_diff_abs"))

    return result, None


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    out_dir = RESULTS_DIR / "harvest"
    out_dir.mkdir(parents=True, exist_ok=True)

    prep_path = RESULTS_DIR / "prep" / "prepared_records.jsonl"
    with open(prep_path) as f:
        records = [json.loads(l) for l in f]

    log.info("Harvesting %d records...", len(records))
    results, failures = [], []

    for i, rec in enumerate(records):
        result, failure = harvest_one(rec)
        if result:
            results.append(result)
        if failure:
            failures.append(failure)
        if (i + 1) % 500 == 0:
            log.info("  %d / %d...", i + 1, len(records))

    (out_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in results) + ("\n" if results else "")
    )
    (out_dir / "failures.jsonl").write_text(
        "\n".join(json.dumps(f) for f in failures) + ("\n" if failures else "")
    )

    improved = sum(1 for r in results if r.get("joule_outcome") == "improved")
    log.info("Done: %d results, %d failures | improved=%d (%.1f%%)",
             len(results), len(failures), improved,
             100 * improved / max(len(results), 1))


if __name__ == "__main__":
    main()
