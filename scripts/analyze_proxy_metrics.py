#!/usr/bin/env python3
"""
Proxy Metrics Analysis Script

Reads mutations_log.json from a completed HEDGE run, computes the 7 EnCoDe
proxy features for every mutation, then:

1. Compares proxy metric deltas to actual energy measurements.
2. Identifies Pareto-optimal solutions per generation and per layer.
3. Calibrates thresholds: for each metric, reports the delta value that
   maximises (TPR - FPR) for predicting energy improvement, enabling the
   proxy filter to be tuned for future runs.

Usage:
    python scripts/analyze_proxy_metrics.py <run_dir> [--output report.json]

Where <run_dir> is the experiment output directory containing mutations_log.json.
"""

import argparse
import ast
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature extraction (mirrors proxy_filter.py to avoid import path issues)
# ---------------------------------------------------------------------------

@dataclass
class ProxyFeatures:
    total_nodes: int
    operator_count: int
    literal_count: int
    conditionals_count: int
    loops_count: int
    cyclomatic_complexity: int
    cognitive_complexity: float
    nesting_complexity: float

    @property
    def operator_density(self) -> float:
        return self.operator_count / self.total_nodes if self.total_nodes else 0.0

    @property
    def literal_density(self) -> float:
        return self.literal_count / self.total_nodes if self.total_nodes else 0.0

    def as_dict(self) -> Dict[str, float]:
        return {
            "operator_density": self.operator_density,
            "literal_density": self.literal_density,
            "conditionals_count": float(self.conditionals_count),
            "loops_count": float(self.loops_count),
            "cyclomatic_complexity": float(self.cyclomatic_complexity),
            "cognitive_complexity": self.cognitive_complexity,
            "nesting_complexity": self.nesting_complexity,
        }


class _FeatureExtractor(ast.NodeVisitor):
    def __init__(self):
        self.total_nodes = 0
        self.operator_count = 0
        self.literal_count = 0
        self.conditionals_count = 0
        self.loops_count = 0
        self.cyclomatic = 1
        self.cognitive = 0.0
        self._cf_depth = 0
        self._nesting_samples: List[float] = []

    def generic_visit(self, node):
        self.total_nodes += 1
        super().generic_visit(node)

    def visit_BinOp(self, node):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_Compare(self, node):
        self.operator_count += len(node.ops)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_Constant(self, node):
        self.literal_count += 1
        self.generic_visit(node)

    visit_Num = visit_Constant
    visit_Str = visit_Constant

    def visit_If(self, node):
        self.conditionals_count += 1
        self.cyclomatic += 1
        self.cognitive += 1 + self._cf_depth
        self._nesting_samples.append(self._cf_depth)
        self._cf_depth += 1
        for child in node.body:
            self.visit(child)
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                self.visit(node.orelse[0])
            else:
                for child in node.orelse:
                    self.visit(child)
        self._cf_depth -= 1

    def visit_For(self, node):
        self.loops_count += 1
        self.cyclomatic += 1
        self.cognitive += 1 + self._cf_depth
        self._nesting_samples.append(self._cf_depth)
        self._cf_depth += 1
        for child in node.body:
            self.visit(child)
        self._cf_depth -= 1
        for child in node.orelse:
            self.visit(child)

    def visit_While(self, node):
        self.loops_count += 1
        self.cyclomatic += 1
        self.cognitive += 1 + self._cf_depth
        self._nesting_samples.append(self._cf_depth)
        self._cf_depth += 1
        for child in node.body:
            self.visit(child)
        self._cf_depth -= 1
        for child in node.orelse:
            self.visit(child)

    def visit_ExceptHandler(self, node):
        self.cyclomatic += 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.loops_count += 1
        self.cyclomatic += 1
        self.generic_visit(node)

    def features(self) -> ProxyFeatures:
        nesting = (
            sum(self._nesting_samples) / len(self._nesting_samples)
            if self._nesting_samples else 0.0
        )
        return ProxyFeatures(
            total_nodes=max(self.total_nodes, 1),
            operator_count=self.operator_count,
            literal_count=self.literal_count,
            conditionals_count=self.conditionals_count,
            loops_count=self.loops_count,
            cyclomatic_complexity=self.cyclomatic,
            cognitive_complexity=self.cognitive,
            nesting_complexity=nesting,
        )


def extract_features(source: str) -> Optional[ProxyFeatures]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    extractor = _FeatureExtractor()
    extractor.visit(tree)
    return extractor.features()


# ---------------------------------------------------------------------------
# Pareto helpers
# ---------------------------------------------------------------------------

def is_dominated(a: Dict[str, float], b: Dict[str, float], objectives: List[str]) -> bool:
    """Return True if b dominates a (b is at least as good on all, strictly better on one)."""
    strictly_better = False
    for obj in objectives:
        if b[obj] > a[obj]:
            return False
        if b[obj] < a[obj]:
            strictly_better = True
    return strictly_better


def pareto_front(items: List[Dict[str, Any]], objectives: List[str]) -> List[Dict[str, Any]]:
    """Return the Pareto-optimal subset (minimising all objectives)."""
    front = []
    for candidate in items:
        dominated = False
        for other in items:
            if other is candidate:
                continue
            if is_dominated(candidate, other, objectives):
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return front


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def compute_proxy_score(delta: Dict[str, float], thresholds: Dict[str, float]) -> int:
    """Count how many metrics signal 'worse' given per-metric thresholds."""
    worse_count = 0
    checks = {
        "operator_density":    lambda d: d["operator_density_delta"]    > thresholds.get("operator_density", 0.012),
        "conditionals_count":  lambda d: d["conditionals_count_delta"]  >= thresholds.get("conditionals_count", 1.0),
        "cognitive_complexity":lambda d: d["cognitive_complexity_delta"]>= thresholds.get("cognitive_complexity", 2.0),
        "nesting_complexity":  lambda d: d["nesting_complexity_delta"]  >= thresholds.get("nesting_complexity", 0.5),
        "cyclomatic_complexity":lambda d:d["cyclomatic_complexity_delta"]>= thresholds.get("cyclomatic_complexity", 1.0),
        "loops_count":         lambda d: d["loops_count_delta"]         >= thresholds.get("loops_count", 1.0),
        "literal_density":     lambda d: d["literal_density_delta"]     > thresholds.get("literal_density", 0.012),
    }
    for check in checks.values():
        if check(delta):
            worse_count += 1
    return worse_count


def calibrate_threshold(
    records: List[Dict[str, Any]], metric_key: str, baseline_energy: float
) -> Dict[str, Any]:
    """
    Find the delta threshold for a single proxy metric that best predicts
    energy improvement (i.e., energy_joules < baseline).

    A mutation 'improves energy' if its energy_joules < baseline_energy.
    We sweep candidate thresholds and pick the one maximising TPR - FPR
    for discarding degrading mutations.
    """
    # Collect (delta, improves_energy) pairs from measured mutations
    pairs = []
    for r in records:
        if r.get("evaluation_success") and r.get("metrics") and metric_key + "_delta" in r.get("proxy_deltas", {}):
            delta_val = r["proxy_deltas"][metric_key + "_delta"]
            energy = r["metrics"].get("energy_joules", float("inf"))
            improves = energy < baseline_energy
            pairs.append((delta_val, improves))

    if not pairs:
        return {"metric": metric_key, "best_threshold": None, "tpr_minus_fpr": None, "n": 0}

    # Sort unique delta values as candidate thresholds
    all_deltas = sorted({p[0] for p in pairs})
    best_thresh = None
    best_score = -float("inf")

    n_positive = sum(1 for _, imp in pairs if imp)     # mutations that improve energy
    n_negative = len(pairs) - n_positive                # mutations that don't improve energy

    for thresh in all_deltas:
        # "discard" = delta >= thresh (metric got worse)
        tp = sum(1 for d, imp in pairs if d >= thresh and not imp)  # correctly discarded bad mutations
        fp = sum(1 for d, imp in pairs if d >= thresh and imp)      # incorrectly discarded good mutations
        tpr = tp / n_negative if n_negative else 0.0
        fpr = fp / n_positive if n_positive else 0.0
        score = tpr - fpr
        if score > best_score:
            best_score = score
            best_thresh = thresh

    return {
        "metric": metric_key,
        "best_threshold": best_thresh,
        "tpr_minus_fpr": best_score,
        "n": len(pairs),
        "n_improving": n_positive,
        "n_degrading": n_negative,
    }


def analyze_run(run_dir: Path) -> Dict[str, Any]:
    mutations_log_path = run_dir / "mutations_log.json"
    if not mutations_log_path.exists():
        logger.error(f"mutations_log.json not found in {run_dir}")
        sys.exit(1)

    with open(mutations_log_path) as f:
        log: List[Dict[str, Any]] = json.load(f)

    logger.info(f"Loaded {len(log)} mutation log entries from {mutations_log_path}")

    # Extract baseline
    baseline_entry = next((e for e in log if e.get("variant_id") == "initial"), None)
    if baseline_entry is None:
        logger.error("No baseline ('initial') entry found in mutation log.")
        sys.exit(1)

    baseline_code = baseline_entry.get("code")
    if not baseline_code:
        logger.error("Baseline entry has no 'code' field. Re-run HEDGE to populate it.")
        sys.exit(1)

    baseline_features = extract_features(baseline_code)
    if baseline_features is None:
        logger.error("Failed to parse baseline code for feature extraction.")
        sys.exit(1)

    baseline_energy = baseline_entry.get("metrics", {}).get("energy_joules", float("inf"))
    baseline_time   = baseline_entry.get("metrics", {}).get("duration_seconds", float("inf"))
    logger.info(f"Baseline: energy={baseline_energy:.6f}J  time={baseline_time:.6f}s")

    # Process each entry
    enriched: List[Dict[str, Any]] = []
    skipped_no_code = 0

    for entry in log:
        if entry.get("variant_id") == "initial":
            continue

        code = entry.get("code")
        if not code:
            skipped_no_code += 1
            continue

        features = extract_features(code)
        if features is None:
            skipped_no_code += 1
            continue

        bf = baseline_features
        mf = features

        deltas = {
            "operator_density_delta":      mf.operator_density     - bf.operator_density,
            "literal_density_delta":       mf.literal_density      - bf.literal_density,
            "conditionals_count_delta":    mf.conditionals_count   - bf.conditionals_count,
            "loops_count_delta":           mf.loops_count          - bf.loops_count,
            "cyclomatic_complexity_delta": mf.cyclomatic_complexity - bf.cyclomatic_complexity,
            "cognitive_complexity_delta":  mf.cognitive_complexity  - bf.cognitive_complexity,
            "nesting_complexity_delta":    mf.nesting_complexity    - bf.nesting_complexity,
        }

        proxy_score = compute_proxy_score(deltas, {})  # with default thresholds

        entry_out = {
            "variant_id":      entry.get("variant_id"),
            "parent_id":       entry.get("parent_id"),
            "generation":      entry.get("generation"),
            "layer":           entry.get("layer") or "unknown",
            "mutator_name":    entry.get("mutator_name"),
            "strategy_name":   entry.get("strategy_name"),
            "validation_success":  entry.get("validation_success"),
            "evaluation_success":  entry.get("evaluation_success"),
            "in_pareto_archive":   entry.get("in_pareto_archive"),
            "metrics":         entry.get("metrics"),
            "proxy_features":  mf.as_dict(),
            "proxy_deltas":    deltas,
            "proxy_score":     proxy_score,   # # of metrics signalling 'worse' (default thresholds)
        }
        enriched.append(entry_out)

    logger.info(
        f"Enriched {len(enriched)} entries with proxy features "
        f"({skipped_no_code} skipped – missing code)"
    )

    # ------------------------------------------------------------------
    # Per-generation Pareto front (energy vs time, among measured mutations)
    # ------------------------------------------------------------------
    measured = [
        e for e in enriched
        if e["evaluation_success"] and e["metrics"]
           and "energy_joules" in e["metrics"]
           and "duration_seconds" in e["metrics"]
    ]

    generations_sorted = sorted({e["generation"] for e in measured})
    pareto_by_generation: Dict[int, List[Dict]] = {}

    for gen in generations_sorted:
        gen_items = [e for e in measured if e["generation"] == gen]
        if not gen_items:
            continue
        objectives_data = [
            {
                "energy_joules":    e["metrics"]["energy_joules"],
                "duration_seconds": e["metrics"]["duration_seconds"],
                "_ref": e,
            }
            for e in gen_items
        ]
        front = pareto_front(objectives_data, ["energy_joules", "duration_seconds"])
        pareto_by_generation[gen] = [item["_ref"] for item in front]

    # ------------------------------------------------------------------
    # Per-layer Pareto front
    # ------------------------------------------------------------------
    layers_found = sorted({e["layer"] for e in measured})
    pareto_by_layer: Dict[str, List[Dict]] = {}

    for layer in layers_found:
        layer_items = [e for e in measured if e["layer"] == layer]
        if not layer_items:
            continue
        objectives_data = [
            {
                "energy_joules":    e["metrics"]["energy_joules"],
                "duration_seconds": e["metrics"]["duration_seconds"],
                "_ref": e,
            }
            for e in layer_items
        ]
        front = pareto_front(objectives_data, ["energy_joules", "duration_seconds"])
        pareto_by_layer[layer] = [item["_ref"] for item in front]

    # ------------------------------------------------------------------
    # Threshold calibration per metric
    # ------------------------------------------------------------------
    metric_keys = [
        "operator_density", "literal_density", "conditionals_count",
        "loops_count", "cyclomatic_complexity", "cognitive_complexity",
        "nesting_complexity",
    ]
    calibration = [
        calibrate_threshold(enriched, mk, baseline_energy) for mk in metric_keys
    ]

    # ------------------------------------------------------------------
    # Proxy filter accuracy with default thresholds (discard_threshold=3)
    # ------------------------------------------------------------------
    DISCARD_THRESHOLD = 3
    true_positives = 0   # proxy says discard AND energy >= baseline (correctly skipped bad)
    false_negatives = 0  # proxy says discard BUT energy < baseline (missed improvement)
    true_negatives = 0   # proxy says measure AND energy >= baseline
    false_positives_filter = 0  # proxy says measure AND energy < baseline (correctly passed good)

    for e in measured:
        energy = e["metrics"]["energy_joules"]
        improves = energy < baseline_energy
        discarded_by_proxy = e["proxy_score"] >= DISCARD_THRESHOLD

        if discarded_by_proxy and not improves:
            true_positives += 1
        elif discarded_by_proxy and improves:
            false_negatives += 1
        elif not discarded_by_proxy and not improves:
            true_negatives += 1
        else:
            false_positives_filter += 1

    total_measured = len(measured)
    proxy_accuracy = {
        "discard_threshold": DISCARD_THRESHOLD,
        "total_measured": total_measured,
        "true_positives":  true_positives,   # bad mutations correctly flagged
        "false_negatives": false_negatives,  # good mutations incorrectly flagged (costly!)
        "true_negatives":  true_negatives,
        "false_positives": false_positives_filter,
        "precision":   true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else None,
        "recall":      true_positives / (true_positives + true_negatives) if (true_positives + true_negatives) > 0 else None,
        "fn_rate":     false_negatives / total_measured if total_measured else None,
    }

    # ------------------------------------------------------------------
    # Summary print
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PROXY METRICS ANALYSIS REPORT")
    print("=" * 70)
    print(f"Run directory : {run_dir}")
    print(f"Total entries : {len(log)}  |  Enriched: {len(enriched)}  |  Measured: {total_measured}")
    print(f"Baseline      : energy={baseline_energy:.6f}J  time={baseline_time:.6f}s")
    print()

    print("── Per-generation Pareto front sizes ──")
    for gen, front in sorted(pareto_by_generation.items()):
        energies = [e["metrics"]["energy_joules"] for e in front]
        print(f"  Gen {gen:2d}: {len(front)} solution(s)  "
              f"energy range [{min(energies):.6f}, {max(energies):.6f}] J")

    print()
    print("── Per-layer Pareto front sizes ──")
    for layer, front in sorted(pareto_by_layer.items()):
        energies = [e["metrics"]["energy_joules"] for e in front]
        print(f"  {layer or 'unknown':20s}: {len(front)} solution(s)  "
              f"energy range [{min(energies):.6f}, {max(energies):.6f}] J")

    print()
    print("── Threshold calibration (maximise TPR−FPR for discarding bad mutations) ──")
    for cal in sorted(calibration, key=lambda x: -(x["tpr_minus_fpr"] or -1)):
        thresh_str = f"{cal['best_threshold']:.4f}" if cal["best_threshold"] is not None else "N/A"
        score_str  = f"{cal['tpr_minus_fpr']:.3f}"  if cal["tpr_minus_fpr"]  is not None else "N/A"
        print(f"  {cal['metric']:30s}  threshold={thresh_str:8s}  TPR−FPR={score_str}  "
              f"(n={cal['n']}, n_improving={cal.get('n_improving',0)}, n_degrading={cal.get('n_degrading',0)})")

    print()
    print("── Proxy filter accuracy (default thresholds, discard_threshold=3) ──")
    print(f"  True positives  (bad correctly skipped) : {true_positives}")
    print(f"  False negatives (good incorrectly skipped): {false_negatives}  ← COSTLY")
    print(f"  True negatives                           : {true_negatives}")
    print(f"  False positives (good passed through)    : {false_positives_filter}")
    if proxy_accuracy["fn_rate"] is not None:
        print(f"  False-negative rate                      : {proxy_accuracy['fn_rate']:.1%}")
    print("=" * 70 + "\n")

    return {
        "baseline": {
            "energy_joules":    baseline_energy,
            "duration_seconds": baseline_time,
        },
        "enriched_mutations": enriched,
        "pareto_by_generation": {
            str(k): v for k, v in pareto_by_generation.items()
        },
        "pareto_by_layer": pareto_by_layer,
        "threshold_calibration": calibration,
        "proxy_accuracy": proxy_accuracy,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyse proxy metrics vs. actual energy for a HEDGE run"
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to HEDGE experiment output directory (must contain mutations_log.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Save analysis report as JSON (default: <run_dir>/proxy_analysis.json)",
    )
    args = parser.parse_args()

    run_dir = args.run_dir
    if not run_dir.exists():
        logger.error(f"Directory not found: {run_dir}")
        sys.exit(1)

    report = analyze_run(run_dir)

    out_path = args.output or (run_dir / "proxy_analysis.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Full report saved to: {out_path}")


if __name__ == "__main__":
    main()
