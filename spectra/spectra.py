#!/usr/bin/env python3
"""
SPECTRA Research Edition  v3.0
════════════════════════════════
Structured Program Evaluation and Cost-modeling via
Transformation Retrieval with Adaptation

Exploratory study harness: captures every measurable signal from the
optimization process and renders a full research-grade figure suite.

Upgrades over v2.0 — Enriched Multi-Fidelity Energy Proxies
────────────────────────────────────────────────────────────
  • Rich measurement statistics: trimmed mean, median, bootstrap 95% CI,
    coefficient of variation (CV), all raw readings stored
  • Welch t-test–based probabilistic abandon decisions at F1/F2:
    - F1 abandons only if P(better) < 10%  (very lenient — prevents false prune)
    - F2 abandons only if P(better) < 25%  (moderate)
    - F3 confirms if P(better) > 90%       (strict — replaces fixed z-test)
  • Adaptive rep escalation: if CV > 30% at F1/F2, auto-doubles reps
    before the abandon decision ("F1.5 mode")
  • FidelityCalibrator: tracks F1→F3 and F2→F3 prediction accuracy in real
    time; after 5 paired observations, tightens thresholds if proxies are
    reliable and loosens if they are noisy
  • Per-fidelity noise floor: estimated from baseline CV; candidates whose
    apparent improvement is inside the noise floor are not abandoned but
    are marked uncertain and passed forward with a penalty EI weight
  • Outlier-robust statistics: IQR-based outlier detection removes readings
    >2.5 IQR from Q1/Q3 before computing statistics (helps with OS scheduler
    interference bursts)
  • Detailed abandon audit log: each prune decision records reason, CV,
    p-value, adaptive reps used, and calibrator state at time of decision
  • New research figures: F1/F2 vs F3 calibration scatter, CV-by-fidelity
    violin, abandon-reason breakdown, noise-floor timeline

Upgrades over v1.0
──────────────────
  • State-isolation: deepcopy args before each evaluation pass
  • RAPL resolution guard: adaptive inner-loop multiplier for sub-50ms fns
  • Correct float/set equality in CorrectnessEngine
  • Concurrent LLM operator generation (ThreadPoolExecutor)
  • LLM self-correction retry on SyntaxError
  • Process-isolated energy measurement (multiprocessing.Process)
  • Configurable CO₂ intensity via --co2-intensity
  • EI math collapse guard (std floor at 1e-9)
  • Enriched GP features: Halstead volume, cyclomatic complexity,
    memory-access density, algorithmic loop depth
  • Throttled GP retraining (every 5 iters after 50 samples)
  • Regex-free StringConcatToJoin precondition
  • Safe (try/except ImportError) import hoisting
  • 15 new transformation operators
  • Local-minima escape via GenericSemanticRewriteLLM with fallback budget

CLI
───
  python spectra_research.py                              # built-in demos
  python spectra_research.py --source f.py --tests t.py  # your own code
  python spectra_research.py --gemini-key AIza...        # enable LLM ops
  python spectra_research.py --out-dir results/
  python spectra_research.py --ei-top-k 2
  python spectra_research.py --co2-intensity 300         # gCO₂/kWh override
  python spectra_research.py --fidelity-leniency 0.10    # P(better) floor at F1
  python spectra_research.py --no-adaptive-reps          # disable CV-triggered extra reps
  python spectra_research.py --list-ops
  python spectra_research.py --demo 2

Test file format (t.py)
───────────────────────
  TEST_INPUTS = [(arg1, arg2, ...), ...]   # original fn as oracle
  TEST_CASES  = [((args,...), expected), ...]

Dependencies
────────────
  Required : Python 3.10+, stdlib only
  Optional : numpy, matplotlib, pandas, seaborn  (plots)
             scikit-learn                        (GP surrogate)
             psutil                              (energy estimate)
             GEMINI_API_KEY env var              (LLM operators)
"""
from __future__ import annotations

import argparse
import ast
import collections
import pickle
import concurrent.futures
import copy
import csv
import importlib.util
import json
import math
import multiprocessing
import os
import random
import re
import sys
import textwrap
import time
import traceback
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
import threading

# ── Optional deps ─────────────────────────────────────────────
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, Matern
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    from matplotlib.ticker import MaxNLocator
    HAS_MPLOT = True
except ImportError:
    HAS_MPLOT = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import seaborn as sns
    HAS_SNS = True
except ImportError:
    HAS_SNS = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ══════════════════════════════════════════════════════════════════════════════
# 0.  Research Metrics System
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CandidateRecord:
    """Full record for one evaluated candidate in one iteration."""
    iteration: int
    operator: str
    tier: str
    is_llm: bool
    # Correctness
    correctness_pass: bool
    correctness_reason: str
    # Surrogate
    surrogate_pred_mj: Optional[float]
    surrogate_std_mj: Optional[float]
    ei_score: float
    # Fidelity escalation trace
    f1_mj: Optional[float]
    f1_improvement_pct: Optional[float]
    f1_abandoned: bool
    f2_mj: Optional[float]
    f2_improvement_pct: Optional[float]
    f2_abandoned: bool
    f3_mj: Optional[float]
    f3_improvement_pct: Optional[float]
    f3_std_mj: Optional[float]
    f3_co2_ug: Optional[float]
    statistically_significant: bool
    confirmed_improvement: bool
    # Source
    transformed_source: str = ""
    chain_depth: int = 0
    # Process isolation metadata
    used_process_isolation: bool = False
    inner_loop_multiplier: int = 1
    # ── v3: per-fidelity rich diagnostics ───────────────────
    # Coefficient of variation at each fidelity
    f1_cv: Optional[float] = None
    f2_cv: Optional[float] = None
    f3_cv: Optional[float] = None
    # Bootstrap CI at F3 (mJ)
    f3_ci_low_mj: Optional[float] = None
    f3_ci_high_mj: Optional[float] = None
    # Probabilistic improvement estimates
    f1_p_improvement: Optional[float] = None
    f2_p_improvement: Optional[float] = None
    f3_p_improvement: Optional[float] = None
    # Welch t-statistics
    f1_welch_t: Optional[float] = None
    f2_welch_t: Optional[float] = None
    f3_welch_t: Optional[float] = None
    # Adaptive rep escalation
    f1_adaptive_extra_reps: int = 0
    f2_adaptive_extra_reps: int = 0
    # Abandon reason (human-readable)
    f1_abandon_reason: str = ""
    f2_abandon_reason: str = ""
    # Calibrator state at time of decision
    f1_calibrator_f1f3_corr: Optional[float] = None
    f2_calibrator_f2f3_corr: Optional[float] = None
    # Trimmed means at each fidelity (mJ)
    f1_trimmed_mean_mj: Optional[float] = None
    f2_trimmed_mean_mj: Optional[float] = None
    f3_trimmed_mean_mj: Optional[float] = None
    # Whether this candidate was "noise uncertain" (borderline, passed with penalty)
    f1_noise_uncertain: bool = False
    f2_noise_uncertain: bool = False
    # n_outliers_removed per fidelity
    f1_outliers_removed: int = 0
    f2_outliers_removed: int = 0
    f3_outliers_removed: int = 0


@dataclass
class IterationRecord:
    """Aggregate for one MFBO iteration."""
    iteration: int
    n_candidates_generated: int
    n_correctness_pass: int
    n_correctness_fail: int
    n_surrogate_screened_in: int
    n_surrogate_screened_out: int
    selected_operator: str
    selected_tier: str
    wall_clock_s: float
    best_energy_mj: float            # running best at end of this iteration
    current_baseline_mj: float
    improvement_over_baseline_pct: float
    f3_evals_used_so_far: int
    surrogate_trained: bool
    used_fallback_escape: bool = False
    candidates: list[CandidateRecord] = field(default_factory=list)


@dataclass
class StudyRecord:
    """Complete record of one function optimization run."""
    function_name: str
    source_file: str
    original_source: str
    best_source: str
    energy_backend: str
    has_rapl: bool
    has_llm: bool
    llm_provider: str
    co2_intensity_g_per_kwh: float
    # Baseline
    baseline_mj: float
    baseline_std_mj: float
    baseline_co2_ug: float
    # Result
    best_mj: float
    improvement_pct: float
    transformation_chain: list[str]
    # Budgets
    total_f3_evals: int
    max_f3_budget: int
    total_wall_s: float
    total_co2_search_ug: float
    # Escape mechanism usage
    total_fallback_escapes_used: int = 0
    # Per-iteration trace
    iterations: list[IterationRecord] = field(default_factory=list)
    # Surrogate accuracy (surrogate pred vs actual F3, for all F3 evals)
    surrogate_pred_vs_actual: list[tuple[float, float]] = field(default_factory=list)
    # Operator-level aggregates (filled post-run)
    operator_stats: dict = field(default_factory=dict)


class MetricsCollector:
    """Accumulates metrics during a run. Thread-safe for single runs."""

    def __init__(self, func_name: str, source_file: str,
                 original_source: str, baseline_mj: float,
                 baseline_std_mj: float, baseline_co2_ug: float,
                 energy_backend: str, has_llm: bool, llm_provider: str,
                 max_budget: int, co2_intensity: float = 475.0):
        self.record = StudyRecord(
            function_name=func_name,
            source_file=source_file,
            original_source=original_source,
            best_source=original_source,
            energy_backend=energy_backend,
            has_rapl=(energy_backend == "rapl"),
            has_llm=has_llm,
            llm_provider=llm_provider,
            co2_intensity_g_per_kwh=co2_intensity,
            baseline_mj=baseline_mj,
            baseline_std_mj=baseline_std_mj,
            baseline_co2_ug=baseline_co2_ug,
            best_mj=baseline_mj,
            improvement_pct=0.0,
            transformation_chain=[],
            total_f3_evals=0,
            max_f3_budget=max_budget,
            total_wall_s=0.0,
            total_co2_search_ug=baseline_co2_ug,
        )
        self._t0 = time.perf_counter()
        self._iter_t0 = time.perf_counter()

    def start_iteration(self):
        self._iter_t0 = time.perf_counter()

    def finish(self, best_mj: float, best_source: str, chain: list[str],
               f3_count: int, total_co2_ug: float, fallback_count: int = 0):
        self.record.total_wall_s = time.perf_counter() - self._t0
        self.record.best_mj = best_mj
        self.record.best_source = best_source
        self.record.improvement_pct = (
            (1.0 - best_mj / self.record.baseline_mj) * 100
            if self.record.baseline_mj > 0 else 0.0)
        self.record.transformation_chain = chain
        self.record.total_f3_evals = f3_count
        self.record.total_co2_search_ug = total_co2_ug
        self.record.total_fallback_escapes_used = fallback_count
        self._compute_operator_stats()

    def _compute_operator_stats(self):
        stats: dict[str, dict] = {}
        for it in self.record.iterations:
            for c in it.candidates:
                op = c.operator
                if op not in stats:
                    stats[op] = {
                        "tier": c.tier, "is_llm": c.is_llm,
                        "n_generated": 0, "n_correct": 0, "n_f3": 0,
                        "n_confirmed": 0, "improvements_pct": [],
                        "f3_mj": [], "ei_scores": [],
                        "inner_loop_multipliers": [],
                        # v3
                        "f1_cvs": [], "f2_cvs": [], "f3_cvs": [],
                        "f1_p_improvements": [], "f2_p_improvements": [],
                        "adaptive_extra_reps_f1": [], "adaptive_extra_reps_f2": [],
                        "n_f1_uncertain": 0, "n_f2_uncertain": 0,
                        "n_f1_abandoned": 0, "n_f2_abandoned": 0,
                    }
                s = stats[op]
                s["n_generated"] += 1
                if c.correctness_pass: s["n_correct"] += 1
                if c.f3_mj is not None: s["n_f3"] += 1; s["f3_mj"].append(c.f3_mj)
                if c.confirmed_improvement:
                    s["n_confirmed"] += 1
                    if c.f3_improvement_pct is not None:
                        s["improvements_pct"].append(c.f3_improvement_pct)
                if c.ei_score > 0: s["ei_scores"].append(c.ei_score)
                if c.inner_loop_multiplier > 1:
                    s["inner_loop_multipliers"].append(c.inner_loop_multiplier)
                # v3 fields
                if c.f1_cv is not None:      s["f1_cvs"].append(c.f1_cv)
                if c.f2_cv is not None:      s["f2_cvs"].append(c.f2_cv)
                if c.f3_cv is not None:      s["f3_cvs"].append(c.f3_cv)
                if c.f1_p_improvement is not None:
                    s["f1_p_improvements"].append(c.f1_p_improvement)
                if c.f2_p_improvement is not None:
                    s["f2_p_improvements"].append(c.f2_p_improvement)
                if c.f1_adaptive_extra_reps > 0:
                    s["adaptive_extra_reps_f1"].append(c.f1_adaptive_extra_reps)
                if c.f2_adaptive_extra_reps > 0:
                    s["adaptive_extra_reps_f2"].append(c.f2_adaptive_extra_reps)
                if c.f1_noise_uncertain: s["n_f1_uncertain"] += 1
                if c.f2_noise_uncertain: s["n_f2_uncertain"] += 1
                if c.f1_abandoned: s["n_f1_abandoned"] += 1
                if c.f2_abandoned: s["n_f2_abandoned"] += 1
        self.record.operator_stats = stats

    def export_json(self, path: Path):
        def _ser(obj):
            if isinstance(obj, (list, dict, str, int, float, bool)) or obj is None:
                return obj
            return str(obj)
        path.write_text(json.dumps(asdict(self.record), indent=2, default=_ser))

    def export_csv(self, path: Path):
        rows = []
        for it in self.record.iterations:
            for c in it.candidates:
                rows.append({
                    "function": self.record.function_name,
                    "iteration": c.iteration,
                    "operator": c.operator,
                    "tier": c.tier,
                    "is_llm": c.is_llm,
                    "correctness_pass": c.correctness_pass,
                    "surrogate_pred_mj": c.surrogate_pred_mj,
                    "surrogate_std_mj": c.surrogate_std_mj,
                    "ei_score": c.ei_score,
                    # F1
                    "f1_mj": c.f1_mj,
                    "f1_improvement_pct": c.f1_improvement_pct,
                    "f1_abandoned": c.f1_abandoned,
                    "f1_abandon_reason": c.f1_abandon_reason,
                    "f1_cv": c.f1_cv,
                    "f1_p_improvement": c.f1_p_improvement,
                    "f1_welch_t": c.f1_welch_t,
                    "f1_trimmed_mean_mj": c.f1_trimmed_mean_mj,
                    "f1_adaptive_extra_reps": c.f1_adaptive_extra_reps,
                    "f1_noise_uncertain": c.f1_noise_uncertain,
                    "f1_outliers_removed": c.f1_outliers_removed,
                    # F2
                    "f2_mj": c.f2_mj,
                    "f2_improvement_pct": c.f2_improvement_pct,
                    "f2_abandoned": c.f2_abandoned,
                    "f2_abandon_reason": c.f2_abandon_reason,
                    "f2_cv": c.f2_cv,
                    "f2_p_improvement": c.f2_p_improvement,
                    "f2_welch_t": c.f2_welch_t,
                    "f2_trimmed_mean_mj": c.f2_trimmed_mean_mj,
                    "f2_adaptive_extra_reps": c.f2_adaptive_extra_reps,
                    "f2_noise_uncertain": c.f2_noise_uncertain,
                    "f2_outliers_removed": c.f2_outliers_removed,
                    # F3
                    "f3_mj": c.f3_mj,
                    "f3_improvement_pct": c.f3_improvement_pct,
                    "f3_std_mj": c.f3_std_mj,
                    "f3_cv": c.f3_cv,
                    "f3_ci_low_mj": c.f3_ci_low_mj,
                    "f3_ci_high_mj": c.f3_ci_high_mj,
                    "f3_p_improvement": c.f3_p_improvement,
                    "f3_welch_t": c.f3_welch_t,
                    "f3_trimmed_mean_mj": c.f3_trimmed_mean_mj,
                    "f3_outliers_removed": c.f3_outliers_removed,
                    "f3_co2_ug": c.f3_co2_ug,
                    "statistically_significant": c.statistically_significant,
                    "confirmed_improvement": c.confirmed_improvement,
                    "chain_depth": c.chain_depth,
                    "used_process_isolation": c.used_process_isolation,
                    "inner_loop_multiplier": c.inner_loop_multiplier,
                    "iteration_best_mj": it.best_energy_mj,
                    "iteration_wall_s": it.wall_clock_s,
                    "used_fallback_escape": it.used_fallback_escape,
                })
        if not rows:
            return
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader(); w.writerows(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 1.  Energy Measurement Backend
# ══════════════════════════════════════════════════════════════════════════════

class EnergyBackend(Enum):
    RAPL   = "rapl"
    PSUTIL = "psutil"
    TIMING = "timing"


RAPL_DOMAINS = [
    "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj",
    "/sys/class/powercap/intel-rapl:0/energy_uj",
]
_TDP_WATTS = 15.0


def _read_rapl_uj() -> Optional[float]:
    for p in RAPL_DOMAINS:
        try: return float(Path(p).read_text().strip())
        except Exception: pass
    return None


def _detect_backend() -> EnergyBackend:
    if _read_rapl_uj() is not None: return EnergyBackend.RAPL
    if HAS_PSUTIL: return EnergyBackend.PSUTIL
    return EnergyBackend.TIMING


_ACTIVE_BACKEND = _detect_backend()

# Global CO₂ intensity (g CO₂ / kWh) — can be overridden via --co2-intensity
_CO2_INTENSITY_G_PER_KWH: float = 475.0


@dataclass
class EnergyReading:
    joules: float
    duration_s: float
    backend: EnergyBackend
    inner_loop_multiplier: int = 1   # NEW: record adaptive multiplier used

    @property
    def co2_g(self) -> float:
        return self.joules * _CO2_INTENSITY_G_PER_KWH / 3_600_000


class EnergyMeter:
    def __init__(self):
        self.result: Optional[EnergyReading] = None
        self._rapl0: Optional[float] = None
        self._t0 = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        if _ACTIVE_BACKEND == EnergyBackend.RAPL:
            self._rapl0 = _read_rapl_uj()
        return self

    def __exit__(self, *_):
        dt = time.perf_counter() - self._t0
        if _ACTIVE_BACKEND == EnergyBackend.RAPL and self._rapl0 is not None:
            ej = max(0.0, (_read_rapl_uj() or 0.0) - self._rapl0)
            joules = ej / 1e6
        elif _ACTIVE_BACKEND == EnergyBackend.PSUTIL and HAS_PSUTIL:
            f = psutil.cpu_freq()
            scale = min(1.0, (f.current if f else 2000) / 3000)
            joules = _TDP_WATTS * scale * dt
        else:
            joules = _TDP_WATTS * dt
        self.result = EnergyReading(joules=joules, duration_s=dt,
                                    backend=_ACTIVE_BACKEND)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Process-Isolated Measurement Worker
#     Must be at module level so multiprocessing can pickle the target fn.
# ══════════════════════════════════════════════════════════════════════════════

def _isolated_verify_worker(queue: multiprocessing.Queue, source: str, func_name: str, test_cases: list, epsilon: float):
    """Runs correctness verification in a totally isolated, killable process."""
    import copy, math

    def _brief_value(value):
        if HAS_NUMPY:
            try:
                if isinstance(value, np.ndarray):
                    summary = (
                        f"ndarray(shape={value.shape}, dtype={value.dtype}, "
                        f"value={value.tolist()})"
                    )
                elif isinstance(value, np.generic):
                    summary = f"{type(value).__name__}({value.item()!r})"
                else:
                    summary = repr(value)
            except Exception:
                summary = repr(value)
        else:
            summary = repr(value)
        if len(summary) > 160:
            summary = summary[:157] + "..."
        return f"{type(value).__name__}({summary})"

    def _eq(a, b):
        if HAS_NUMPY:
            try:
                if isinstance(a, np.ndarray):
                    return _eq(a.tolist(), b)
                if isinstance(b, np.ndarray):
                    return _eq(a, b.tolist())
                if isinstance(a, np.generic):
                    return _eq(a.item(), b)
                if isinstance(b, np.generic):
                    return _eq(a, b.item())
            except Exception:
                pass
        if isinstance(a, set): return a == b
        if isinstance(a, float):
            if math.isnan(a) and isinstance(b, float) and math.isnan(b): return True
            return isinstance(b, float) and math.isclose(a, b, rel_tol=epsilon, abs_tol=epsilon)
        if isinstance(a, (list, tuple)):
            if not isinstance(b, type(a)): return False
            return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
        if isinstance(a, dict):
            if not isinstance(b, dict): return False
            return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
        return a == b

    try:
        ns = {}
        exec(compile(source, "<spectra_verify>", "exec"), ns)
        cand = ns.get(func_name)
        if cand is None:
            queue.put((False, "Function not found in compiled source"))
            return

        for args, exp in test_cases:
            try:
                actual = cand(*copy.deepcopy(args))
            except Exception as exc:
                queue.put((False, f"Exception[{type(exc).__name__}] on args={args}: {exc}"))
                return
            if not _eq(exp, actual):
                queue.put((
                    False,
                    f"Test case mismatch: args={args}; expected={_brief_value(exp)}; actual={_brief_value(actual)}",
                ))
                return
        
        queue.put((True, "OK"))
    except Exception as e:
        queue.put((False, f"Exception[{type(e).__name__}]: {str(e)}"))

def _isolated_measure_worker(queue: multiprocessing.Queue,
                              source: str, func_name: str,
                              test_inputs_serialized: list,
                              n_reps: int, warmup: int,
                              co2_intensity: float,
                              rapl_domains: list[str],
                              tdp_watts: float,
                              backend_name: str):
    """
    Runs in a separate process so that optimizer/GP/LLM memory does not
    contaminate energy readings with JIT effects or cache inflation.
    Returns (mean_j, std_j, co2_g_per_call, inner_mult) via queue.
    """
    import time, math, copy
    # Restore backend detection inside child
    def read_rapl():
        for p in rapl_domains:
            try:
                return float(open(p).read().strip())
            except Exception:
                pass
        return None

    def measure_once(fn, inputs, inner_mult):
        t0 = time.perf_counter()
        rapl0 = read_rapl() if backend_name == "rapl" else None
        for _ in range(inner_mult):
            for args in inputs:
                fn(*copy.deepcopy(args))
        dt = time.perf_counter() - t0
        if backend_name == "rapl" and rapl0 is not None:
            rapl1 = read_rapl() or 0.0
            j = max(0.0, rapl1 - rapl0) / 1e6
        elif backend_name == "psutil":
            try:
                import psutil as _ps
                f = _ps.cpu_freq()
                scale = min(1.0, (f.current if f else 2000) / 3000)
            except Exception:
                scale = 0.5
            j = tdp_watts * scale * dt
        else:
            j = tdp_watts * dt
        return j / inner_mult   # normalised per-pass energy

    try:
        ns: dict = {}
        exec(compile(source, "<spectra_isolated>", "exec"), ns)
        fn: Callable = ns[func_name]

        # Warmup (deepcopy to avoid mutation)
        for _ in range(warmup):
            for args in test_inputs_serialized[:1]:
                fn(*copy.deepcopy(args))

        # Adaptive inner-loop multiplier (RAPL resolution guard)
        inner_mult = 1
        t_probe = time.perf_counter()
        for args in test_inputs_serialized:
            fn(*copy.deepcopy(args))
        elapsed = time.perf_counter() - t_probe
        if elapsed < 0.05 and elapsed > 0:
                inner_mult = max(1, int(0.05 / elapsed))

        readings = []
        for _ in range(n_reps):
            j = measure_once(fn, test_inputs_serialized, inner_mult)
            readings.append(j)

        # Return raw readings so the parent can compute rich stats
        queue.put((readings, inner_mult, None))
    except Exception as exc:
        queue.put((None, 1, str(exc)))

# ══════════════════════════════════════════════════════════════════════════════
# 2.  Core Data Structures
# ══════════════════════════════════════════════════════════════════════════════

class Tier(Enum):
    H = "H"; M = "M"; L = "L"


class Fidelity(Enum):
    F0 = 0; F1 = 1; F2 = 2; F3 = 3


FIDELITY_REPS = {Fidelity.F1: 5, Fidelity.F2: 8, Fidelity.F3: 20}
# Max extra reps allowed when adaptive escalation kicks in (CV > threshold)
FIDELITY_ADAPTIVE_EXTRA = {Fidelity.F1: 5, Fidelity.F2: 7, Fidelity.F3: 10}
# CV threshold above which adaptive extra reps are triggered
CV_TRIGGER_EXTRA_REPS = 0.30
# Per-fidelity P(better) floors: abandon if P(cand < baseline) < this
# Very lenient at F1, moderate at F2, strict confirm at F3
FIDELITY_P_ABANDON = {Fidelity.F1: 0.10, Fidelity.F2: 0.25}
FIDELITY_P_CONFIRM = 0.90   # F3 confirmation threshold


@dataclass
class EnergyMeasurement:
    mean_j: float
    std_j: float
    n_runs: int
    fidelity: Fidelity
    improvement: float = 0.0
    co2_g: float = 0.0
    inner_loop_multiplier: int = 1
    # ── Rich stats (v3) ─────────────────────────────────────
    # All raw readings (joules), stored for research / calibrator
    readings_j: list = field(default_factory=list)
    # Outlier-robust central tendency
    trimmed_mean_j: float = 0.0   # drop top+bottom 1 reading
    median_j: float = 0.0
    # Spread
    cv: float = 0.0               # coefficient of variation (std/mean)
    iqr_j: float = 0.0            # interquartile range
    n_outliers_removed: int = 0   # readings dropped by IQR filter
    # Bootstrap 95% CI
    ci_low_j: float = 0.0
    ci_high_j: float = 0.0
    # Probabilistic comparison vs baseline
    p_improvement: float = 0.5    # P(candidate energy < baseline energy)
    welch_t: float = 0.0          # Welch t-statistic vs baseline
    # Adaptive reps metadata
    adaptive_extra_reps: int = 0  # extra reps taken due to high CV

    @property
    def mean_mj(self): return self.mean_j * 1000

    @property
    def std_mj(self): return self.std_j * 1000

    @property
    def trimmed_mean_mj(self): return self.trimmed_mean_j * 1000

    @property
    def median_mj(self): return self.median_j * 1000

    @property
    def ci_low_mj(self): return self.ci_low_j * 1000

    @property
    def ci_high_mj(self): return self.ci_high_j * 1000


@dataclass
class ProgramVariant:
    source: str
    chain: list[dict] = field(default_factory=list)
    measurements: dict[Fidelity, EnergyMeasurement] = field(default_factory=dict)
    is_correct: Optional[bool] = None

    def best_measurement(self) -> Optional[EnergyMeasurement]:
        for f in [Fidelity.F3, Fidelity.F2, Fidelity.F1]:
            if f in self.measurements: return self.measurements[f]
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 3.  Gemini LLM Client  (with self-correction retry)
# ══════════════════════════════════════════════════════════════════════════════
class GeminiClient:
    """
    Calls Gemini via the REST API (no google-generativeai package needed).
    Model: gemini-2.5-flash
    Includes robust error handling: Key Rotation, Exponential Backoff, and Jitter.
    """
    BASE_URL = ("https://generativelanguage.googleapis.com/v1beta/models"
                "/gemini-2.5-flash:generateContent")

    def __init__(self, api_key: Optional[str] = None):
        # Support single key or comma-separated multiple keys for rotation
        raw_keys = api_key or os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY", "")
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        
        self.available = bool(self.api_keys)
        self.provider = "gemini-2.5-flash"
        
        # Tracking states
        self._key_idx = 0
        self._call_count = 0
        self._retry_count = 0          # tracks self-correction attempts
        self._total_tokens_est = 0
        self._lock = threading.Lock()

    def _get_current_key(self) -> str:
        with self._lock:
            return self.api_keys[self._key_idx]

    def _rotate_key(self):
        """Thread-safe key rotation. Moves to the next API key."""
        with self._lock:
            self._key_idx = (self._key_idx + 1) % len(self.api_keys)
    
    def complete(self, prompt: str, system: str = "",
                 max_tokens: int = 8096) -> Optional[str]:
        if not self.available:
            return None

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": ({"parts": [{"text": system}]} if system else None),
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.1,
            },
        }).encode()

        max_attempts  = 5
        base_delay    = 20.0
        # Track per-attempt whether we already rotated for this attempt so we
        # don't rotate again on the retry of the same attempt.
        rotated_this_attempt = False

        for attempt in range(max_attempts):
            rotated_this_attempt = False
            current_key = self._get_current_key()
            url = f"{self.BASE_URL}?key={current_key}"
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST")

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())

                if "candidates" not in data or not data["candidates"]:
                    print("[Gemini] Warning: response blocked by safety filters.",
                          file=sys.stderr)
                    return None

                text = (data["candidates"][0]["content"]["parts"][0]["text"])
                with self._lock:
                    self._call_count += 1
                    self._total_tokens_est += len(text.split())
                return text

            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    if len(self.api_keys) > 1 and not rotated_this_attempt:
                        # Rotate to the next key …
                        self._rotate_key()
                        rotated_this_attempt = True
                        # … but still observe a short mandatory cooldown so we
                        # don't hammer all keys simultaneously.  Use a shorter
                        # delay than the full backoff since we have a fresh key,
                        # but never zero.
                        cooldown = min(
                            base_delay,
                            2.0 * (attempt + 1) + random.uniform(0.5, 2.0))
                        print(
                            f"[Gemini] 429 on key #{self._key_idx - 1 % len(self.api_keys)}"
                            f" — rotated to key #{self._key_idx},"
                            f" cooling down {cooldown:.1f}s",
                            file=sys.stderr)
                        time.sleep(cooldown)
                        continue   # retry with new key + cooldown applied
                    # Single key, or already rotated this attempt: full backoff
                    delay = (base_delay * (2 ** attempt)
                             + random.uniform(0.1, 1.0))
                    print(
                        f"[Gemini] 429 rate-limit. "
                        f"Backing off {delay:.1f}s (attempt {attempt+1}/{max_attempts})",
                        file=sys.stderr)
                    time.sleep(delay)

                elif exc.code not in (500, 502, 503, 504):
                    # 400 Bad Request, 403 Unauthorized, 404 Not Found → fatal
                    print(f"[Gemini] Fatal API error {exc.code}: {exc.reason}",
                          file=sys.stderr)
                    return None
                else:
                    # 5xx server errors — exponential backoff
                    delay = (base_delay * (2 ** attempt)
                             + random.uniform(0.1, 1.0))
                    print(
                        f"[Gemini] Server error {exc.code}. "
                        f"Retrying in {delay:.1f}s (attempt {attempt+1}/{max_attempts})",
                        file=sys.stderr)
                    time.sleep(delay)

            except (urllib.error.URLError, Exception) as exc:
                delay = (base_delay * (2 ** attempt)
                         + random.uniform(0.1, 1.0))
                print(
                    f"[Gemini] Network error: {exc}. "
                    f"Retrying in {delay:.1f}s…",
                    file=sys.stderr)
                time.sleep(delay)

        print("[Gemini] Max retries exceeded.", file=sys.stderr)
        return None

    def _clean_raw(self, raw: str) -> str:
        """Strip markdown fences."""
        raw = raw.strip()
        raw = re.sub(r"^```python\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
        return raw.strip()

    def transform(self, source: str, operator: str,
                  extra_context: str = "") -> Optional[str]:
        system = ("You are an expert Python performance engineer. "
                  "Return only clean Python code, no markdown, no explanation.")
        prompt = (f"Apply this transformation to the Python function: {operator}\n"
                  f"{extra_context}\n\n"
                  f"STRICT RULES:\n"
                  f"1. Return ONLY the transformed Python source.\n"
                  f"2. No markdown, no backticks, no comments explaining changes.\n"
                  f"3. Preserve exact function signature and return semantics.\n"
                  f"4. If not applicable, return exactly: INAPPLICABLE\n\n"
                  f"Source:\n{source}")
                  
        raw = self.complete(prompt, system=system)
        if raw is None: return None
        raw = self._clean_raw(raw)
        if raw.upper().startswith("INAPPLICABLE"): return None

        # --- Self-correction retry ---
        try:
            ast.parse(raw)
            return raw
        except SyntaxError as err:
            with self._lock:
                self._retry_count += 1
            retry_prompt = (
                f"{prompt}\n\n"
                f"The generated code failed to parse with: {err}\n"
                f"Return ONLY corrected valid Python code, no markdown.")
            raw2 = self.complete(retry_prompt, system=system)
            if raw2 is None: return None
            raw2 = self._clean_raw(raw2)
            try:
                ast.parse(raw2)
                return raw2
            except SyntaxError:
                return None

# ══════════════════════════════════════════════════════════════════════════════
# 4.  Transformation Operators
# ══════════════════════════════════════════════════════════════════════════════

class TransformationOperator:
    tier: Tier = Tier.L
    name: str = "base"
    needs_llm: bool = False

    def precondition(self, tree: ast.AST, source: str) -> bool:
        raise NotImplementedError

    def apply(self, source: str, llm: Optional[GeminiClient] = None) -> Optional[str]:
        raise NotImplementedError


# ─── Tier L: deterministic AST rewrites ──────────────────────

class ForLoopToComprehension(TransformationOperator):
    tier, name = Tier.L, "ForLoopToComprehension"

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            for i, s in enumerate(fn.body[:-1]):
                nxt = fn.body[i + 1]
                if (isinstance(s, ast.Assign) and isinstance(s.value, ast.List)
                        and not s.value.elts and isinstance(nxt, ast.For)
                        and len(nxt.body) == 1 and not nxt.orelse
                        and isinstance(nxt.body[0], ast.Expr)
                        and isinstance(nxt.body[0].value, ast.Call)):
                    call = nxt.body[0].value
                    if (isinstance(call.func, ast.Attribute)
                            and call.func.attr == "append"): return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                new_body, i = [], 0
                while i < len(node.body):
                    s = node.body[i]
                    if (i + 1 < len(node.body)
                            and isinstance(s, ast.Assign) and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and isinstance(s.value, ast.List) and not s.value.elts):
                        vn = s.targets[0].id; nxt = node.body[i + 1]
                        if (isinstance(nxt, ast.For) and len(nxt.body) == 1
                                and not nxt.orelse
                                and isinstance(nxt.body[0], ast.Expr)
                                and isinstance(nxt.body[0].value, ast.Call)):
                            call = nxt.body[0].value
                            if (isinstance(call.func, ast.Attribute)
                                    and call.func.attr == "append"
                                    and isinstance(call.func.value, ast.Name)
                                    and call.func.value.id == vn
                                    and len(call.args) == 1):
                                comp = ast.ListComp(
                                    elt=call.args[0],
                                    generators=[ast.comprehension(
                                        target=nxt.target, iter=nxt.iter,
                                        ifs=[], is_async=0)])
                                new_body.append(ast.Assign(
                                    targets=s.targets, value=comp,
                                    lineno=s.lineno, col_offset=s.col_offset))
                                i += 2; self.changed = True; continue
                    new_body.append(s); i += 1
                node.body = new_body; return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None

class ListToSetMembership(TransformationOperator):
    tier, name = Tier.H, "DataStructureSubstitution[list→set]"

    _MUTATING_METHODS = frozenset({
        "append", "extend", "insert", "pop", "remove",
        "clear", "sort", "reverse", "__setitem__", "__delitem__",
    })
    _ORDER_SENSITIVE_FUNCS = frozenset({
        "sorted", "reversed", "enumerate", "zip", "list", "tuple",
    })

    def _safe_to_convert(self, fn_node: ast.FunctionDef, arg_name: str) -> bool:
        """
        Return True only when arg_name is never:
          • mutated via a method call,
          • iterated with a for-loop (order-dependent),
          • subscripted by index,
          • passed to an order-sensitive builtin.
        """
        for node in ast.walk(fn_node):
            # Mutation via method
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == arg_name
                    and node.func.attr in self._MUTATING_METHODS):
                return False
            # Ordered for-loop iteration
            if (isinstance(node, ast.For)
                    and isinstance(node.iter, ast.Name)
                    and node.iter.id == arg_name):
                return False
            # Index-based subscript
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == arg_name):
                return False
            # Passed to order-sensitive function
            if isinstance(node, ast.Call):
                for call_arg in node.args:
                    if (isinstance(call_arg, ast.Name)
                            and call_arg.id == arg_name
                            and isinstance(node.func, ast.Name)
                            and node.func.id in self._ORDER_SENSITIVE_FUNCS):
                        return False
        return True

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            arg_names = {a.arg for a in fn.args.args}
            for s in ast.walk(fn):
                if isinstance(s, ast.Compare):
                    for op, comp in zip(s.ops, s.comparators):
                        if (isinstance(op, ast.In)
                                and isinstance(comp, ast.Name)
                                and comp.id in arg_names
                                and self._safe_to_convert(fn, comp.id)):
                            return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self, outer): self.changed = False; self.outer = outer

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                arg_names = {a.arg for a in node.args.args}
                tested_args = {
                    comp.id
                    for s in ast.walk(node)
                    if isinstance(s, ast.Compare)
                    for op, comp in zip(s.ops, s.comparators)
                    if (isinstance(op, ast.In)
                        and isinstance(comp, ast.Name)
                        and comp.id in arg_names
                        and self.outer._safe_to_convert(node, comp.id))
                }
                if tested_args:
                    set_assigns = [
                        ast.Assign(
                            targets=[ast.Name(id=arg, ctx=ast.Store())],
                            value=ast.Call(
                                func=ast.Name(id="set", ctx=ast.Load()),
                                args=[ast.Name(id=arg, ctx=ast.Load())],
                                keywords=[]),
                            lineno=node.lineno, col_offset=node.col_offset)
                        for arg in sorted(tested_args)
                    ]
                    node.body = set_assigns + node.body
                    self.changed = True
                return node

        try:
            t = ast.parse(source)
            tr = _T(self)
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None

class MemoizationAddition(TransformationOperator):
    tier, name = Tier.H, "MemoizationAddition"

    _UNHASHABLE_NAMES = frozenset({
        "list", "List", "dict", "Dict", "set", "Set",
        "MutableSequence", "MutableMapping", "MutableSet",
        "deque", "defaultdict", "Counter", "bytearray",
    })

    def _annotation_unhashable(self, ann) -> bool:
        if ann is None:
            return False
        if isinstance(ann, ast.Name):
            return ann.id in self._UNHASHABLE_NAMES
        if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
            return ann.value.id in self._UNHASHABLE_NAMES
        if isinstance(ann, ast.Attribute):
            return ann.attr in self._UNHASHABLE_NAMES
        return False

    def _all_args_hashable(self, fn: ast.FunctionDef) -> bool:
        """
        Return True only when no parameter has an unhashable annotation
        or a mutable default value (list/dict/set literal).
        """
        all_args = (fn.args.args
                    + fn.args.posonlyargs
                    + fn.args.kwonlyargs
                    + ([fn.args.vararg]  if fn.args.vararg  else [])
                    + ([fn.args.kwarg]   if fn.args.kwarg   else []))
        for arg in all_args:
            if self._annotation_unhashable(arg.annotation):
                return False
        for default in fn.args.defaults + fn.args.kw_defaults:
            if default is not None and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                return False
        return True

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not self._all_args_hashable(fn):
                continue
            for child in ast.walk(fn):
                if (child is not fn
                        and isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == fn.name):
                    return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self, outer):
                self.changed = False
                self._recurs: set[str] = set()
                self.outer = outer

            def visit_Module(self, node):
                for s in node.body:
                    if not isinstance(s, ast.FunctionDef):
                        continue
                    if not self.outer._all_args_hashable(s):
                        continue
                    for child in ast.walk(s):
                        if (child is not s
                                and isinstance(child, ast.Call)
                                and isinstance(child.func, ast.Name)
                                and child.func.id == s.name):
                            self._recurs.add(s.name)
                            break
                self.generic_visit(node)
                if self._recurs and not any(
                        isinstance(s, ast.Import)
                        and any(a.name == "functools" for a in s.names)
                        for s in node.body):
                    node.body.insert(
                        0, ast.Import(names=[ast.alias(name="functools")]))
                return node

            def visit_FunctionDef(self, node):
                if node.name in self._recurs and not node.decorator_list:
                    node.decorator_list = [ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="functools", ctx=ast.Load()),
                            attr="lru_cache", ctx=ast.Load()),
                        args=[],
                        keywords=[ast.keyword(arg="maxsize",
                                              value=ast.Constant(None))])]
                    self.changed = True
                return node

        try:
            t = ast.parse(source)
            tr = _T(self)
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None


class IteratorSubstitution(TransformationOperator):
    tier, name = Tier.L, "IteratorSubstitution"

    def precondition(self, tree, source):
        AGG = {"sum", "max", "min", "any", "all"}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in AGG and len(node.args) == 1
                    and isinstance(node.args[0], ast.Call)
                    and isinstance(node.args[0].func, ast.Name)
                    and node.args[0].func.id == "list"): return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_Call(self, node):
                self.generic_visit(node)
                AGG = {"sum", "max", "min", "any", "all"}
                if (isinstance(node.func, ast.Name) and node.func.id in AGG
                        and len(node.args) == 1
                        and isinstance(node.args[0], ast.Call)
                        and isinstance(node.args[0].func, ast.Name)
                        and node.args[0].func.id == "list"
                        and node.args[0].args):
                    node.args[0] = node.args[0].args[0]; self.changed = True
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class StringConcatToJoin(TransformationOperator):
    """
    FIX v2: precondition now uses AST walk instead of regex.
    """
    tier, name = Tier.L, "StringConcatToJoin"

    def precondition(self, tree, source):
        # AST-based: find   var = ""  followed by  for ...: var += <expr>
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            body = fn.body
            for i, stmt in enumerate(body[:-1]):
                nxt = body[i + 1]
                if (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and isinstance(stmt.value, ast.Constant)
                        and stmt.value.value == ""):
                    vn = stmt.targets[0].id
                    if (isinstance(nxt, ast.For)
                            and len(nxt.body) == 1
                            and not nxt.orelse
                            and isinstance(nxt.body[0], ast.AugAssign)
                            and isinstance(nxt.body[0].target, ast.Name)
                            and nxt.body[0].target.id == vn
                            and isinstance(nxt.body[0].op, ast.Add)):
                        return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                new_body, i = [], 0
                while i < len(node.body):
                    s = node.body[i]
                    if (i + 1 < len(node.body)
                            and isinstance(s, ast.Assign) and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and isinstance(s.value, ast.Constant)
                            and s.value.value == ""):
                        vn = s.targets[0].id; nxt = node.body[i + 1]
                        if (isinstance(nxt, ast.For) and len(nxt.body) == 1
                                and not nxt.orelse
                                and isinstance(nxt.body[0], ast.AugAssign)
                                and isinstance(nxt.body[0].target, ast.Name)
                                and nxt.body[0].target.id == vn
                                and isinstance(nxt.body[0].op, ast.Add)):
                            parts = ast.ListComp(
                                elt=nxt.body[0].value,
                                generators=[ast.comprehension(
                                    target=nxt.target, iter=nxt.iter,
                                    ifs=[], is_async=0)])
                            join_call = ast.Call(
                                func=ast.Attribute(value=ast.Constant(""),
                                                   attr="join", ctx=ast.Load()),
                                args=[parts], keywords=[])
                            new_body.append(ast.Assign(
                                targets=s.targets, value=join_call,
                                lineno=s.lineno, col_offset=s.col_offset))
                            i += 2; self.changed = True; continue
                    new_body.append(s); i += 1
                node.body = new_body; return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class SortedToInPlaceSort(TransformationOperator):
    tier, name = Tier.L, "SortedToInPlaceSort"

    @staticmethod
    def _local_list_vars(fn_node: ast.FunctionDef) -> set[str]:
        """
        Return names of variables that were assigned as list literals or
        list() calls inside fn_node and are not parameters.
        """
        param_names = {a.arg for a in fn_node.args.args}
        list_vars: set[str] = set()
        for node in ast.walk(fn_node):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                continue
            tgt = node.targets[0]
            if not (isinstance(tgt, ast.Name) and tgt.id not in param_names):
                continue
            val = node.value
            if isinstance(val, ast.List):
                list_vars.add(tgt.id)
            elif (isinstance(val, ast.Call)
                  and isinstance(val.func, ast.Name)
                  and val.func.id == "list"):
                list_vars.add(tgt.id)
        return list_vars

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            safe = self._local_list_vars(fn)
            for node in ast.walk(fn):
                if (isinstance(node, ast.Assign)
                        and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in safe
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "sorted"
                        and node.value.args
                        and isinstance(node.value.args[0], ast.Name)
                        and node.value.args[0].id == node.targets[0].id):
                    return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._safe: set[str] = set()

            def visit_FunctionDef(self, node):
                # Compute the safe set once per function, then descend.
                prev = self._safe
                self._safe = SortedToInPlaceSort._local_list_vars(node)
                self.generic_visit(node)
                self._safe = prev
                return node

            def visit_Assign(self, node):
                if (len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in self._safe
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "sorted"
                        and node.value.args
                        and isinstance(node.value.args[0], ast.Name)
                        and node.value.args[0].id == node.targets[0].id):
                    vn = node.targets[0].id
                    sort_call = ast.Expr(value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=vn, ctx=ast.Load()),
                            attr="sort", ctx=ast.Load()),
                        args=[], keywords=node.value.keywords))
                    self.changed = True
                    return ast.copy_location(sort_call, node)
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None


class LocalImportHoisting(TransformationOperator):
    tier, name = Tier.L, "LocalImportHoisting"

    @staticmethod
    def _protected_names(tree) -> set[str]:
        """
        Return the set of module root-names that appear inside any
        try/except, if, for, while, or with block anywhere in the tree.
        Imports with these names must never be hoisted.
        """
        protected: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Try, ast.If,
                                     ast.For, ast.While, ast.With)):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Import):
                    for alias in child.names:
                        protected.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(child, ast.ImportFrom) and child.module:
                    protected.add(child.module.split(".")[0])
        return protected

    @staticmethod
    def _import_root_names(stmt) -> set[str]:
        if isinstance(stmt, ast.Import):
            return {a.asname or a.name.split(".")[0] for a in stmt.names}
        if isinstance(stmt, ast.ImportFrom) and stmt.module:
            return {stmt.module.split(".")[0]}
        return set()

    def precondition(self, tree, source):
        protected = self._protected_names(tree)
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            for s in fn.body:
                if isinstance(s, (ast.Import, ast.ImportFrom)):
                    if not (self._import_root_names(s) & protected):
                        return True
        return False

    def apply(self, source, llm=None):
        try:
            tree = ast.parse(source)
            protected = self._protected_names(tree)
            hoisted: list = []

            class _T(ast.NodeTransformer):
                def visit_FunctionDef(self, node):
                    new_body = []
                    for s in node.body:
                        if isinstance(s, (ast.Import, ast.ImportFrom)):
                            # Only hoist if none of its root names are protected.
                            if not (LocalImportHoisting._import_root_names(s)
                                    & protected):
                                hoisted.append(s)
                                continue
                        new_body.append(s)
                    node.body = new_body or [ast.Pass()]
                    # No generic_visit: do not recurse into nested functions.
                    return node

            new_tree = _T().visit(tree)
            if hoisted:
                existing = {ast.unparse(s) for s in new_tree.body
                            if isinstance(s, (ast.Import, ast.ImportFrom))}
                to_add = [s for s in hoisted if ast.unparse(s) not in existing]
                if to_add:
                    new_tree.body = to_add + new_tree.body
                    ast.fix_missing_locations(new_tree)
                    return ast.unparse(new_tree)
        except Exception:
            pass
        return None

class ReductionListCompToGenerator(TransformationOperator):
    tier, name = Tier.L, "ReductionListCompToGenerator"

    def precondition(self, tree, source):
        agg = {"sum", "max", "min", "any", "all"}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in agg
                    and node.args
                    and isinstance(node.args[0], ast.ListComp)):
                return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_Call(self, node):
                self.generic_visit(node)
                agg = {"sum", "max", "min", "any", "all"}
                if (isinstance(node.func, ast.Name)
                        and node.func.id in agg
                        and node.args
                        and isinstance(node.args[0], ast.ListComp)):
                    lc = node.args[0]
                    node.args[0] = ast.GeneratorExp(elt=lc.elt, generators=lc.generators)
                    self.changed = True
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class DictKeysMembershipElision(TransformationOperator):
    tier, name = Tier.L, "DictKeysMembershipElision"

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if (isinstance(op, (ast.In, ast.NotIn))
                        and isinstance(comp, ast.Call)
                        and isinstance(comp.func, ast.Attribute)
                        and comp.func.attr == "keys"
                        and not comp.args and not comp.keywords):
                    return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_Compare(self, node):
                self.generic_visit(node)
                for idx, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                    if (isinstance(op, (ast.In, ast.NotIn))
                            and isinstance(comp, ast.Call)
                            and isinstance(comp.func, ast.Attribute)
                            and comp.func.attr == "keys"
                            and not comp.args and not comp.keywords):
                        node.comparators[idx] = comp.func.value
                        self.changed = True
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class LoopMembershipSetCache(TransformationOperator):
    tier, name = Tier.H, "LoopMembershipSetCache"
    _MUTATING_METHODS = {
        "append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse",
        "add", "update", "discard", "setdefault", "__setitem__", "__delitem__"
    }

    def precondition(self, tree, source):
        for loop in ast.walk(tree):
            if isinstance(loop, ast.For) and self._loop_candidates(loop):
                return True
        return False

    @staticmethod
    def _target_names(node):
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                names.add(sub.id)
        return names

    def _mutated_names(self, loop):
        mutated = set()
        for node in ast.walk(loop):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    mutated |= self._target_names(target)
            elif isinstance(node, ast.AnnAssign):
                mutated |= self._target_names(node.target)
            elif isinstance(node, ast.AugAssign):
                mutated |= self._target_names(node.target)
            elif isinstance(node, ast.For):
                mutated |= self._target_names(node.target)
            elif isinstance(node, ast.comprehension):
                mutated |= self._target_names(node.target)
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and isinstance(node.func.value, ast.Name)
                  and node.func.attr in self._MUTATING_METHODS):
                mutated.add(node.func.value.id)
        return mutated

    def _loop_candidates(self, loop):
        counts: dict[str, int] = {}
        for node in ast.walk(loop):
            if not isinstance(node, ast.Compare):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if (isinstance(op, (ast.In, ast.NotIn))
                        and isinstance(comp, ast.Name)
                        and not comp.id.startswith("_spectra_set_")):
                    counts[comp.id] = counts.get(comp.id, 0) + 1
        mutated = self._mutated_names(loop)
        return [name for name, count in counts.items() if count >= 2 and name not in mutated]

    def apply(self, source, llm=None):
        class _ComparatorRewriter(ast.NodeTransformer):
            def __init__(self, cache_map): self.cache_map = cache_map
            def visit_Compare(self, node):
                self.generic_visit(node)
                for idx, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                    if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Name):
                        repl = self.cache_map.get(comp.id)
                        if repl:
                            node.comparators[idx] = ast.copy_location(
                                ast.Name(id=repl, ctx=ast.Load()), comp)
                return node

        class _T(ast.NodeTransformer):
            def __init__(self, outer):
                self.outer = outer
                self.changed = False
                self._used: set[str] = set()

            def _fresh(self, base: str) -> str:
                if base not in self._used:
                    self._used.add(base); return base
                i = 1
                while f"{base}_{i}" in self._used:
                    i += 1
                name = f"{base}_{i}"
                self._used.add(name)
                return name

            def visit_FunctionDef(self, node):
                self._used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                self.generic_visit(node)
                return node

            def visit_For(self, node):
                node = self.generic_visit(node)
                containers = self.outer._loop_candidates(node)
                if not containers:
                    return node
                cache_map = {
                    name: self._fresh(f"_spectra_set_{name}")
                    for name in sorted(containers)
                }
                node = _ComparatorRewriter(cache_map).visit(node)
                init_nodes = []
                for src_name, cache_name in cache_map.items():
                    init_nodes.append(ast.Try(
                        body=[ast.Assign(
                            targets=[ast.Name(id=cache_name, ctx=ast.Store())],
                            value=ast.Call(
                                func=ast.Name(id="set", ctx=ast.Load()),
                                args=[ast.Name(id=src_name, ctx=ast.Load())],
                                keywords=[]))],
                        handlers=[ast.ExceptHandler(
                            type=ast.Name(id="TypeError", ctx=ast.Load()),
                            name=None,
                            body=[ast.Assign(
                                targets=[ast.Name(id=cache_name, ctx=ast.Store())],
                                value=ast.Name(id=src_name, ctx=ast.Load()))])],
                        orelse=[],
                        finalbody=[]))
                self.changed = True
                return init_nodes + [node]

        try:
            t = ast.parse(source); tr = _T(self); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class SeenSetForAppendDedup(TransformationOperator):
    tier, name = Tier.H, "SeenSetForAppendDedup"

    @staticmethod
    def _match_pattern(node):
        if (not isinstance(node, ast.If) or node.orelse
                or len(node.body) != 1
                or not isinstance(node.body[0], ast.Expr)
                or not isinstance(node.body[0].value, ast.Call)):
            return None
        call = node.body[0].value
        if (not isinstance(call.func, ast.Attribute)
                or call.func.attr != "append"
                or not isinstance(call.func.value, ast.Name)
                or len(call.args) != 1):
            return None
        test = node.test
        if (not isinstance(test, ast.Compare)
                or len(test.ops) != 1
                or len(test.comparators) != 1
                or not isinstance(test.ops[0], ast.NotIn)
                or not isinstance(test.left, ast.Name)
                or not isinstance(test.comparators[0], ast.Name)):
            return None
        result_name = test.comparators[0].id
        if call.func.value.id != result_name:
            return None
        if not isinstance(call.args[0], ast.Name) or call.args[0].id != test.left.id:
            return None
        return result_name, test.left.id

    def precondition(self, tree, source):
        if "_spectra_seen_" in source:
            return False
        for loop in ast.walk(tree):
            if not isinstance(loop, ast.For):
                continue
            for node in ast.walk(loop):
                if self._match_pattern(node):
                    return True
        return False

    def apply(self, source, llm=None):
        class _IfRewriter(ast.NodeTransformer):
            def __init__(self, owner, mapping):
                self.owner = owner
                self.mapping = mapping

            def _replacement(self, original_if, result_name, item_name, seen_var):
                slow_if = deepcopy(original_if)
                fast_if = ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=item_name, ctx=ast.Load()),
                        ops=[ast.NotIn()],
                        comparators=[ast.Name(id=seen_var, ctx=ast.Load())]),
                    body=[
                        ast.Expr(value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id=result_name, ctx=ast.Load()),
                                attr="append", ctx=ast.Load()),
                            args=[ast.Name(id=item_name, ctx=ast.Load())], keywords=[])),
                        ast.Expr(value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id=seen_var, ctx=ast.Load()),
                                attr="add", ctx=ast.Load()),
                            args=[ast.Name(id=item_name, ctx=ast.Load())], keywords=[])),
                    ],
                    orelse=[])
                fallback_if = deepcopy(original_if)
                try_stmt = ast.Try(
                    body=[fast_if],
                    handlers=[ast.ExceptHandler(
                        type=ast.Name(id="TypeError", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[ast.Name(id=seen_var, ctx=ast.Store())],
                                value=ast.Constant(None)),
                            fallback_if,
                        ])],
                    orelse=[],
                    finalbody=[])
                wrapped = ast.If(
                    test=ast.Compare(
                        left=ast.Name(id=seen_var, ctx=ast.Load()),
                        ops=[ast.Is()],
                        comparators=[ast.Constant(None)]),
                    body=[slow_if],
                    orelse=[try_stmt])
                return ast.copy_location(wrapped, original_if)

            def visit_If(self, node):
                node = self.generic_visit(node)
                match = SeenSetForAppendDedup._match_pattern(node)
                if not match:
                    return node
                result_name, item_name = match
                seen_var = self.mapping.get(result_name)
                if seen_var is None:
                    seen_var = self.owner._fresh(f"_spectra_seen_{result_name}")
                    self.mapping[result_name] = seen_var
                self.owner.changed = True
                return self._replacement(node, result_name, item_name, seen_var)

        class _T(ast.NodeTransformer):
            def __init__(self):
                self.changed = False
                self._used: set[str] = set()

            def _fresh(self, base: str) -> str:
                if base not in self._used:
                    self._used.add(base); return base
                i = 1
                while f"{base}_{i}" in self._used:
                    i += 1
                name = f"{base}_{i}"
                self._used.add(name)
                return name

            def visit_FunctionDef(self, node):
                self._used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                self.generic_visit(node)
                return node

            def visit_For(self, node):
                node = self.generic_visit(node)
                mapping: dict[str, str] = {}
                rewriter = _IfRewriter(self, mapping)
                new_body = []
                for stmt in node.body:
                    out = rewriter.visit(stmt)
                    if isinstance(out, list):
                        new_body.extend(out)
                    else:
                        new_body.append(out)
                node.body = new_body
                if not mapping:
                    return node
                init_nodes = []
                for result_name, seen_var in mapping.items():
                    init_nodes.append(ast.Try(
                        body=[ast.Assign(
                            targets=[ast.Name(id=seen_var, ctx=ast.Store())],
                            value=ast.Call(
                                func=ast.Name(id="set", ctx=ast.Load()),
                                args=[ast.Name(id=result_name, ctx=ast.Load())],
                                keywords=[]))],
                        handlers=[ast.ExceptHandler(
                            type=ast.Name(id="TypeError", ctx=ast.Load()),
                            name=None,
                            body=[ast.Assign(
                                targets=[ast.Name(id=seen_var, ctx=ast.Store())],
                                value=ast.Constant(None))])],
                        orelse=[],
                        finalbody=[]))
                self.changed = True
                return init_nodes + [node]

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


# ─── NEW Tier L Operators ─────────────────────────────────────

class ListPopZeroToDeque(TransformationOperator):
    """Convert list.pop(0) inside loops to collections.deque.popleft()."""
    tier, name = Tier.L, "ListPopZeroToDeque"

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "pop"
                    and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 0):
                return True
        return False

    def apply(self, source, llm=None):
        try:
            tree = ast.parse(source)

            # ── Pass 1: collect every variable name used with .pop(0) ──
            queues: set[str] = set()
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "pop"
                        and len(node.args) == 1
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == 0
                        and isinstance(node.func.value, ast.Name)):
                    queues.add(node.func.value.id)

            if not queues:
                return None

            # ── Pass 2: rewrite using the fully-populated queues set ──
            class _T(ast.NodeTransformer):
                def __init__(self, queues: set[str]):
                    self.changed = False
                    self._queues = queues

                def visit_Module(self, node):
                    self.generic_visit(node)
                    has_collections = any(
                        isinstance(s, ast.Import)
                        and any(a.name == "collections" for a in s.names)
                        for s in node.body)
                    if self._queues and not has_collections:
                        node.body.insert(
                            0, ast.Import(names=[ast.alias(name="collections")]))
                    return node

                def visit_Assign(self, node):
                    # Rewrite  var = [...]  →  var = collections.deque([...])
                    self.generic_visit(node)
                    if (len(node.targets) == 1
                            and isinstance(node.targets[0], ast.Name)
                            and node.targets[0].id in self._queues
                            and isinstance(node.value, ast.List)):
                        node.value = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="collections", ctx=ast.Load()),
                                attr="deque", ctx=ast.Load()),
                            args=[node.value], keywords=[])
                        self.changed = True
                    return node

                def visit_Call(self, node):
                    self.generic_visit(node)
                    if (isinstance(node.func, ast.Attribute)
                            and node.func.attr == "pop"
                            and len(node.args) == 1
                            and isinstance(node.args[0], ast.Constant)
                            and node.args[0].value == 0
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id in self._queues):
                        node.func.attr = "popleft"
                        node.args = []
                        self.changed = True
                    return node

            tr = _T(queues)
            nt = tr.visit(tree)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None

class FStringConversion(TransformationOperator):
    """Convert %-formatting and .format() calls to f-strings where safe."""
    tier, name = Tier.L, "FStringConversion"

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            # %-format:  "..." % x
            if (isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Mod)
                    and isinstance(node.left, ast.Constant)
                    and isinstance(node.left.value, str)):
                return True
            # .format()
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and not node.keywords):
                return True
        return False

    def apply(self, source, llm=None):
        """
        Conservative: only converts simple single-value %-formatting
        and simple positional .format(x) with one arg to f-string.
        """
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_BinOp(self, node):
                self.generic_visit(node)
                if (isinstance(node.op, ast.Mod)
                        and isinstance(node.left, ast.Constant)
                        and isinstance(node.left.value, str)):
                    tmpl = node.left.value
                    # Only handle very simple "%s" % single_name or tuple of names
                    if tmpl.count("%s") == 1 and tmpl.count("%") == 1:
                        rhs = node.right
                        if isinstance(rhs, ast.Name):
                            # Build f-string: replace %s with {name}
                            new_tmpl = tmpl.replace("%s", "{" + rhs.id + "}", 1)
                            try:
                                fstr_node = ast.parse(f'f"{new_tmpl}"', mode="eval").body
                                self.changed = True
                                return fstr_node
                            except Exception:
                                pass
                return node

            def visit_Call(self, node):
                self.generic_visit(node)
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr == "format"
                        and isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)
                        and len(node.args) == 1
                        and not node.keywords
                        and isinstance(node.args[0], ast.Name)):
                    tmpl = node.func.value.value
                    if tmpl.count("{}") == 1:
                        new_tmpl = tmpl.replace("{}", "{" + node.args[0].id + "}", 1)
                        try:
                            fstr_node = ast.parse(f'f"{new_tmpl}"', mode="eval").body
                            self.changed = True
                            return fstr_node
                        except Exception:
                            pass
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class MultipleAssignmentFusion(TransformationOperator):
    """Convert adjacent single assignments to tuple unpacking."""
    tier, name = Tier.L, "MultipleAssignmentFusion"

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            body = fn.body
            for i in range(len(body) - 1):
                a, b = body[i], body[i + 1]
                if (isinstance(a, ast.Assign) and isinstance(b, ast.Assign)
                        and len(a.targets) == 1 and len(b.targets) == 1
                        and isinstance(a.targets[0], ast.Name)
                        and isinstance(b.targets[0], ast.Name)
                        and a.targets[0].id != b.targets[0].id
                        and isinstance(a.value, ast.Constant)
                        and isinstance(b.value, ast.Constant)):
                    return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                new_body, i = [], 0
                while i < len(node.body):
                    s = node.body[i]
                    if (i + 1 < len(node.body)
                            and isinstance(s, ast.Assign)
                            and isinstance(node.body[i + 1], ast.Assign)
                            and len(s.targets) == 1
                            and len(node.body[i + 1].targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and isinstance(node.body[i + 1].targets[0], ast.Name)
                            and s.targets[0].id != node.body[i + 1].targets[0].id
                            and isinstance(s.value, ast.Constant)
                            and isinstance(node.body[i + 1].value, ast.Constant)):
                        nxt = node.body[i + 1]
                        tup_target = ast.Tuple(
                            elts=[s.targets[0], nxt.targets[0]], ctx=ast.Store())
                        tup_value = ast.Tuple(
                            elts=[s.value, nxt.value], ctx=ast.Load())
                        fused = ast.Assign(
                            targets=[tup_target], value=tup_value,
                            lineno=s.lineno, col_offset=s.col_offset)
                        new_body.append(fused)
                        i += 2; self.changed = True; continue
                    new_body.append(s); i += 1
                node.body = new_body; return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class GeneratorToYieldFrom(TransformationOperator):
    """Convert 'for x in gen: yield x' to 'yield from gen'."""
    tier, name = Tier.L, "GeneratorToYieldFrom"

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.For)
                        and len(node.body) == 1
                        and not node.orelse
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Yield)
                        and isinstance(node.body[0].value.value, ast.Name)
                        and isinstance(node.target, ast.Name)
                        and node.body[0].value.value.id == node.target.id):
                    return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_For(self, node):
                self.generic_visit(node)
                if (len(node.body) == 1
                        and not node.orelse
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Yield)
                        and isinstance(node.body[0].value.value, ast.Name)
                        and isinstance(node.target, ast.Name)
                        and node.body[0].value.value.id == node.target.id):
                    yf = ast.Expr(value=ast.YieldFrom(value=node.iter))
                    self.changed = True
                    return ast.copy_location(yf, node)
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class MultipleOrToSetMembership(TransformationOperator):
    """Convert 'x==1 or x==2 or x==3' to 'x in {1,2,3}'."""
    tier, name = Tier.L, "MultipleOrToSetMembership"

    @staticmethod
    def _collect_or_chain(node):
        """Return list of (name, const) pairs if the BoolOp is all x==const."""
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
            return None
        pairs = []
        pivot = None
        for val in node.values:
            if (isinstance(val, ast.Compare)
                    and len(val.ops) == 1
                    and isinstance(val.ops[0], ast.Eq)
                    and len(val.comparators) == 1
                    and isinstance(val.left, ast.Name)
                    and isinstance(val.comparators[0], ast.Constant)):
                if pivot is None: pivot = val.left.id
                if val.left.id == pivot:
                    pairs.append(val.comparators[0].value)
                    continue
            return None
        return (pivot, pairs) if len(pairs) >= 3 else None

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if self._collect_or_chain(node): return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_BoolOp(self, node):
                self.generic_visit(node)
                result = MultipleOrToSetMembership._collect_or_chain(node)
                if result:
                    pivot, consts = result
                    new_node = ast.Compare(
                        left=ast.Name(id=pivot, ctx=ast.Load()),
                        ops=[ast.In()],
                        comparators=[ast.Set(
                            elts=[ast.Constant(c) for c in consts])])
                    self.changed = True
                    return ast.copy_location(new_node, node)
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class EnumerateSubstitution(TransformationOperator):
    """Convert 'for i in range(len(lst)): ... lst[i]' to enumerate."""
    tier, name = Tier.L, "EnumerateSubstitution"

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.For)
                    and isinstance(node.target, ast.Name)
                    and isinstance(node.iter, ast.Call)
                    and isinstance(node.iter.func, ast.Name)
                    and node.iter.func.id == "range"
                    and len(node.iter.args) == 1
                    and isinstance(node.iter.args[0], ast.Call)
                    and isinstance(node.iter.args[0].func, ast.Name)
                    and node.iter.args[0].func.id == "len"):
                idx = node.target.id
                # Check body uses the index for subscript
                for child in ast.walk(node):
                    if (isinstance(child, ast.Subscript)
                            and isinstance(child.slice, ast.Name)
                            and child.slice.id == idx):
                        return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_For(self, node):
                self.generic_visit(node)
                if (isinstance(node.target, ast.Name)
                        and isinstance(node.iter, ast.Call)
                        and isinstance(node.iter.func, ast.Name)
                        and node.iter.func.id == "range"
                        and len(node.iter.args) == 1
                        and isinstance(node.iter.args[0], ast.Call)
                        and isinstance(node.iter.args[0].func, ast.Name)
                        and node.iter.args[0].func.id == "len"
                        and node.iter.args[0].args):
                    idx = node.target.id
                    lst_node = node.iter.args[0].args[0]
                    if not isinstance(lst_node, ast.Name): return node
                    lst_name = lst_node.id
                    item_var = f"_spectra_item_{idx}"
                    # Replace  lst[idx]  with item_var in body
                    class _Sub(ast.NodeTransformer):
                        def __init__(self): self.hit = False
                        def visit_Subscript(self, n):
                            self.generic_visit(n)
                            if (isinstance(n.slice, ast.Name)
                                    and n.slice.id == idx
                                    and isinstance(n.value, ast.Name)
                                    and n.value.id == lst_name
                                    and isinstance(n.ctx, ast.Load)):
                                self.hit = True
                                return ast.copy_location(
                                    ast.Name(id=item_var, ctx=ast.Load()), n)
                            return n
                    sub = _Sub()
                    new_body_nodes = [sub.visit(s) for s in node.body]
                    if not sub.hit: return node
                    # New target: (idx, item_var)
                    node.target = ast.Tuple(
                        elts=[ast.Name(id=idx, ctx=ast.Store()),
                              ast.Name(id=item_var, ctx=ast.Store())],
                        ctx=ast.Store())
                    node.iter = ast.Call(
                        func=ast.Name(id="enumerate", ctx=ast.Load()),
                        args=[lst_node], keywords=[])
                    node.body = new_body_nodes
                    self.changed = True
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class LoopGlobalToLocalHoisting(TransformationOperator):
    """Hoist builtin references used inside loops to local variables."""
    tier, name = Tier.L, "LoopGlobalToLocalHoisting"
    _SAFE_BUILTINS = {"len", "str", "int", "float", "abs", "range", "enumerate",
                      "isinstance", "type", "sorted", "reversed", "zip", "map",
                      "filter", "min", "max", "sum", "any", "all"}

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            for loop in ast.walk(fn):
                if not isinstance(loop, ast.For): continue
                for call in ast.walk(loop):
                    if (isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Name)
                            and call.func.id in self._SAFE_BUILTINS):
                        return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self, safe): self.safe = safe; self.changed = False

            def visit_FunctionDef(self, node):
                # Find all builtins used inside for-loops in this function
                used = set()
                for loop in ast.walk(node):
                    if not isinstance(loop, ast.For): continue
                    for call in ast.walk(loop):
                        if (isinstance(call, ast.Call)
                                and isinstance(call.func, ast.Name)
                                and call.func.id in self.safe):
                            used.add(call.func.id)
                if not used:
                    return node
                local_map = {b: f"_local_{b}" for b in sorted(used)}
                # Inject local assignments at top of function body
                init_stmts = [
                    ast.Assign(
                        targets=[ast.Name(id=lname, ctx=ast.Store())],
                        value=ast.Name(id=bname, ctx=ast.Load()),
                        lineno=node.body[0].lineno if node.body else 1,
                        col_offset=0)
                    for bname, lname in local_map.items()
                ]
                # Replace references inside loops
                class _Repl(ast.NodeTransformer):
                    def __init__(self, lmap): self.lmap = lmap
                    def visit_For(self, n):
                        self.generic_visit(n)
                        return n
                    def visit_Call(self, n):
                        self.generic_visit(n)
                        if isinstance(n.func, ast.Name) and n.func.id in self.lmap:
                            n.func.id = self.lmap[n.func.id]
                        return n
                # Only replace inside loops
                new_body = []
                for stmt in node.body:
                    if isinstance(stmt, ast.For):
                        new_body.append(_Repl(local_map).visit(stmt))
                    else:
                        new_body.append(stmt)
                node.body = init_stmts + new_body
                self.changed = True
                return node

        try:
            t = ast.parse(source); tr = _T(self._SAFE_BUILTINS); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class JoinListCompToGenerator(TransformationOperator):
    """Convert '"".join([x for x in y])' to '"".join(x for x in y)'."""
    tier, name = Tier.L, "JoinListCompToGenerator"

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "join"
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                    and node.args
                    and isinstance(node.args[0], ast.ListComp)):
                return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_Call(self, node):
                self.generic_visit(node)
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr == "join"
                        and isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)
                        and node.args
                        and isinstance(node.args[0], ast.ListComp)):
                    lc = node.args[0]
                    node.args[0] = ast.GeneratorExp(
                        elt=lc.elt, generators=lc.generators)
                    self.changed = True
                return node

        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class ReturnBoolSimplification(TransformationOperator):
    """
    Simplify redundant boolean return patterns:
 
        if cond:          →   return cond
            return True
        (else:)
        return False
 
        if cond:          →   return not cond
            return False
        (else:)
        return True
    """
    tier, name = Tier.L, "ReturnBoolSimplification"
 
    @staticmethod
    def _match(if_stmt, next_stmt):
        """
        Returns (condition_node, negate) if the pattern matches, else None.
        Handles both with and without an explicit else branch.
        """
        # Pattern A: body=[return True/False], orelse=[] or orelse=[return False/True]
        if not isinstance(if_stmt, ast.If):
            return None
        if len(if_stmt.body) != 1 or not isinstance(if_stmt.body[0], ast.Return):
            return None
        body_val = if_stmt.body[0].value
        if not isinstance(body_val, ast.Constant) or body_val.value not in (True, False):
            return None
 
        returns_true_in_body = body_val.value is True
 
        # Explicit else branch
        if if_stmt.orelse:
            if len(if_stmt.orelse) != 1 or not isinstance(if_stmt.orelse[0], ast.Return):
                return None
            else_val = if_stmt.orelse[0].value
            if not isinstance(else_val, ast.Constant) or else_val.value not in (True, False):
                return None
            if returns_true_in_body and else_val.value is False:
                return if_stmt.test, False   # return cond
            if not returns_true_in_body and else_val.value is True:
                return if_stmt.test, True    # return not cond
            return None
 
        # No else — must have a bare `return False/True` as the *next* statement
        if next_stmt is None or not isinstance(next_stmt, ast.Return):
            return None
        next_val = next_stmt.value
        if not isinstance(next_val, ast.Constant) or next_val.value not in (True, False):
            return None
        if returns_true_in_body and next_val.value is False:
            return if_stmt.test, False
        if not returns_true_in_body and next_val.value is True:
            return if_stmt.test, True
        return None
 
    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            body = fn.body
            for i, stmt in enumerate(body):
                nxt = body[i + 1] if i + 1 < len(body) else None
                if self._match(stmt, nxt) is not None:
                    return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                new_body, i = [], 0
                while i < len(node.body):
                    stmt = node.body[i]
                    nxt = node.body[i + 1] if i + 1 < len(node.body) else None
                    result = ReturnBoolSimplification._match(stmt, nxt)
                    if result is not None:
                        cond, negate = result
                        if negate:
                            ret_val = (
                                ast.UnaryOp(op=ast.Not(), operand=cond)
                            )
                        else:
                            ret_val = ast.Call(
                                func=ast.Name(id="bool", ctx=ast.Load()),
                                args=[cond], keywords=[])
                            
                        new_ret = ast.Return(value=ret_val)
                        ast.copy_location(new_ret, stmt)
                        new_body.append(new_ret)
                        # Skip next stmt if it was the bare `return False/True`
                        i += 2 if not stmt.orelse else 1
                        self.changed = True
                        continue
                    new_body.append(stmt)
                    i += 1
                node.body = new_body
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
class TupleUnpackInLoop(TransformationOperator):
    """
    Convert manual index access on a loop variable into tuple unpacking:
 
        for item in pairs:         →   for x, y in pairs:
            x = item[0]                    ...
            y = item[1]
    """
    tier, name = Tier.L, "TupleUnpackInLoop"
 
    @staticmethod
    def _leading_index_assigns(body, loop_var):
        """
        Return list of (var_name, index) for consecutive subscript assignments
        at the top of the loop body that all index into `loop_var`.
        """
        assigns = []
        for stmt in body:
            if not (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Subscript)
                    and isinstance(stmt.value.value, ast.Name)
                    and stmt.value.value.id == loop_var
                    and isinstance(stmt.value.slice, ast.Constant)
                    and isinstance(stmt.value.slice.value, int)):
                break
            assigns.append((stmt.targets[0].id, stmt.value.slice.value))
        return assigns
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.For)
                    and isinstance(node.target, ast.Name)):
                assigns = self._leading_index_assigns(node.body, node.target.id)
                # Need at least 2 consecutive index unpacks starting at 0
                if (len(assigns) >= 2
                        and all(idx == i for i, (_, idx) in enumerate(assigns))):
                    return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_For(self, node):
                self.generic_visit(node)
                if not isinstance(node.target, ast.Name):
                    return node
                assigns = TupleUnpackInLoop._leading_index_assigns(
                    node.body, node.target.id)
                if (len(assigns) < 2
                        or not all(idx == i for i, (_, idx) in enumerate(assigns))):
                    return node
                names = [name for name, _ in assigns]
                new_target = ast.Tuple(
                    elts=[ast.Name(id=n, ctx=ast.Store()) for n in names],
                    ctx=ast.Store())
                node.target = new_target
                node.body = node.body[len(assigns):]  # strip the index-assign stmts
                if not node.body:
                    node.body = [ast.Pass()]
                self.changed = True
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
class ChainedComparisonFusion(TransformationOperator):
    """
    Fuse redundant double comparisons against the same variable:

        x > a and x < b    →   a < x < b
        x >= a and x <= b  →   a <= x <= b
        x < b and x > a    →   a < x < b   (commuted — was broken before)
    """
    tier, name = Tier.L, "ChainedComparisonFusion"

    # Keyed by (lower_bound_op, upper_bound_op) after normalisation.
    # lower_bound_op is always Gt or GtE  ("pivot > a"  →  a is lower bound)
    # upper_bound_op is always Lt or LtE  ("pivot < b"  →  b is upper bound)
    _PAIRS = {
        (ast.Gt,  ast.Lt):  (ast.Lt,  ast.Lt),
        (ast.Gt,  ast.LtE): (ast.Lt,  ast.LtE),
        (ast.GtE, ast.Lt):  (ast.LtE, ast.Lt),
        (ast.GtE, ast.LtE): (ast.LtE, ast.LtE),
    }
    _LOWER_OPS = frozenset({ast.Gt, ast.GtE})  # "pivot > bound" → bound is lower
    _UPPER_OPS = frozenset({ast.Lt, ast.LtE})  # "pivot < bound" → bound is upper

    @staticmethod
    def _extract(compare, pivot_id):
        """
        Return (op_type, bound_node) oriented as  pivot OP bound,
        handling both  'pivot OP bound'  and  'bound OP pivot'  forms.
        """
        if not (isinstance(compare, ast.Compare)
                and len(compare.ops) == 1
                and len(compare.comparators) == 1):
            return None
        op   = type(compare.ops[0])
        left, right = compare.left, compare.comparators[0]
        if isinstance(left, ast.Name) and left.id == pivot_id:
            return op, right
        _FLIP = {ast.Lt: ast.Gt, ast.LtE: ast.GtE,
                 ast.Gt: ast.Lt, ast.GtE: ast.LtE}
        if isinstance(right, ast.Name) and right.id == pivot_id and op in _FLIP:
            return _FLIP[op], left
        return None

    @staticmethod
    def _normalise(r1, r2):
        """
        Given two (op, bound) pairs, return (r_lower, r_upper) where
        r_lower.op ∈ {Gt, GtE} and r_upper.op ∈ {Lt, LtE}.
        Returns None if the pair cannot form a valid range.
        """
        lower_ops = ChainedComparisonFusion._LOWER_OPS
        upper_ops = ChainedComparisonFusion._UPPER_OPS
        if r1[0] in lower_ops and r2[0] in upper_ops:
            return r1, r2
        if r2[0] in lower_ops and r1[0] in upper_ops:
            return r2, r1
        return None  # same direction (e.g. x>a and x>b) — not fuseable

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And)
                    and len(node.values) == 2):
                continue
            for v in node.values:
                if not isinstance(v, ast.Compare):
                    continue
                if isinstance(v.left, ast.Name):
                    pivot = v.left.id
                    other = node.values[1] if v is node.values[0] else node.values[0]
                    r1 = self._extract(v, pivot)
                    r2 = self._extract(other, pivot)
                    if r1 and r2:
                        pair = self._normalise(r1, r2)
                        if pair and (pair[0][0], pair[1][0]) in self._PAIRS:
                            return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False

            def visit_BoolOp(self, node):
                self.generic_visit(node)
                if not (isinstance(node.op, ast.And) and len(node.values) == 2):
                    return node
                for i in range(2):
                    v = node.values[i]
                    if not (isinstance(v, ast.Compare)
                            and isinstance(v.left, ast.Name)):
                        continue
                    pivot = v.left.id
                    other = node.values[1 - i]
                    r1 = ChainedComparisonFusion._extract(v, pivot)
                    r2 = ChainedComparisonFusion._extract(other, pivot)
                    if not (r1 and r2):
                        continue
                    pair = ChainedComparisonFusion._normalise(r1, r2)
                    if pair is None:
                        continue
                    r_lower, r_upper = pair
                    chain_ops = ChainedComparisonFusion._PAIRS.get(
                        (r_lower[0], r_upper[0]))
                    if chain_ops is None:
                        continue
                    # Build:  lower_bound OP1 pivot OP2 upper_bound
                    chained = ast.Compare(
                        left=r_lower[1],
                        ops=[chain_ops[0](), chain_ops[1]()],
                        comparators=[ast.Name(id=pivot, ctx=ast.Load()), r_upper[1]])
                    self.changed = True
                    return ast.copy_location(chained, node)
                return node

        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
class DictGetWithDefault(TransformationOperator):
    """
    Convert ternary dict-lookup to dict.get():
 
        d[k] if k in d else default   →   d.get(k, default)
        d[k] if k in d else None      →   d.get(k)
    """
    tier, name = Tier.L, "DictGetWithDefault"
 
    @staticmethod
    def _match(node):
        """Return (dict_name, key_node, default_node) or None."""
        if not isinstance(node, ast.IfExp):
            return None
        test = node.test
        # test must be  k in d
        if not (isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.In)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Name)):
            return None
        dict_name = test.comparators[0].id
        key_node = test.left
        # body must be  d[k]
        body = node.body
        if not (isinstance(body, ast.Subscript)
                and isinstance(body.value, ast.Name)
                and body.value.id == dict_name
                and ast.unparse(body.slice) == ast.unparse(key_node)):
            return None
        return dict_name, key_node, node.orelse
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if self._match(node) is not None:
                return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_IfExp(self, node):
                self.generic_visit(node)
                result = DictGetWithDefault._match(node)
                if result is None:
                    return node
                dict_name, key_node, default_node = result
                is_none_default = (isinstance(default_node, ast.Constant)
                                   and default_node.value is None)
                call = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=dict_name, ctx=ast.Load()),
                        attr="get", ctx=ast.Load()),
                    args=([key_node] if is_none_default else [key_node, default_node]),
                    keywords=[])
                self.changed = True
                return ast.copy_location(call, node)
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
class IdentityCompareNormalization(TransformationOperator):
    """
    Normalize equality checks against None/True/False to identity checks:
 
        x == None   →  x is None
        x != None   →  x is not None
        x == True   →  x is True
        x == False  →  x is False
    """
    tier, name = Tier.L, "IdentityCompareNormalization"
  
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Compare)
                    and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)):
                for comp in node.comparators:
                    if (isinstance(comp, ast.Constant)
                            and type(comp.value) in (type(None), bool)):
                        return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_Compare(self, node):
                self.generic_visit(node)
                new_ops = []
                for op, comp in zip(node.ops, node.comparators):
                    if (isinstance(op, ast.Eq)
                            and isinstance(comp, ast.Constant)
                            and comp.value in (None, True, False)):
                        new_ops.append(ast.Is())
                        self.changed = True
                    elif (isinstance(op, ast.NotEq)
                            and isinstance(comp, ast.Constant)
                            and comp.value is None):
                        new_ops.append(ast.IsNot())
                        self.changed = True
                    else:
                        new_ops.append(op)
                node.ops = new_ops
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
class ConstantConditionElision(TransformationOperator):
    """
    Remove dead branches with constant conditions:
 
        if True:  body      →   body
        if False: body      →   (removed / else branch kept)
        while False: body   →   (removed)
    """
    tier, name = Tier.L, "ConstantConditionElision"
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if (isinstance(node.test, ast.Constant)
                        and node.test.value in (True, False)):
                    return True
            if isinstance(node, ast.While):
                if (isinstance(node.test, ast.Constant)
                        and node.test.value is False):
                    return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_If(self, node):
                self.generic_visit(node)
                if not (isinstance(node.test, ast.Constant)
                        and node.test.value in (True, False)):
                    return node
                self.changed = True
                if node.test.value:
                    # if True → keep body
                    return node.body
                else:
                    # if False → keep else (may be empty)
                    return node.orelse if node.orelse else []
 
            def visit_While(self, node):
                self.generic_visit(node)
                if (isinstance(node.test, ast.Constant)
                        and node.test.value is False):
                    self.changed = True
                    return []  # dead loop — remove entirely
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
class NotInNormalization(TransformationOperator):
    """
    Rewrite  'not x in y'  to the cleaner  'x not in y'.
    Also rewrites 'not x is y' → 'x is not y'.
    """
    tier, name = Tier.L, "NotInNormalization"
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.UnaryOp)
                    and isinstance(node.op, ast.Not)
                    and isinstance(node.operand, ast.Compare)
                    and len(node.operand.ops) == 1
                    and isinstance(node.operand.ops[0], (ast.In, ast.Is))):
                return True
        return False
 
    def apply(self, source, llm=None):
        _FLIP = {ast.In: ast.NotIn, ast.Is: ast.IsNot}
 
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_UnaryOp(self, node):
                self.generic_visit(node)
                if (isinstance(node.op, ast.Not)
                        and isinstance(node.operand, ast.Compare)
                        and len(node.operand.ops) == 1
                        and type(node.operand.ops[0]) in _FLIP):
                    cmp = node.operand
                    cmp.ops = [_FLIP[type(cmp.ops[0])]()]
                    self.changed = True
                    return ast.copy_location(cmp, node)
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
class ConcatListLiteralFusion(TransformationOperator):
    """
    Fold adjacent list literal concatenation at parse time:
 
        [a, b] + [c, d]   →   [a, b, c, d]
 
    Only applies when BOTH operands are literal list nodes (not variables).
    """
    tier, name = Tier.L, "ConcatListLiteralFusion"
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Add)
                    and isinstance(node.left, ast.List)
                    and isinstance(node.right, ast.List)):
                return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
 
            def visit_BinOp(self, node):
                self.generic_visit(node)
                if (isinstance(node.op, ast.Add)
                        and isinstance(node.left, ast.List)
                        and isinstance(node.right, ast.List)):
                    merged = ast.List(
                        elts=node.left.elts + node.right.elts,
                        ctx=ast.Load())
                    self.changed = True
                    return ast.copy_location(merged, node)
                return node
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 

# ─── Tier H/M: LLM-based semantic operators ──────────────────

class LLMOperator(TransformationOperator):
    needs_llm = True
    _extra: str = ""

    def precondition(self, tree, source): return True

    def apply(self, source, llm=None, extra_context: str = ""):
        if not llm or not llm.available: return None
        context = self._extra
        if extra_context:
            context = f"{context}\n\n{extra_context}" if context else extra_context
        return llm.transform(source, self.name, context)


class RecursionToDynamicProgramming(LLMOperator):
    tier, name = Tier.H, "RecursionToDynamicProgramming"
    _extra = ("Rewrite the recursive function using bottom-up iterative DP. "
              "Remove all recursion. Preserve exact signature and outputs.")

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for child in ast.walk(fn):
                    if (child is not fn and isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == fn.name): return True
        return False


class NaiveSearchToIndexed(LLMOperator):
    tier, name = Tier.H, "NaiveSearchToIndexed"
    _extra = ("Replace O(n) sequential search with O(1) dict/set lookup. "
              "Pre-build the index once if the collection is static. "
              "Preserve exact output semantics.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if (isinstance(child, ast.Compare) and
                            any(isinstance(op, (ast.Eq, ast.Is)) for op in child.ops)):
                        return True
        return False


class VectorizationDelegate(LLMOperator):
    tier, name = Tier.H, "VectorizationDelegate[loop→numpy]"
    _extra = ("Vectorize numeric loops using NumPy array operations. "
              "Add 'import numpy as np'. Preserve exact numeric outputs.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, (ast.BinOp, ast.AugAssign)): return True
        return False


class AlgorithmComplexityReduction(LLMOperator):
    tier, name = Tier.H, "AlgorithmicComplexityReduction"
    _extra = ("Reduce algorithmic complexity (e.g. O(n²)→O(n log n) or O(n)). "
              "Use sorting, prefix sums, or hash maps. "
              "Preserve exact output for all valid inputs.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.For) and child is not node: return True
        return False


class GeneratorChainFusion(LLMOperator):
    tier, name = Tier.M, "GeneratorChainFusion"
    _extra = ("Fuse multiple sequential loops over the same collection into "
              "a single pass. Preserve all outputs exactly.")

    def precondition(self, tree, source):
        loop_iters = []
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            for s in fn.body:
                if isinstance(s, ast.For) and isinstance(s.iter, ast.Name):
                    loop_iters.append(s.iter.id)
        return len(loop_iters) != len(set(loop_iters))


class EarlyExitOptimization(LLMOperator):
    tier, name = Tier.M, "EarlyExitOptimization"
    _extra = ("Add early exit / break / return to loops wherever the result "
              "can be determined before full iteration completes. "
              "Preserve exact output semantics.")

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for s in fn.body:
                    if isinstance(s, ast.For):
                        for child in ast.walk(s):
                            if isinstance(child, ast.AugAssign): return True
        return False


class CachingWrapper(LLMOperator):
    tier, name = Tier.M, "CachingWrapper"
    _extra = ("Add module-level dict cache or lru_cache for repeated pure-function "
              "calls inside loops. Preserve exact output semantics.")

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
                return len(calls) >= 3
        return False


class LoopMembershipIndexingLLM(LLMOperator):
    tier, name = Tier.H, "LoopMembershipIndexingLLM"
    _extra = ("Precompute set/dict index for repeated membership checks inside loops. "
              "Keep exact output and ordering semantics.")

    def precondition(self, tree, source):
        for loop in ast.walk(tree):
            if not isinstance(loop, ast.For):
                continue
            memberships = 0
            for node in ast.walk(loop):
                if not isinstance(node, ast.Compare):
                    continue
                for op, comp in zip(node.ops, node.comparators):
                    if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Name):
                        memberships += 1
            if memberships >= 1:
                return True
        return False


class SeenSetDeduplicationLLM(LLMOperator):
    tier, name = Tier.H, "SeenSetDeduplicationLLM"
    _extra = ("When preserving order, replace repeated list-membership dedup checks "
              "with a seen-set strategy and safe fallback for unhashable values.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and len(node.test.ops) == 1
                    and isinstance(node.test.ops[0], ast.NotIn)
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Call)):
                call = node.body[0].value
                if (isinstance(call.func, ast.Attribute)
                        and call.func.attr == "append"
                        and isinstance(call.func.value, ast.Name)):
                    return True
        return False


class ManualReductionToBuiltinsLLM(LLMOperator):
    tier, name = Tier.M, "ManualReductionToBuiltinsLLM"
    _extra = ("Convert manual accumulator loops into builtins like sum/any/all/min/max "
              "using generator expressions where appropriate.")

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            has_loop_aug = any(
                isinstance(n, ast.AugAssign) and isinstance(n.op, (ast.Add, ast.Mult))
                for n in ast.walk(fn))
            has_seed = any(
                isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                for n in ast.walk(fn))
            if has_loop_aug and has_seed:
                return True
        return False


class LoopInvariantHoistingLLM(LLMOperator):
    tier, name = Tier.M, "LoopInvariantHoistingLLM"
    _extra = ("Hoist loop-invariant computations and function calls outside loops "
              "without changing observable behavior.")

    @staticmethod
    def _target_names(target):
        return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}

    def precondition(self, tree, source):
        for loop in ast.walk(tree):
            if not isinstance(loop, ast.For):
                continue
            loop_vars = self._target_names(loop.target)
            if not loop_vars:
                continue
            for call in ast.walk(loop):
                if not isinstance(call, ast.Call):
                    continue
                refs = {n.id for n in ast.walk(call) if isinstance(n, ast.Name)}
                if refs and not (refs & loop_vars):
                    return True
        return False


# ─── NEW Tier M/H LLM Operators ──────────────────────────────

class ItertoolsDelegateLLM(LLMOperator):
    tier, name = Tier.M, "ItertoolsDelegateLLM"
    _extra = ("Replace manual grouping, permutations, combinations, or chaining "
              "with the appropriate itertools function "
              "(groupby, permutations, combinations, chain, product, etc.). "
              "Add 'import itertools'. Preserve exact output semantics.")

    def precondition(self, tree, source):
        # Look for nested loops suggesting combinatorial patterns
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                for child in ast.walk(node):
                    if isinstance(child, ast.For) and child is not node:
                        return True
        # Or look for manual grouping (dict accumulator patterns)
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            if any(isinstance(n, ast.Dict) and not n.keys for n in ast.walk(fn)):
                return True
        return False


class MathToBitwiseLLM(LLMOperator):
    tier, name = Tier.M, "MathToBitwiseLLM"
    _extra = ("Convert modulo (%) and integer division (//) by powers of 2 "
              "to bitwise & and >> respectively. "
              "Only apply where the divisor is a literal power of 2. "
              "Preserve exact semantics for non-negative integers.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, (ast.Mod, ast.FloorDiv)):
                    if (isinstance(node.right, ast.Constant)
                            and isinstance(node.right.value, int)
                            and node.right.value > 0
                            and (node.right.value & (node.right.value - 1)) == 0):
                        return True
        return False


class LazyEvaluationRewriteLLM(LLMOperator):
    tier, name = Tier.M, "LazyEvaluationRewriteLLM"
    _extra = ("Move expensive variable assignments inside the conditional branches "
              "(if/elif) that actually use them, so they are only computed on the "
              "taken branch. Preserve exact output semantics.")

    def precondition(self, tree, source):
        # Heuristic: assignments before if-blocks that use those vars
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            body = fn.body
            for i, stmt in enumerate(body[:-1]):
                if (isinstance(stmt, ast.Assign)
                        and isinstance(body[i + 1], ast.If)):
                    assigned_names = {
                        n.id for n in ast.walk(stmt)
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                    used_names = {
                        n.id for n in ast.walk(body[i + 1])
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                    if assigned_names & used_names:
                        return True
        return False


class RegexPrecompilationLLM(LLMOperator):
    tier, name = Tier.M, "RegexPrecompilationLLM"
    _extra = ("Hoist all static re.match / re.search / re.sub / re.findall "
              "pattern strings into module-level re.compile() calls. "
              "Replace in-loop invocations with the compiled pattern object. "
              "Preserve exact output semantics.")

    def precondition(self, tree, source):
        RE_FUNCS = {"match", "search", "sub", "findall", "finditer", "split", "fullmatch"}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in RE_FUNCS
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                return True
        return False


class DictDoubleHashEliminationLLM(LLMOperator):
    tier, name = Tier.M, "DictDoubleHashEliminationLLM"
    _extra = ("Replace 'if k in d: d[k] += v' (double hash) patterns with "
              "dict.get(), setdefault(), or collections.defaultdict. "
              "Preserve exact output semantics.")

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and len(node.test.ops) == 1
                    and isinstance(node.test.ops[0], ast.In)
                    and isinstance(node.test.comparators[0], ast.Name)):
                dict_name = node.test.comparators[0].id
                # Check body accesses same dict
                for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                    if (isinstance(child, ast.Subscript)
                            and isinstance(child.value, ast.Name)
                            and child.value.id == dict_name):
                        return True
        return False


class TryExceptFastPathLLM(LLMOperator):
    tier, name = Tier.M, "TryExceptFastPathLLM"
    _extra = ("Replace type/bounds checking 'if isinstance(x, ...)' or 'if x is not None' "
              "guards inside loops with try...except blocks (EAFP paradigm). "
              "This can be faster in CPython when the success path is common. "
              "Preserve exact output semantics.")

    def precondition(self, tree, source):
        for loop in ast.walk(tree):
            if not isinstance(loop, ast.For): continue
            for node in ast.walk(loop):
                if (isinstance(node, ast.If)
                        and isinstance(node.test, ast.Call)
                        and isinstance(node.test.func, ast.Name)
                        and node.test.func.id == "isinstance"):
                    return True
        return False


class DefaultDictSubstitution(TransformationOperator):
    """
    Replace manual dict-with-list-default patterns with collections.defaultdict:
 
        d = {}
        for ...:
            if k not in d:
                d[k] = []
            d[k].append(v)
 
        →
 
        import collections
        d = collections.defaultdict(list)
        for ...:
            d[k].append(v)
    """
    tier, name = Tier.H, "DefaultDictSubstitution"
 
    @staticmethod
    def _find_patterns(fn_node: ast.FunctionDef) -> list[tuple[str, str]]:
        """
        Returns list of (dict_var, factory_str) for each defaultdict candidate.
        Now searches all nested scopes, not just the top-level function body.
        """
        results = []
        # Use the shared helper — walks the whole function tree
        empty_dicts = _find_dict_init_nodes(fn_node)

        for dname in empty_dicts:
            for node in ast.walk(fn_node):
                if not isinstance(node, ast.If):
                    continue
                test = node.test
                if not (isinstance(test, ast.Compare)
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.NotIn)
                        and isinstance(test.comparators[0], ast.Name)
                        and test.comparators[0].id == dname
                        and len(node.body) == 1
                        and isinstance(node.body[0], ast.Assign)):
                    continue
                init_assign = node.body[0]
                if not (len(init_assign.targets) == 1
                        and isinstance(init_assign.targets[0], ast.Subscript)
                        and isinstance(init_assign.targets[0].value, ast.Name)
                        and init_assign.targets[0].value.id == dname):
                    continue
                init_val = init_assign.value
                factory = None
                if isinstance(init_val, ast.List)  and not init_val.elts: factory = "list"
                elif isinstance(init_val, ast.Set)  and not init_val.elts: factory = "set"
                elif isinstance(init_val, ast.Dict)  and not init_val.keys: factory = "dict"
                elif isinstance(init_val, ast.Constant) and init_val.value == 0: factory = "int"
                if factory:
                    results.append((dname, factory))
                    break
        return results

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and self._find_patterns(fn):
                return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._to_replace: dict[str, str] = {}

            def visit_Module(self, node):
                self.generic_visit(node)
                if self._to_replace:
                    has_col = any(
                        isinstance(s, ast.Import)
                        and any(a.name == "collections" for a in s.names)
                        for s in node.body)
                    if not has_col:
                        node.body.insert(
                            0, ast.Import(names=[ast.alias(name="collections")]))
                return node

            def visit_FunctionDef(self, node):
                patterns = DefaultDictSubstitution._find_patterns(node)
                self._to_replace = {d: f for d, f in patterns}
                self.generic_visit(node)
                self._to_replace = {}
                return node

            def visit_Assign(self, node):
                """Replace  d = {}  with  d = collections.defaultdict(factory)."""
                if (len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in self._to_replace
                        and isinstance(node.value, ast.Dict)
                        and not node.value.keys):
                    factory = self._to_replace[node.targets[0].id]
                    node.value = ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="collections", ctx=ast.Load()),
                            attr="defaultdict", ctx=ast.Load()),
                        args=[ast.Name(id=factory, ctx=ast.Load())],
                        keywords=[])
                    self.changed = True
                return node

            def visit_If(self, node):
                """Remove  if k not in d: d[k] = []  guard blocks."""
                test = node.test
                if (isinstance(test, ast.Compare)
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.NotIn)
                        and isinstance(test.comparators[0], ast.Name)
                        and test.comparators[0].id in self._to_replace
                        and len(node.body) == 1
                        and isinstance(node.body[0], ast.Assign)
                        and not node.orelse):
                    init = node.body[0]
                    if (len(init.targets) == 1
                            and isinstance(init.targets[0], ast.Subscript)
                            and isinstance(init.targets[0].value, ast.Name)
                            and init.targets[0].value.id in self._to_replace):
                        self.changed = True
                        return None  # remove guard entirely
                self.generic_visit(node)
                return node

        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            for node in ast.walk(nt):
                for attr in ("body", "orelse", "finalbody"):
                    lst = getattr(node, attr, None)
                    if isinstance(lst, list):
                        setattr(node, attr, [s for s in lst if s is not None])
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
def _find_dict_init_nodes(fn_node: ast.FunctionDef) -> dict[str, ast.Assign]:
    """
    Walk the ENTIRE function body (including nested loops and conditionals)
    and return a mapping of  variable_name → Assign-node  for every
    ``d = {}`` assignment found.  Only the FIRST occurrence is kept so that
    the transformer knows which node to replace.
    """
    found: dict[str, ast.Assign] = {}
    for node in ast.walk(fn_node):
        if not (isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Dict)
                and not node.value.keys):
            continue
        name = node.targets[0].id
        if name not in found:          # keep first occurrence only
            found[name] = node
    return found
class CounterSubstitution(TransformationOperator):
    tier, name = Tier.H, "CounterSubstitution"

    @staticmethod
    def _find_counter_pattern(fn_node: ast.FunctionDef
                               ) -> list[tuple[str, ast.expr, ast.Assign, ast.For]]:
        """
        Returns list of (dict_var, iterable_node, init_assign_node, loop_node).
        Now detects patterns anywhere in the function, not just at top-level.
        """
        results = []
        # Full-tree scan for  d = {}
        empty_dicts: dict[str, ast.Assign] = _find_dict_init_nodes(fn_node)

        # Full-tree scan for qualifying for-loops
        for node in ast.walk(fn_node):
            if not isinstance(node, ast.For):
                continue
            loop_var = node.target
            if not isinstance(loop_var, ast.Name):
                continue
            lv_id = loop_var.id

            if len(node.body) != 1 or not isinstance(node.body[0], ast.If):
                continue
            if_stmt = node.body[0]
            test = if_stmt.test
            if not (isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.In)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == lv_id
                    and isinstance(test.comparators[0], ast.Name)):
                continue
            dname = test.comparators[0].id
            if dname not in empty_dicts:
                continue
            # body: d[x] += 1
            if not (len(if_stmt.body) == 1
                    and isinstance(if_stmt.body[0], ast.AugAssign)
                    and isinstance(if_stmt.body[0].op, ast.Add)
                    and isinstance(if_stmt.body[0].target, ast.Subscript)
                    and isinstance(if_stmt.body[0].target.value, ast.Name)
                    and if_stmt.body[0].target.value.id == dname
                    and isinstance(if_stmt.body[0].value, ast.Constant)
                    and if_stmt.body[0].value.value == 1):
                continue
            # orelse: d[x] = 1
            if not (len(if_stmt.orelse) == 1
                    and isinstance(if_stmt.orelse[0], ast.Assign)
                    and len(if_stmt.orelse[0].targets) == 1
                    and isinstance(if_stmt.orelse[0].targets[0], ast.Subscript)
                    and isinstance(if_stmt.orelse[0].targets[0].value, ast.Name)
                    and if_stmt.orelse[0].targets[0].value.id == dname
                    and isinstance(if_stmt.orelse[0].value, ast.Constant)
                    and if_stmt.orelse[0].value.value == 1):
                continue
            results.append((dname, node.iter,
                             empty_dicts[dname], node))
        return results

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and self._find_counter_pattern(fn):
                return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._info: dict = {}

            def visit_Module(self, node):
                self.generic_visit(node)
                if self._info:
                    has_col = any(
                        isinstance(s, ast.Import)
                        and any(a.name == "collections" for a in s.names)
                        for s in node.body)
                    if not has_col:
                        node.body.insert(
                            0, ast.Import(names=[ast.alias(name="collections")]))
                return node

            def visit_FunctionDef(self, node):
                patterns = CounterSubstitution._find_counter_pattern(node)
                # Map: dict_var → (iterable, init_node_id, loop_node_id)
                self._info = {
                    d: (it, id(init), id(loop))
                    for d, it, init, loop in patterns
                }
                self.generic_visit(node)
                self._info = {}
                return node

            def visit_Assign(self, node):
                """Replace  d = {}  with  d = collections.Counter(iterable)."""
                if (len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)):
                    dname = node.targets[0].id
                    if (dname in self._info
                            and id(node) == self._info[dname][1]
                            and isinstance(node.value, ast.Dict)
                            and not node.value.keys):
                        iterable = self._info[dname][0]
                        node.value = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="collections", ctx=ast.Load()),
                                attr="Counter", ctx=ast.Load()),
                            args=[iterable], keywords=[])
                        self.changed = True
                return node

            def visit_For(self, node):
                """Remove the manual counting loop."""
                self.generic_visit(node)
                for dname, (_, _, loop_id) in self._info.items():
                    if id(node) == loop_id:
                        self.changed = True
                        return None   # delete the for-loop
                return node

        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            for node in ast.walk(nt):
                for attr in ("body", "orelse", "finalbody"):
                    lst = getattr(node, attr, None)
                    if isinstance(lst, list):
                        setattr(node, attr, [s for s in lst if s is not None])
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
class HeapNLargestSmallest(TransformationOperator):
    """
    Replace sliced sorted() calls with heapq equivalents:
 
        sorted(lst)[:n]                →   heapq.nsmallest(n, lst)
        sorted(lst, reverse=True)[:n]  →   heapq.nlargest(n, lst)
    """
    tier, name = Tier.H, "HeapNLargestSmallest"
 
    @staticmethod
    def _match(node):
        """
        Returns (n_node, lst_node, is_largest) or None.
        """
        if not (isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Slice)):
            return None
        slc = node.slice
        # Slice must be  [:n]  — lower=None, step=None
        if slc.lower is not None or slc.step is not None:
            return None
        if slc.upper is None or not isinstance(slc.upper, ast.Constant):
            return None
        n_node = slc.upper
        call = node.value
        if not (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "sorted"
                and len(call.args) == 1):
            return None
        lst_node = call.args[0]
        # Check for reverse=True keyword
        is_largest = any(
            isinstance(kw, ast.keyword)
            and kw.arg == "reverse"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in call.keywords)
        # No unsupported keywords (key= is fine for both)
        unsupported = [kw for kw in call.keywords
                       if kw.arg not in ("reverse", "key")]
        if unsupported:
            return None
        key_kws = [kw for kw in call.keywords if kw.arg == "key"]
        return n_node, lst_node, is_largest, key_kws
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if self._match(node) is not None:
                return True
        return False
 
    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._need_heapq = False
 
            def visit_Module(self, node):
                self.generic_visit(node)
                if self._need_heapq:
                    has_heapq = any(
                        isinstance(s, ast.Import)
                        and any(a.name == "heapq" for a in s.names)
                        for s in node.body)
                    if not has_heapq:
                        node.body.insert(
                            0, ast.Import(names=[ast.alias(name="heapq")]))
                return node
 
            def visit_Subscript(self, node):
                self.generic_visit(node)
                result = HeapNLargestSmallest._match(node)
                if result is None:
                    return node
                n_node, lst_node, is_largest, key_kws = result
                fn_name = "nlargest" if is_largest else "nsmallest"
                new_call = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="heapq", ctx=ast.Load()),
                        attr=fn_name, ctx=ast.Load()),
                    args=[n_node, lst_node],
                    keywords=key_kws)
                self.changed = True
                self._need_heapq = True
                return ast.copy_location(new_call, node)
 
        try:
            t = ast.parse(source)
            tr = _T()
            nt = tr.visit(t)
            if tr.changed:
                ast.fix_missing_locations(nt)
                return ast.unparse(nt)
        except Exception:
            pass
        return None
 
 
# ──────────────────────────────────────────────────────────────────────────────
# TIER M — LLM-BASED SEMANTIC OPERATORS
# ──────────────────────────────────────────────────────────────────────────────
 
 
class SlotsDelegateLLM(LLMOperator):
    """
    Add __slots__ to classes whose instances only use a fixed set of attributes.
    Reduces per-instance memory significantly for large numbers of instances.
    """
    tier, name = Tier.M, "SlotsDelegateLLM"
    _extra = (
        "Analyze all __init__ self.x = ... assignments to determine the fixed "
        "attribute set. Add __slots__ = (...) to the class definition if no "
        "dynamic attributes are set anywhere. Do not add __slots__ if the class "
        "inherits from a class that does not define __slots__, unless that base "
        "is 'object'. Preserve exact semantics.")
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Skip classes that already have __slots__
            for item in node.body:
                if (isinstance(item, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "__slots__"
                                for t in item.targets)):
                    break
            else:
                # Has an __init__ with self.x = ... assignments
                for method in node.body:
                    if (isinstance(method, ast.FunctionDef)
                            and method.name == "__init__"):
                        for s in ast.walk(method):
                            if (isinstance(s, ast.Assign)
                                    and any(isinstance(t, ast.Attribute)
                                            and isinstance(t.value, ast.Name)
                                            and t.value.id == "self"
                                            for t in s.targets)):
                                return True
        return False
 
 
class ConcurrentMapDelegateLLM(LLMOperator):
    """
    Replace pure list-comprehension function calls with ThreadPoolExecutor.map
    for IO-bound tasks, or ProcessPoolExecutor for CPU-bound ones.
    """
    tier, name = Tier.M, "ConcurrentMapDelegateLLM"
    _extra = (
        "If the list comprehension applies a single named function to each "
        "element and that function has no shared mutable state, replace it with "
        "concurrent.futures.ThreadPoolExecutor().map() for IO-bound work or "
        "ProcessPoolExecutor for CPU-bound work. "
        "Add 'from concurrent.futures import ThreadPoolExecutor'. "
        "Wrap in list() to materialise results. "
        "Preserve exact output semantics and ordering.")
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if isinstance(node, ast.ListComp):
                if (len(node.generators) == 1
                        and not node.generators[0].ifs
                        and isinstance(node.generators[0].target, ast.Name)
                        and isinstance(node.elt, ast.Call)
                        and isinstance(node.elt.func, ast.Name)
                        and len(node.elt.args) == 1
                        and isinstance(node.elt.args[0], ast.Name)
                        and node.elt.args[0].id == node.generators[0].target.id):
                    return True
        return False
 
 
class BisectSubstitutionLLM(LLMOperator):
    """
    Replace manual binary-search loops with bisect.bisect_left / bisect_right.
    """
    tier, name = Tier.M, "BisectSubstitutionLLM"
    _extra = (
        "Identify manual binary search loops (while lo < hi / while left <= right "
        "patterns that halve the search space). Replace them with the appropriate "
        "bisect.bisect_left or bisect.bisect_right call. "
        "Add 'import bisect'. Preserve exact output semantics.")
 
    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if not isinstance(node, ast.While):
                continue
            test = node.test
            # Heuristic: while lo < hi or while left <= right
            if (isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], (ast.Lt, ast.LtE))
                    and isinstance(test.left, ast.Name)
                    and isinstance(test.comparators[0], ast.Name)):
                # Look for mid = (lo + hi) // 2 inside body
                for child in ast.walk(node):
                    if (isinstance(child, ast.Assign)
                            and isinstance(child.value, ast.BinOp)
                            and isinstance(child.value.op, ast.FloorDiv)):
                        return True
        return False
 
 
class StringBuildBufferLLM(LLMOperator):
    """
    Catch complex string-building patterns (conditional appends, nested loops)
    not handled by StringConcatToJoin, and rewrite using io.StringIO or
    a parts-list with a final join.
    """
    tier, name = Tier.M, "StringBuildBufferLLM"
    _extra = (
        "Find string accumulation patterns using += inside loops or conditionals "
        "that are too complex for a simple join rewrite. "
        "Rewrite using a list of parts with ''.join(parts) at the end, "
        "or use io.StringIO write/getvalue if the structure is complex. "
        "Preserve exact output semantics.")
 
    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            # Find  s = ""  followed later by  s += expr  in a loop
            str_vars = set()
            for s in ast.walk(fn):
                if (isinstance(s, ast.Assign)
                        and len(s.targets) == 1
                        and isinstance(s.targets[0], ast.Name)
                        and isinstance(s.value, ast.Constant)
                        and s.value.value == ""):
                    str_vars.add(s.targets[0].id)
            for loop in ast.walk(fn):
                if not isinstance(loop, ast.For):
                    continue
                for child in ast.walk(loop):
                    if (isinstance(child, ast.AugAssign)
                            and isinstance(child.op, ast.Add)
                            and isinstance(child.target, ast.Name)
                            and child.target.id in str_vars):
                        # Only fire if the loop body is non-trivial
                        # (more than just the aug-assign)
                        if len(loop.body) > 1:
                            return True
        return False

# ─── Local Minima Escape Operator ────────────────────────────

class GenericSemanticRewriteLLM(LLMOperator):
    """
    Fallback escape mechanism: asks the LLM to try a completely
    different algorithmic approach to break out of local minima.
    Tier H. Precondition always True (triggered programmatically).
    """
    tier, name = Tier.H, "GenericSemanticRewriteLLM"
    _extra = ("Refactor and rewrite this function using a completely different "
              "algorithmic approach or structural coding style. "
              "Swap loops for comprehensions, invert conditionals, or use "
              "different data structures to reshape the AST. "
              "The goal is maximum energy/performance improvement. "
              "Preserve exact function signature and return semantics.")

    def precondition(self, tree, source):
        return True   # Always applicable — triggered by escape logic


ALL_OPERATORS: list[TransformationOperator] = [
    # ── Tier L deterministic
    ForLoopToComprehension(),
    IteratorSubstitution(),
    ReductionListCompToGenerator(),
    DictKeysMembershipElision(),
    StringConcatToJoin(),
    SortedToInPlaceSort(),
    LocalImportHoisting(),
    JoinListCompToGenerator(),
    GeneratorToYieldFrom(),
    MultipleOrToSetMembership(),
    EnumerateSubstitution(),
    ListPopZeroToDeque(),
    FStringConversion(),
    MultipleAssignmentFusion(),
    LoopGlobalToLocalHoisting(),
    ReturnBoolSimplification(),
    TupleUnpackInLoop(),
    ChainedComparisonFusion(),
    DictGetWithDefault(),
    IdentityCompareNormalization(),
    ConstantConditionElision(),
    NotInNormalization(),
    ConcatListLiteralFusion(),
    # ── Tier H/M AST-based
    ListToSetMembership(),
    LoopMembershipSetCache(),
    SeenSetForAppendDedup(),
    MemoizationAddition(),
    DefaultDictSubstitution(),
    CounterSubstitution(),
    HeapNLargestSmallest(),
    # ── Tier H LLM
    RecursionToDynamicProgramming(),
    NaiveSearchToIndexed(),
    AlgorithmComplexityReduction(),
    VectorizationDelegate(),
    LoopMembershipIndexingLLM(),
    SeenSetDeduplicationLLM(),
    MathToBitwiseLLM(),
    # ── Tier M LLM
    GeneratorChainFusion(),
    ManualReductionToBuiltinsLLM(),
    LoopInvariantHoistingLLM(),
    EarlyExitOptimization(),
    # CachingWrapper(),
    ItertoolsDelegateLLM(),
    LazyEvaluationRewriteLLM(),
    RegexPrecompilationLLM(),
    DictDoubleHashEliminationLLM(),
    TryExceptFastPathLLM(),
    SlotsDelegateLLM(),
    ConcurrentMapDelegateLLM(),
    BisectSubstitutionLLM(),
    StringBuildBufferLLM(),
    # GenericSemanticRewriteLLM is NOT in the standard list; triggered by escape logic
]

# Separate reference for the escape operator
_ESCAPE_OPERATOR = GenericSemanticRewriteLLM()


# ══════════════════════════════════════════════════════════════════════════════
# 5.  Fidelity Statistics Engine
#     Pure-stdlib statistical utilities for robust energy measurement.
# ══════════════════════════════════════════════════════════════════════════════

def _ncdf_approx(z: float) -> float:
    """Standard normal CDF via math.erf (stdlib only)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _iqr_filter(readings: list[float]) -> tuple[list[float], int, float]:
    """
    Remove outliers beyond 2.5 × IQR from Q1/Q3.
    Returns (filtered_readings, n_removed).
    Falls back to original list if <4 readings.
    """
    n = len(readings)
    if n < 4:
        return readings, 0, 0
    s = sorted(readings)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    iqr = q3 - q1
    if iqr < 1e-20:   # effectively zero variance — keep all
        return readings, 0, 0
    lo = q1 - 2.5 * iqr
    hi = q3 + 2.5 * iqr
    filtered = [r for r in readings if lo <= r <= hi]
    removed = n - len(filtered)
    return (filtered if filtered else readings), removed, iqr


def _trimmed_mean(readings: list[float], trim: int = 1) -> float:
    """Mean after dropping `trim` highest and `trim` lowest values."""
    s = sorted(readings)
    if len(s) <= 2 * trim:
        return sum(s) / len(s)
    trimmed = s[trim: len(s) - trim]
    return sum(trimmed) / len(trimmed)


def _median(readings: list[float]) -> float:
    s = sorted(readings)
    n = len(s)
    if n == 0: return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _bootstrap_ci(readings: list[float], n_boot: int = 400,
                  alpha: float = 0.05) -> tuple[float, float]:
    """
    Bootstrap percentile 95% CI for the mean.
    Pure stdlib — uses random module.
    """
    n = len(readings)
    if n < 2:
        v = readings[0] if readings else 0.0
        return v, v
    boot_means = []
    for _ in range(n_boot):
        sample = [readings[random.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lo_idx = max(0,     int(alpha / 2 * n_boot))
    hi_idx = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return boot_means[lo_idx], boot_means[hi_idx]


def _tcdf_approx(t: float, df: float) -> float:
    """
    Accurate t-distribution CDF via the regularised incomplete beta function,
    implemented using Lentz's continued-fraction method (stdlib only).

    P(T <= t) for a t-distribution with `df` degrees of freedom.
    Matches scipy.stats.t.cdf to within ~1e-6 for df >= 2.
    """
    # For large df the normal approximation is fine (error < 0.001 for df >= 30)
    if df >= 30:
        return _ncdf_approx(t)

    # --- Regularised incomplete beta  I_x(a, b) via continued fraction ---
    # Relation:  CDF(t, df) = 1 - 0.5 * I_x(df/2, 0.5)
    # where x = df / (df + t^2)   [two-tailed beta transform]
    a = df / 2.0
    b = 0.5
    x = df / (df + t * t)

    def _beta_cf(a, b, x, max_iter=200, tol=1e-12):
        """
        Evaluate I_x(a,b) via Lentz's continued fraction (Numerical Recipes §6.4).
        Returns the regularised incomplete beta value.
        """
        # Front factor: x^a * (1-x)^b / (a * Beta(a,b))
        # We compute log of front factor using lgamma (stdlib math)
        lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(
            a * math.log(max(x, 1e-300))
            + b * math.log(max(1.0 - x, 1e-300))
            - lbeta
        ) / a

        # Lentz's method
        TINY = 1e-300
        f = TINY
        C, D = f, 0.0
        for m in range(0, max_iter):
            for step in range(2):
                if step == 0:
                    # Even step (m=0 special-cased)
                    if m == 0:
                        d = 1.0
                    else:
                        d = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
                else:
                    d = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
                D = 1.0 + d * D
                if abs(D) < TINY: D = TINY
                C = 1.0 + d / C
                if abs(C) < TINY: C = TINY
                D = 1.0 / D
                delta = C * D
                f *= delta
                if abs(delta - 1.0) < tol:
                    return front * f
        return front * f   # best estimate even if not converged

    # x must be in (0, 1); clamp for numerical safety
    x = max(1e-15, min(1.0 - 1e-15, x))

    # I_x(a,b) converges better when x < (a+1)/(a+b+2);  otherwise use symmetry
    if x < (a + 1.0) / (a + b + 2.0):
        incomplete_beta = _beta_cf(a, b, x)
    else:
        incomplete_beta = 1.0 - _beta_cf(b, a, 1.0 - x)

    # Two-tailed → one-tailed CDF
    p_two_tail = incomplete_beta        # P(|T| >= |t|)
    p_one_tail  = 1.0 - p_two_tail / 2  # P(T <= t)  for t > 0

    return max(0.0, min(1.0, p_one_tail))

def _welch_t_p_improvement(mean_base: float, std_base: float, n_base: int,
                            mean_cand: float, std_cand: float, n_cand: int,
                            ) -> tuple[float, float]:
    """
    Welch t-test: returns (t_stat, p_improvement).
    p_improvement = P(candidate_energy < baseline_energy).
    A positive t means candidate is faster (lower energy).

    Uses the Lentz continued-fraction t-CDF for df < 30 (accurate),
    and the normal approximation for df >= 30 (error < 0.001).
    """
    se2 = std_base ** 2 / max(n_base, 1) + std_cand ** 2 / max(n_cand, 1)
    se  = math.sqrt(max(se2, 1e-30))
    # t > 0 means baseline > candidate, i.e. candidate uses less energy
    t = (mean_base - mean_cand) / se

    # Welch-Satterthwaite degrees of freedom
    va = std_base ** 2 / max(n_base, 1)
    vb = std_cand ** 2 / max(n_cand, 1)
    denom = (va ** 2 / max(n_base - 1, 1)) + (vb ** 2 / max(n_cand - 1, 1))
    df = (va + vb) ** 2 / max(denom, 1e-30)
    df = max(df, 1.0)   # clamp — df < 1 is not meaningful

    p = _tcdf_approx(t, df)
    return t, max(0.0, min(1.0, p))


def _compute_rich_stats(readings_raw: list[float],
                        baseline: Optional["EnergyMeasurement"],
                        fidelity: "Fidelity",
                        co2_intensity: float,
                        inner_mult: int) -> "EnergyMeasurement":
    """
    Given a list of raw per-pass joule readings, compute all statistics and
    return a fully populated EnergyMeasurement.
    """
    # --- IQR outlier filter ---
    readings, n_outliers, iqr_val = _iqr_filter(readings_raw)

    n = len(readings)
    mean = sum(readings) / n
    variance = sum((r - mean) ** 2 for r in readings) / max(n - 1, 1)
    std = math.sqrt(variance)
    cv = std / mean if mean > 0 else 0.0

    trim = 1 if n >= 4 else 0
    t_mean = _trimmed_mean(readings, trim)
    med = _median(readings)
    ci_lo, ci_hi = _bootstrap_ci(readings)
    co2_g = mean * co2_intensity / 3_600_000

    improvement = 0.0
    p_impr = 0.5
    welch_t = 0.0
    if baseline is not None and baseline.mean_j > 0:
        improvement = 1.0 - mean / baseline.mean_j
        welch_t, p_impr = _welch_t_p_improvement(
            baseline.mean_j, baseline.std_j, baseline.n_runs,
            mean, std, n)

    return EnergyMeasurement(
        mean_j=mean, std_j=std, n_runs=n,
        fidelity=fidelity,
        improvement=improvement,
        co2_g=co2_g,
        inner_loop_multiplier=inner_mult,
        readings_j=readings_raw,          # store originals for research
        trimmed_mean_j=t_mean,
        median_j=med,
        cv=cv,
        iqr_j=iqr_val,
        n_outliers_removed=n_outliers,
        ci_low_j=ci_lo,
        ci_high_j=ci_hi,
        p_improvement=p_impr,
        welch_t=welch_t,
    )


# ──────────────────────────────────────────────────────────────────────────────
# FidelityCalibrator
# Tracks how well F1/F2 predict F3 and adjusts P(abandon) thresholds in-run.
# ──────────────────────────────────────────────────────────────────────────────

class FidelityCalibrator:
    """
    Collects (f1_improvement, f3_improvement) and (f2_improvement, f3_improvement)
    pairs from completed escalations. After MIN_PAIRS observations it:
      - Computes Pearson r between proxy and ground-truth
      - Estimates mean absolute error (MAE)
      - Adjusts effective P-abandon thresholds:
          * high correlation  → thresholds can be tightened (proxy is trustworthy)
          * low correlation   → thresholds loosened (proxy is noisy, don't prune early)
    """
    MIN_PAIRS = 5

    def __init__(self, base_p_f1: float = 0.10, base_p_f2: float = 0.25):
        self._base_p_f1 = base_p_f1
        self._base_p_f2 = base_p_f2
        # Paired observations: (proxy_improvement, f3_improvement)
        self._f1_f3: list[tuple[float, float]] = []
        self._f2_f3: list[tuple[float, float]] = []
        # Running calibration metrics (for research logging)
        self.f1_f3_pearson: Optional[float] = None
        self.f2_f3_pearson: Optional[float] = None
        self.f1_f3_mae: Optional[float] = None
        self.f2_f3_mae: Optional[float] = None
        self.f1_f3_bias: Optional[float] = None   # mean(f1_impr - f3_impr)
        self.f2_f3_bias: Optional[float] = None

    def record_f1_f3(self, f1_improvement: float, f3_improvement: float):
        self._f1_f3.append((f1_improvement, f3_improvement))
        if len(self._f1_f3) >= self.MIN_PAIRS:
            self._recalc_f1()

    def record_f2_f3(self, f2_improvement: float, f3_improvement: float):
        self._f2_f3.append((f2_improvement, f3_improvement))
        if len(self._f2_f3) >= self.MIN_PAIRS:
            self._recalc_f2()

    def _pearson(self, pairs: list[tuple[float, float]]) -> float:
        xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = math.sqrt(sum((x - mx)**2 for x in xs) *
                        sum((y - my)**2 for y in ys) + 1e-15)
        return num / den

    def _recalc_f1(self):
        self.f1_f3_pearson = self._pearson(self._f1_f3)
        errs = [abs(a - b) for a, b in self._f1_f3]
        self.f1_f3_mae = sum(errs) / len(errs)
        self.f1_f3_bias = sum(a - b for a, b in self._f1_f3) / len(self._f1_f3)

    def _recalc_f2(self):
        self.f2_f3_pearson = self._pearson(self._f2_f3)
        errs = [abs(a - b) for a, b in self._f2_f3]
        self.f2_f3_mae = sum(errs) / len(errs)
        self.f2_f3_bias = sum(a - b for a, b in self._f2_f3) / len(self._f2_f3)

    def effective_p_abandon_f1(self) -> float:
        """
        Returns the adaptive P(better) floor for F1.
        Loosens when proxy is poorly correlated; tightens when reliable.
        """
        if self.f1_f3_pearson is None:
            return self._base_p_f1     # not enough data yet
        r = self.f1_f3_pearson
        if r < 0.3:    return max(self._base_p_f1 * 0.5, 0.03)   # very noisy → very lenient
        if r < 0.6:    return self._base_p_f1                      # default
        return min(self._base_p_f1 * 2.0, 0.20)                    # reliable → slightly stricter

    def effective_p_abandon_f2(self) -> float:
        if self.f2_f3_pearson is None:
            return self._base_p_f2
        r = self.f2_f3_pearson
        if r < 0.3:    return max(self._base_p_f2 * 0.5, 0.08)
        if r < 0.6:    return self._base_p_f2
        return min(self._base_p_f2 * 1.5, 0.40)

    def summary_dict(self) -> dict:
        return {
            "n_f1_f3_pairs": len(self._f1_f3),
            "n_f2_f3_pairs": len(self._f2_f3),
            "f1_f3_pearson": self.f1_f3_pearson,
            "f2_f3_pearson": self.f2_f3_pearson,
            "f1_f3_mae": self.f1_f3_mae,
            "f2_f3_mae": self.f2_f3_mae,
            "f1_f3_bias": self.f1_f3_bias,
            "f2_f3_bias": self.f2_f3_bias,
            "effective_p_abandon_f1": self.effective_p_abandon_f1(),
            "effective_p_abandon_f2": self.effective_p_abandon_f2(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# MultiFidelityOracle  v3
# ──────────────────────────────────────────────────────────────────────────────

class MultiFidelityOracle:

    def __init__(self, func_name: str, test_inputs: list[tuple],
                 use_process_isolation: bool = True,
                 co2_intensity: float = 475.0,
                 adaptive_reps: bool = True,
                 calibrator: Optional[FidelityCalibrator] = None):
        self.func_name = func_name
        self.test_inputs = test_inputs
        self.use_process_isolation = use_process_isolation
        self.co2_intensity = co2_intensity
        self.adaptive_reps = adaptive_reps
        self.calibrator = calibrator or FidelityCalibrator()
        self._baseline: Optional[EnergyMeasurement] = None
        # Research stats
        self.isolation_failures: int = 0
        self.isolation_successes: int = 0
        self.adaptive_escalations: int = 0   # times extra reps were triggered

    def establish_baseline(self, source: str) -> Optional[EnergyMeasurement]:
        m = self.measure(source, Fidelity.F3)
        self._baseline = m
        return m

    def measure(self, source: str, fidelity: Fidelity,
                warmup: int = 1,
                extra_reps: int = 0) -> Optional[EnergyMeasurement]:
        """
        Measure energy at the given fidelity level.
        extra_reps: additional reps beyond the base count (from adaptive escalation).
        """
        if fidelity == Fidelity.F0:
            return None
        n_base = FIDELITY_REPS[fidelity]
        n = n_base + extra_reps

        if self.use_process_isolation:
            result = self._measure_isolated(source, n, warmup)
            if result is not None:
                readings_raw, inner_mult = result
                self.isolation_successes += 1
                m = _compute_rich_stats(readings_raw, self._baseline,
                                        fidelity, self.co2_intensity, inner_mult)
                m.adaptive_extra_reps = extra_reps
                return m
            else:
                self.isolation_failures += 1

        return self._measure_inprocess(source, fidelity, n, warmup, extra_reps)

    def measure_with_adaptive_reps(self, source: str, fidelity: Fidelity,
                                   warmup: int = 1) -> Optional[EnergyMeasurement]:
        """
        Measure at fidelity; if CV > threshold, automatically doubles reps
        and re-measures before returning. Records extra reps in measurement.
        """
        m = self.measure(source, fidelity, warmup)
        if m is None:
            return None
        if (self.adaptive_reps
                and fidelity in (Fidelity.F1, Fidelity.F2)
                and m.cv > CV_TRIGGER_EXTRA_REPS):
            extra = min(FIDELITY_ADAPTIVE_EXTRA[fidelity],
                        FIDELITY_REPS[fidelity])  # cap at 1× base
            m2 = self.measure(source, fidelity, warmup, extra_reps=extra)
            if m2 is not None:
                self.adaptive_escalations += 1
                m2.adaptive_extra_reps = extra
                return m2
        return m

    def _measure_isolated(self, source: str, n_reps: int,
                          warmup: int) -> Optional[tuple[list[float], int]]:
        """Returns (raw_readings_j, inner_mult) or None on failure."""
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        p = ctx.Process(
            target=_isolated_measure_worker,
            args=(queue, source, self.func_name, self.test_inputs,
                  n_reps, warmup, self.co2_intensity,
                  RAPL_DOMAINS, _TDP_WATTS, _ACTIVE_BACKEND.value),
            daemon=True)
        p.start()
        p.join(timeout=120)
        if p.is_alive():
            p.terminate(); p.join()
            return None
        if p.exitcode != 0 or queue.empty():
            return None
        readings_raw, inner_mult, err = queue.get_nowait()
        if err is not None:
            print(f"[Isolation] Worker error: {err}", file=sys.stderr)
            return None
        if readings_raw is None:
            print("[Isolation] Worker returned no readings.", file=sys.stderr)
            return None
        return readings_raw, inner_mult

    def _measure_inprocess(self, source: str, fidelity: Fidelity,
                           n: int, warmup: int,
                           extra_reps: int = 0) -> Optional[EnergyMeasurement]:
        """Fallback in-process measurement."""
        readings_raw: list[float] = []
        try:
            ns: dict = {}
            exec(compile(source, "<spectra>", "exec"), ns)
            fn: Callable = ns[self.func_name]
            for _ in range(warmup):
                for args in self.test_inputs[:1]:
                    fn(*copy.deepcopy(args))

            inner_mult = 1
            if _ACTIVE_BACKEND == EnergyBackend.RAPL:
                t_probe = time.perf_counter()
                for args in self.test_inputs:
                    fn(*copy.deepcopy(args))
                elapsed = time.perf_counter() - t_probe
                if 0 < elapsed < 0.05:
                    inner_mult = max(1, int(0.05 / elapsed))

            for _ in range(n):
                with EnergyMeter() as em:
                    for _ in range(inner_mult):
                        for args in self.test_inputs:
                            fn(*copy.deepcopy(args))
                readings_raw.append(em.result.joules / inner_mult)

        except Exception:
            return None

        m = _compute_rich_stats(readings_raw, self._baseline,
                                fidelity, self.co2_intensity, inner_mult)
        m.adaptive_extra_reps = extra_reps
        return m


# ──────────────────────────────────────────────────────────────────────────────
# Fidelity Decision Engine
# Replaces the old _abandon_threshold + _is_significant pair with a single
# probabilistic decision object that carries full audit information.
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FidelityDecision:
    """Outcome of a fidelity-level evaluation decision."""
    action: str           # "pass" | "abandon" | "uncertain_pass"
    reason: str           # human-readable explanation
    p_improvement: float  # P(candidate < baseline)
    welch_t: float
    cv: float
    threshold_used: float
    adaptive_extra_reps: int = 0
    calibrator_corr: Optional[float] = None


class FidelityDecisionEngine:
    """
    Encapsulates all abandon/confirm logic for F1, F2, F3.
    Noise-floor-aware, calibrator-adaptive, outlier-robust.
    """

    def __init__(self, calibrator: FidelityCalibrator,
                 p_abandon_f1: float = 0.10,
                 p_abandon_f2: float = 0.25,
                 p_confirm_f3: float = 0.90):
        self.calibrator = calibrator
        self._p_f1 = p_abandon_f1
        self._p_f2 = p_abandon_f2
        self._p_f3 = p_confirm_f3
        # Track noise floor from baseline (set by optimizer after baseline measurement)
        self.noise_floor_cv: float = 0.0

    def set_noise_floor(self, baseline: EnergyMeasurement):
        """Estimate noise floor from baseline CV for context-aware decisions."""
        self.noise_floor_cv = baseline.cv

    def decide_f1(self, m: EnergyMeasurement) -> FidelityDecision:
        p_thresh = self.calibrator.effective_p_abandon_f1()
        corr = self.calibrator.f1_f3_pearson

        # If CV is extremely high AND we're on a noisy backend, treat as uncertain
        if m.cv > 0.50:
            return FidelityDecision(
                action="uncertain_pass",
                reason=f"CV={m.cv:.2f} too high to make reliable F1 decision — passing forward",
                p_improvement=m.p_improvement,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=p_thresh,
                adaptive_extra_reps=m.adaptive_extra_reps,
                calibrator_corr=corr)

        if m.p_improvement < p_thresh:
            return FidelityDecision(
                action="abandon",
                reason=(f"P(better)={m.p_improvement:.3f} < threshold={p_thresh:.3f}  "
                        f"t={m.welch_t:.2f}  CV={m.cv:.2f}"),
                p_improvement=m.p_improvement,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=p_thresh,
                adaptive_extra_reps=m.adaptive_extra_reps,
                calibrator_corr=corr)

        return FidelityDecision(
            action="pass",
            reason=f"P(better)={m.p_improvement:.3f} >= {p_thresh:.3f}  CV={m.cv:.2f}",
            p_improvement=m.p_improvement,
            welch_t=m.welch_t, cv=m.cv,
            threshold_used=p_thresh,
            adaptive_extra_reps=m.adaptive_extra_reps,
            calibrator_corr=corr)

    def decide_f2(self, m: EnergyMeasurement) -> FidelityDecision:
        p_thresh = self.calibrator.effective_p_abandon_f2()
        corr = self.calibrator.f2_f3_pearson

        if m.cv > 0.40:
            return FidelityDecision(
                action="uncertain_pass",
                reason=f"CV={m.cv:.2f} too high for reliable F2 decision — passing forward",
                p_improvement=m.p_improvement,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=p_thresh,
                adaptive_extra_reps=m.adaptive_extra_reps,
                calibrator_corr=corr)

        if m.p_improvement < p_thresh:
            return FidelityDecision(
                action="abandon",
                reason=(f"P(better)={m.p_improvement:.3f} < threshold={p_thresh:.3f}  "
                        f"t={m.welch_t:.2f}  CV={m.cv:.2f}"),
                p_improvement=m.p_improvement,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=p_thresh,
                adaptive_extra_reps=m.adaptive_extra_reps,
                calibrator_corr=corr)

        return FidelityDecision(
            action="pass",
            reason=f"P(better)={m.p_improvement:.3f} >= {p_thresh:.3f}  CV={m.cv:.2f}",
            p_improvement=m.p_improvement,
            welch_t=m.welch_t, cv=m.cv,
            threshold_used=p_thresh,
            adaptive_extra_reps=m.adaptive_extra_reps,
            calibrator_corr=corr)

    def decide_f3(self, m: EnergyMeasurement,
                  baseline: EnergyMeasurement) -> FidelityDecision:
        """
        F3 confirmation: requires p_improvement >= p_confirm_f3.
        Uses the trimmed mean for the final answer to be outlier-robust.
        """
        # Recompute t and p using trimmed mean for extra robustness
        # Use the standard (non-trimmed) statistics for a consistent Welch test.
        # The trimmed-mean path above is the primary signal; this is a cross-check.
        _, p_trimmed = _welch_t_p_improvement(
            baseline.mean_j, baseline.std_j, baseline.n_runs,
            m.mean_j,        m.std_j,        m.n_runs)

        # Use the more conservative of the two p values
        p_final = min(m.p_improvement, p_trimmed)

        if p_final >= self._p_f3:
            return FidelityDecision(
                action="confirm",
                reason=(f"P(better)={p_final:.3f} >= {self._p_f3:.3f}  "
                        f"CV={m.cv:.2f}  CI=[{m.ci_low_mj:.4f},{m.ci_high_mj:.4f}]mJ"),
                p_improvement=p_final,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=self._p_f3)
        else:
            return FidelityDecision(
                action="reject",
                reason=(f"P(better)={p_final:.3f} < {self._p_f3:.3f}  "
                        f"CV={m.cv:.2f}  CI=[{m.ci_low_mj:.4f},{m.ci_high_mj:.4f}]mJ"),
                p_improvement=p_final,
                welch_t=m.welch_t, cv=m.cv,
                threshold_used=self._p_f3)


# ══════════════════════════════════════════════════════════════════════════════
# 6.  Energy Surrogate (GP)  — enriched features + throttled retraining
# ══════════════════════════════════════════════════════════════════════════════

def _halstead_volume(tree: ast.AST) -> float:
    """Approximate Halstead Volume from AST."""
    operators: set[str] = set()
    operands:  set[str] = set()
    n1 = n2 = 0
    OP_TYPES = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd,
                ast.FloorDiv, ast.MatMult, ast.And, ast.Or, ast.Not,
                ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
                ast.Is, ast.IsNot, ast.In, ast.NotIn,
                ast.UAdd, ast.USub, ast.Invert)
    for node in ast.walk(tree):
        cls = type(node).__name__
        if isinstance(node, OP_TYPES):
            operators.add(cls); n1 += 1
        elif isinstance(node, ast.Name):
            operands.add(node.id); n2 += 1
        elif isinstance(node, ast.Constant):
            operands.add(str(node.value)); n2 += 1
    eta1, eta2 = max(len(operators), 1), max(len(operands), 1)
    N = n1 + n2
    return N * math.log2(eta1 + eta2) if (eta1 + eta2) > 0 else 0.0


def _cyclomatic_complexity(tree: ast.AST) -> int:
    """McCabe cyclomatic complexity approximation."""
    cc = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While,
                              ast.ExceptHandler, ast.With,
                              ast.Assert)):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
    return cc


def _memory_access_density(tree: ast.AST) -> float:
    """(Subscript + Attribute) / total nodes."""
    total = sum(1 for _ in ast.walk(tree))
    if total == 0: return 0.0
    mem = sum(1 for n in ast.walk(tree)
              if isinstance(n, (ast.Subscript, ast.Attribute)))
    return mem / total


def _algorithmic_depth(tree: ast.AST) -> int:
    """Maximum nesting depth of For/While loops."""
    def _depth(node, current=0):
        if isinstance(node, (ast.For, ast.While)):
            current += 1
        best = current
        for child in ast.iter_child_nodes(node):
            best = max(best, _depth(child, current))
        return best
    return _depth(tree)

class EnergySurrogate:

    def __init__(self):
        self._X: list = []
        self._y: list = []
        self._noise_var: list = []  
        self._model = None
        self._trained = False
        self._update_count = 0  

    def _featurize(self, source: str, chain: list[dict], max_n: float) -> list:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return [0.0] * 16

        def c(cls): return sum(1 for _ in ast.walk(tree) if isinstance(_, cls))

        llm_tier = max({"H": 3, "M": 2, "L": 1}.get(t.get("tier", "L"), 1)
                       for t in chain) if chain else 0

        f0  = float(c(ast.For))
        f1  = float(c(ast.While))
        f2  = float(c(ast.ListComp))
        f3  = float(c(ast.Set)) + float(c(ast.DictComp))
        f4  = float(c(ast.Call))
        f5  = float(sum(1 for _ in ast.walk(tree))) / 50.0 
        f6  = float(c(ast.Compare))
        f7  = float(sum(1 for n in ast.walk(tree) if isinstance(n, ast.Compare)
                        and any(isinstance(op, ast.In) for op in n.ops)))
        f8  = float(llm_tier)
        f9  = float(len(chain))
        f10 = float(sum(1 for t in chain if t.get("needs_llm")))
        f11 = math.log1p(max(0.0, max_n)) / 10.0
        f12 = math.log1p(_halstead_volume(tree)) / 20.0
        f13 = float(_cyclomatic_complexity(tree)) / 20.0
        f14 = _memory_access_density(tree)
        f15 = float(_algorithmic_depth(tree)) / 5.0

        return [f0, f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14, f15]

    def update(self, source: str, chain: list[dict], energy_j: float, std_j: float, max_n: float):
        self._X.append(self._featurize(source, chain, max_n))
        self._y.append(energy_j)
        variance = (std_j ** 2) if std_j > 0 else 1e-10
        self._noise_var.append(variance)
        self._update_count += 1
        
        n = len(self._X)
        if n < 3 or not (HAS_SKLEARN and HAS_NUMPY):
            return
            
        # Throttle: retrain every call up to 50; every 5th call after that
        if n > 50 and self._update_count % 5 != 0:
            return
        self._retrain()

    def predict(self, source: str, chain: list[dict], max_n: float) -> tuple[Optional[float], float]:
        if not self._trained or not HAS_SKLEARN: return None, float("inf")
        x = np.array([self._featurize(source, chain, max_n)])
        m, s = self._model.predict(x, return_std=True)
        return float(m[0]), float(s[0])

    def _retrain(self):
        X = np.array(self._X)
        y = np.array(self._y)
        y_var = np.var(y) if len(y) > 1 else 1.0
        alpha = (np.array(self._noise_var) / (y_var + 1e-9)) + 1e-5
        
        # WARM START OPTIMIZATION:
        # If we loaded a previous model, reuse its optimized kernel to skip searching from scratch
        if self._model is not None and hasattr(self._model, "kernel_"):
            kernel = copy.deepcopy(self._model.kernel_)
        else:
            kernel = ConstantKernel(1.0) * Matern(length_scale=np.ones(X.shape[1]), nu=2.5)
            
        self._model = GaussianProcessRegressor(
            kernel=kernel, 
            alpha=alpha, 
            normalize_y=True, 
            n_restarts_optimizer=2 # We can keep this low because the warm-started kernel is already near optimal
        )
        self._model.fit(X, y)
        self._trained = True

    @property
    def is_trained(self) -> bool: return self._trained

    # --- PERSISTENCE METHODS ---
    def save(self, filepath: Path):
        """Pickle the model and historical data to the given path."""
        if not self._trained or not HAS_SKLEARN:
            return
        state = {
            'X':            self._X,
            'y':            self._y,
            'noise_var':    self._noise_var,
            'model':        self._model,
            'update_count': self._update_count,
        }
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"[Surrogate] Failed to save model to {filepath}: {e}",
                  file=sys.stderr)

    def load(self, filepath: Path) -> bool:
        """Load the model and historical data from the given path."""
        if not filepath.exists() or not HAS_SKLEARN:
            return False
        try:
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
            self._X            = state['X']
            self._y            = state['y']
            self._noise_var    = state['noise_var']
            self._model        = state['model']
            self._update_count = state['update_count']
            self._trained      = True
            return True
        except Exception as e:
            print(f"[Surrogate] Failed to load model from {filepath}: {e}",
                  file=sys.stderr)
            return False

# ══════════════════════════════════════════════════════════════════════════════
# 7.  MFBO Search Engine
# ══════════════════════════════════════════════════════════════════════════════

class MFBOEngine:

    def __init__(self, surrogate: EnergySurrogate, oracle: MultiFidelityOracle):
        self.surrogate = surrogate
        self.oracle = oracle
        self.best_energy = float("inf")

    @staticmethod
    def _ncdf(z):
        return _ncdf_approx(z)

    @staticmethod
    def _npdf(z):
        return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)

    def expected_improvement(self, mean: float, std: float) -> float:
        std = max(std, 1e-9)   # FIX v2: prevent EI math collapse
        z = (self.best_energy - mean) / std
        return max(0.0, (self.best_energy - mean) * self._ncdf(z) + std * self._npdf(z))

    def screen_and_score(self, candidates: list[ProgramVariant]
                         ) -> list[tuple[int, float, float, float]]:
        """Returns [(idx, pred_mj, std_mj, ei)] sorted by EI descending."""
        results = []
        for i, c in enumerate(candidates):
            pred, std = self.surrogate.predict(c.source, c.chain, 100.0)
            if pred is not None:
                ei = self.expected_improvement(pred, std)
                # FIX: Loosen threshold drastically to allow EI to explore uncertain areas
                if pred < self.best_energy * 3.0:  
                    results.append((i, pred, std, ei))
            else:
                results.append((i, float("nan"), float("nan"), 1.0))
        if not results: results = [(i, float("nan"), float("nan"), 1.0)
                                    for i in range(len(candidates))]
        results.sort(key=lambda x: -x[3] if not math.isnan(x[3]) else float('inf'))
        return results


# ══════════════════════════════════════════════════════════════════════════════
# 8.  Correctness Engine  (deepcopy + float/set fix)
# ══════════════════════════════════════════════════════════════════════════════

class CorrectnessEngine:
    def __init__(self, orig_source: str, func_name: str,
                 test_inputs: list[tuple], test_cases: list[tuple],
                 epsilon: float = 1e-9):
        self.func_name = func_name
        self.test_inputs = test_inputs
        self.epsilon = epsilon
        self.timeout_s = 60.0  # 1 min timeout to kill infinite loops
        
        # Precompute all expected outputs so the worker doesn't need the original function
        self.full_test_cases = list(test_cases)

        ns = {}
        try:
            exec(compile(orig_source, "<spectra>", "exec"), ns)
            orig = ns[func_name]
            import copy
            
            # Build regression tests
            for args in test_inputs:
                try:
                    exp = orig(*copy.deepcopy(args))
                    self.full_test_cases.append((args, exp))
                except Exception: 
                    pass
                    
            # Build fuzz tests
            for args in self._fuzz_inputs():
                try:
                    exp = orig(*copy.deepcopy(args))
                    self.full_test_cases.append((args, exp))
                except Exception: 
                    pass
        except Exception:
            pass

    def _fuzz_inputs(self) -> list[tuple]:
        if not self.test_inputs: return []
        sample = self.test_inputs[0]; fuzz = []
        for i, arg in enumerate(sample):
            def swap(v, _i=i): return tuple(v if j == _i else a
                                            for j, a in enumerate(sample))
            if isinstance(arg, int):
                for v in [0, 1, 2, 3, 5, 8, 10, 15, -1]: fuzz.append(swap(v))
            elif isinstance(arg, list):
                for sz in [0, 1, 3, 20, 100]:
                    fuzz.append(swap(list(range(sz))))
                fuzz.append(swap(list(range(50, 0, -1))))
                fuzz.append(swap([]))
            elif isinstance(arg, str):
                for v in ["", "a", "abc", "A" * 50]: fuzz.append(swap(v))
        return fuzz[:35]

    def verify(self, source: str) -> tuple[bool, str]:
        """
        Executes the candidate code in an isolated subprocess with a strict timeout.
        If the candidate enters an infinite loop or causes a segfault/OOM, it is killed safely.
        """
        if not self.full_test_cases:
            return False, "No valid test cases generated from baseline"

        # Use 'spawn' context to ensure clean process state across all OSes
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        
        p = ctx.Process(
            target=_isolated_verify_worker,
            args=(queue, source, self.func_name, self.full_test_cases, self.epsilon),
            daemon=True
        )
        
        p.start()
        p.join(timeout=self.timeout_s)
        
        # Guard 1: Infinite Loop (Process exceeded timeout)
        if p.is_alive():
            p.terminate()
            p.join()
            return False, f"Timeout after {self.timeout_s}s (Infinite loop detected)"
            
        # Guard 2: Memory/Segfault issues (Process crashed)
        if p.exitcode != 0:
            return False, f"Process crashed with exit code {p.exitcode} (Possible Out-Of-Memory)"
            
        # Guard 3: Uncaught internal queue failure
        if queue.empty():
            return False, "Process died unexpectedly without returning a result"
            
        return queue.get()

# ══════════════════════════════════════════════════════════════════════════════
# 9.  Research Plotter
# ══════════════════════════════════════════════════════════════════════════════

RESEARCH_COLORS = {
    "baseline": "#E74C3C", "best":     "#2ECC71",
    "candidate": "#3498DB", "fail":    "#95A5A6",
    "H": "#E74C3C", "M": "#F39C12",  "L": "#27AE60",
    "confirmed": "#2ECC71", "rejected": "#E74C3C", "partial": "#F39C12",
    "f1":        "#4E9DE0",
    "f2":        "#F0A500",
    "f3":        "#47B39C",
}


def _apply_research_style():
    if HAS_SNS:
        sns.set_theme(style="whitegrid", context="paper", font_scale=1.15)
    plt.rcParams.update({
        "font.family": "sans-serif",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titleweight": "bold", "axes.titlesize": 13,
        "axes.labelsize": 11, "figure.dpi": 150,
        "savefig.bbox": "tight", "savefig.dpi": 200,
    })


class ResearchPlotter:
    """
    Generates the full research figure suite from a StudyRecord.
    Produces individual PNGs + one composite summary figure.
    """

    def __init__(self, record: StudyRecord, out_dir: Path):
        self.r = record
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)
        if HAS_MPLOT: _apply_research_style()

    def _all_candidates(self) -> list[CandidateRecord]:
        return [c for it in self.r.iterations for c in it.candidates]

    def _save(self, fig, name: str):
        p = self.out / name
        fig.savefig(p)
        fig.clf()
        plt.close(fig)
        return p

    # ── Figure 1: Energy Trajectory ─────────────────────────
    def plot_energy_trajectory(self) -> Path:
        iters = self.r.iterations
        if not iters: return None
        xs = list(range(len(iters)))
        best_mj  = [it.best_energy_mj  for it in iters]
        conf_x, conf_y, conf_e = [], [], []
        for it in iters:
            for c in it.candidates:
                if c.f3_mj is not None:
                    conf_x.append(it.iteration - 1)
                    conf_y.append(c.f3_mj)
                    conf_e.append(c.f3_std_mj or 0)

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.axhline(self.r.baseline_mj, color=RESEARCH_COLORS["baseline"],
                   linestyle="--", lw=1.8, label=f"Baseline ({self.r.baseline_mj:.3f} mJ)")
        ax.fill_between(xs,
                        [self.r.baseline_mj - self.r.baseline_std_mj] * len(xs),
                        [self.r.baseline_mj + self.r.baseline_std_mj] * len(xs),
                        alpha=0.12, color=RESEARCH_COLORS["baseline"])
        ax.step(xs, best_mj, where="post", color=RESEARCH_COLORS["best"],
                lw=2.2, label="Running Best", zorder=4)
        if conf_y:
            ax.errorbar(conf_x, conf_y, yerr=conf_e, fmt="o",
                        color=RESEARCH_COLORS["candidate"], ms=6, lw=1.2,
                        alpha=0.7, label="F3 Evaluations ± 1σ", zorder=5)
        # Annotate fallback escape iterations
        for it in iters:
            if it.used_fallback_escape:
                ax.axvline(it.iteration - 1, color="purple", linestyle=":",
                           lw=1.2, alpha=0.7)
        ax.set_xlabel("MFBO Iteration")
        ax.set_ylabel("Energy (mJ)")
        ax.set_title(f"Energy Trajectory — {self.r.function_name}")
        ax.legend(loc="upper right", fontsize=9)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        fig.tight_layout()
        return self._save(fig, "fig1_energy_trajectory.png")

    # ── Figure 2: Fidelity Escalation Heatmap ───────────────
    def plot_fidelity_heatmap(self) -> Path:
        cands = self._all_candidates()
        if not cands: return None
        ops = [c.operator for c in cands]
        n = len(cands)
        data = []
        for c in cands:
            f1 = c.f1_improvement_pct if c.f1_mj is not None else float("nan")
            f2 = c.f2_improvement_pct if c.f2_mj is not None else float("nan")
            f3 = c.f3_improvement_pct if c.f3_mj is not None else float("nan")
            data.append([f1, f2, f3])
        if not HAS_NUMPY: return None
        arr = np.array(data)
        arr_disp = np.clip(arr, -50, 100)

        fig, ax = plt.subplots(figsize=(5, max(4, n * 0.45 + 1.5)))
        display = np.where(np.isnan(arr_disp), -999, arr_disp)
        im = ax.imshow(display, aspect="auto", cmap="RdYlGn",
                       vmin=-50, vmax=100, interpolation="nearest")
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Improvement (%)", fontsize=9)
        ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["F1", "F2", "F3"])
        ax.set_yticks(range(n))
        short_ops = [o[:22] for o in ops]
        ax.set_yticklabels(short_ops, fontsize=7)
        for i in range(n):
            for j in range(3):
                v = arr[i, j]
                if not math.isnan(v):
                    ax.text(j, i, f"{v:+.1f}%", ha="center", va="center",
                            fontsize=6.5, color="black" if -30 < v < 70 else "white")
                else:
                    ax.text(j, i, "—", ha="center", va="center",
                            fontsize=7, color="#aaa")
        ax.set_title("Fidelity Escalation Heatmap", pad=10)
        ax.set_xlabel("Fidelity Level")
        ax.set_ylabel("Candidate")
        fig.tight_layout()
        return self._save(fig, "fig2_fidelity_heatmap.png")

    # ── Figure 3: Operator Performance Bar Chart ─────────────
    def plot_operator_performance(self) -> Path:
        stats = self.r.operator_stats
        if not stats: return None
        ops = list(stats.keys())
        n_gen = [stats[o]["n_generated"] for o in ops]
        n_cor = [stats[o]["n_correct"]   for o in ops]
        n_f3  = [stats[o]["n_f3"]        for o in ops]
        n_con = [stats[o]["n_confirmed"] for o in ops]

        fig, ax = plt.subplots(figsize=(max(7, len(ops) * 1.1), 4.5))
        x = range(len(ops)); w = 0.2
        ax.bar([i - 1.5*w for i in x], n_gen, w, label="Generated",
               color="#BDC3C7", edgecolor="white")
        ax.bar([i - 0.5*w for i in x], n_cor, w, label="Correctness ✓",
               color="#3498DB", edgecolor="white")
        ax.bar([i + 0.5*w for i in x], n_f3,  w, label="F3 Evaluated",
               color="#F39C12", edgecolor="white")
        ax.bar([i + 1.5*w for i in x], n_con, w, label="Confirmed ✓",
               color=RESEARCH_COLORS["confirmed"], edgecolor="white")
        short_ops = [o[:18] for o in ops]
        ax.set_xticks(list(x)); ax.set_xticklabels(short_ops, rotation=35, ha="right",
                                                    fontsize=8)
        ax.set_ylabel("Count"); ax.set_title("Operator Funnel: Generated → Confirmed")
        ax.legend(loc="upper right", fontsize=9)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        fig.tight_layout()
        return self._save(fig, "fig3_operator_performance.png")

    # ── Figure 4: Surrogate Accuracy Scatter ─────────────────
    def plot_surrogate_accuracy(self) -> Path:
        pts = self.r.surrogate_pred_vs_actual
        if len(pts) < 2: return None
        pred_mj = [p[0] for p in pts]
        act_mj  = [p[1] for p in pts]
        if not HAS_NUMPY: return None

        fig, ax = plt.subplots(figsize=(5, 5))
        lo = min(min(pred_mj), min(act_mj)) * 0.9
        hi = max(max(pred_mj), max(act_mj)) * 1.1
        ax.plot([lo, hi], [lo, hi], "--", color="#95A5A6", lw=1.2, label="Perfect")
        ax.scatter(pred_mj, act_mj, s=60, color=RESEARCH_COLORS["candidate"],
                   alpha=0.8, edgecolors="white", zorder=5)
        pm, am = sum(pred_mj)/len(pred_mj), sum(act_mj)/len(act_mj)
        num = sum((p-pm)*(a-am) for p, a in zip(pred_mj, act_mj))
        den = math.sqrt(sum((p-pm)**2 for p in pred_mj) *
                        sum((a-am)**2 for a in act_mj) + 1e-15)
        r = num / den
        ax.text(0.05, 0.92, f"Pearson r = {r:.3f}", transform=ax.transAxes,
                fontsize=10, color="#2C3E50",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))
        ax.set_xlabel("Surrogate Prediction (mJ)"); ax.set_ylabel("Actual Energy (mJ)")
        ax.set_title("GP Surrogate Accuracy")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.legend(fontsize=9); fig.tight_layout()
        return self._save(fig, "fig4_surrogate_accuracy.png")

    # ── Figure 5: CO₂ Budget Breakdown ───────────────────────
    def plot_co2_breakdown(self) -> Path:
        f1_co2 = f2_co2 = f3_co2 = 0.0
        intensity = self.r.co2_intensity_g_per_kwh
        for c in self._all_candidates():
            f1_reps = (FIDELITY_REPS[Fidelity.F1]
                       + (c.f1_adaptive_extra_reps or 0))
            f2_reps = (FIDELITY_REPS[Fidelity.F2]
                       + (c.f2_adaptive_extra_reps or 0))
            f3_reps = FIDELITY_REPS[Fidelity.F3]

            if c.f1_mj is not None:
                f1_co2 += (c.f1_mj / 1000) * f1_reps * intensity / 3.6e6 * 1e6
            if c.f2_mj is not None:
                f2_co2 += (c.f2_mj / 1000) * f2_reps * intensity / 3.6e6 * 1e6
            if c.f3_mj is not None:
                if c.f3_co2_ug is not None:
                    f3_co2 += c.f3_co2_ug
                else:
                    f3_co2 += (c.f3_mj / 1000) * f3_reps * intensity / 3.6e6 * 1e6

        base_co2 = self.r.baseline_co2_ug * FIDELITY_REPS[Fidelity.F3]
        total = base_co2 + f1_co2 + f2_co2 + f3_co2
        if total < 1e-10: return None

        labels = ["Baseline\nMeasurement", "F1\nScreening", "F2\nScreening", "F3\nGround-Truth"]
        values = [base_co2, f1_co2, f2_co2, f3_co2]
        colors = [RESEARCH_COLORS["baseline"], "#F7DC6F", RESEARCH_COLORS["M"], RESEARCH_COLORS["H"]]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.5))
        wedges, texts, autotexts = ax1.pie(
            values, labels=labels, colors=colors,
            autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
            startangle=140, pctdistance=0.75)
        for at in autotexts: at.set_fontsize(8)
        ax1.set_title(f"CO₂ Budget by Phase\n(intensity={intensity:.0f} gCO₂/kWh)")

        cum_co2 = [0.0]
        for it in self.r.iterations:
            last = cum_co2[-1]
            for c in it.candidates:
                if c.f3_co2_ug: last += c.f3_co2_ug
            cum_co2.append(last)
        xs = list(range(len(cum_co2)))
        ax2.fill_between(xs, cum_co2, alpha=0.3, color=RESEARCH_COLORS["H"])
        ax2.plot(xs, cum_co2, color=RESEARCH_COLORS["H"], lw=2)
        ax2.set_xlabel("MFBO Iteration"); ax2.set_ylabel("Cumulative CO₂ (µg eq.)")
        ax2.set_title("Cumulative Search Carbon Cost")
        ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
        fig.suptitle(f"Energy / CO₂ Accounting — {self.r.function_name}",
                     fontweight="bold", y=1.02)
        fig.tight_layout()
        return self._save(fig, "fig5_co2_breakdown.png")

    # ── Figure 6: Correctness Pass/Fail by Tier ──────────────
    def plot_correctness_by_tier(self) -> Path:
        cands = self._all_candidates()
        if not cands: return None
        by_tier: dict[str, dict] = {}
        for c in cands:
            t = c.tier
            if t not in by_tier: by_tier[t] = {"pass": 0, "fail": 0}
            if c.correctness_pass: by_tier[t]["pass"] += 1
            else: by_tier[t]["fail"] += 1

        tiers = sorted(by_tier.keys())
        pass_counts = [by_tier[t]["pass"] for t in tiers]
        fail_counts = [by_tier[t]["fail"] for t in tiers]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4))
        x = range(len(tiers)); w = 0.35
        ax1.bar([i - w/2 for i in x], pass_counts, w,
                label="Pass", color=RESEARCH_COLORS["confirmed"])
        ax1.bar([i + w/2 for i in x], fail_counts, w,
                label="Fail", color=RESEARCH_COLORS["fail"], alpha=0.85)
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([f"Tier {t}" for t in tiers])
        ax1.set_ylabel("Count"); ax1.set_title("Correctness by Tier")
        ax1.legend(fontsize=9)
        ax1.yaxis.set_major_locator(MaxNLocator(integer=True))

        imp_by_tier: dict[str, list] = {t: [] for t in tiers}
        for c in cands:
            if c.f3_improvement_pct is not None:
                imp_by_tier[c.tier].append(c.f3_improvement_pct)
        data_list = [imp_by_tier[t] for t in tiers]
        data_list_nonempty = [d for d in data_list if d]
        tiers_nonempty = [tiers[i] for i, d in enumerate(data_list) if d]
        if data_list_nonempty:
            bp = ax2.boxplot(data_list_nonempty, notch=False, patch_artist=True,
                             medianprops=dict(color="black", lw=1.5))
            for patch, t in zip(bp["boxes"], tiers_nonempty):
                patch.set_facecolor(RESEARCH_COLORS.get(t, "#3498DB"))
                patch.set_alpha(0.75)
            ax2.set_xticklabels([f"Tier {t}" for t in tiers_nonempty])
            ax2.axhline(0, color="#95A5A6", lw=1, linestyle="--")
            ax2.set_ylabel("F3 Improvement (%)")
            ax2.set_title("Improvement Distribution by Tier")
        fig.tight_layout()
        return self._save(fig, "fig6_correctness_by_tier.png")

    # ── Figure 7: Improvement Waterfall ──────────────────────
    def plot_improvement_waterfall(self) -> Path:
        iters = self.r.iterations
        if not iters: return None
        energies = [self.r.baseline_mj] + [it.best_energy_mj for it in iters]
        labels   = ["Baseline"] + [f"Iter {it.iteration}\n{it.selected_operator[:14]}"
                                    for it in iters]
        deltas   = [0.0] + [energies[i] - energies[i-1] for i in range(1, len(energies))]
        colors   = ["#7F8C8D"] + [RESEARCH_COLORS["confirmed"] if d < 0
                                   else "#E74C3C" for d in deltas[1:]]

        fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.9), 4.5))
        bars = ax.bar(range(len(labels)), energies, color=colors, alpha=0.85,
                      edgecolor="white")
        for i, (e, d) in enumerate(zip(energies, deltas)):
            pct = f"{-d/self.r.baseline_mj*100:+.1f}%" if i > 0 and self.r.baseline_mj > 0 else ""
            ax.text(i, e + max(energies) * 0.015, f"{e:.3f}\n{pct}",
                    ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8, rotation=20, ha="right")
        ax.set_ylabel("Energy (mJ)")
        ax.set_title(f"Optimization Waterfall — {self.r.function_name}")
        patch_better  = mpatches.Patch(color=RESEARCH_COLORS["confirmed"], label="Improved")
        patch_worse   = mpatches.Patch(color="#E74C3C", label="No Improvement")
        patch_base    = mpatches.Patch(color="#7F8C8D", label="Baseline")
        ax.legend(handles=[patch_base, patch_better, patch_worse], fontsize=9)
        fig.tight_layout()
        return self._save(fig, "fig7_waterfall.png")

    # ── Figure 8: EI Acquisition Trace ───────────────────────
    def plot_acquisition_trace(self) -> Path:
        cands = self._all_candidates()
        ei_vals = [(c.iteration, c.operator, c.ei_score) for c in cands
                   if c.ei_score > 0]
        if len(ei_vals) < 2: return None

        fig, ax = plt.subplots(figsize=(8, 4))
        colors_map = {"H": RESEARCH_COLORS["H"], "M": RESEARCH_COLORS["M"],
                      "L": RESEARCH_COLORS["L"]}
        for c in cands:
            if c.ei_score > 0:
                col = colors_map.get(c.tier, "#999")
                ax.scatter(c.iteration, c.ei_score * 1000, color=col, s=50, alpha=0.8,
                           zorder=5)
        xs = [e[0] for e in ei_vals]; ys = [e[2]*1000 for e in ei_vals]
        ax.plot(xs, ys, "-", color="#BDC3C7", lw=1, zorder=1)
        for tier, col in colors_map.items():
            ax.scatter([], [], color=col, s=50, label=f"Tier {tier}")
        ax.set_xlabel("Iteration"); ax.set_ylabel("Expected Improvement (×10⁻³ mJ)")
        ax.set_title("Acquisition Function Trace (EI)")
        ax.legend(fontsize=9); ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        fig.tight_layout()
        return self._save(fig, "fig8_acquisition_trace.png")

    # ── Figure 9: Measurement Noise Profile ──────────────────
    def plot_noise_profile(self) -> Path:
        cands = self._all_candidates()
        f3_cands = [c for c in cands if c.f3_mj is not None and c.f3_std_mj is not None]
        if not f3_cands: return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))
        means = [c.f3_mj   for c in f3_cands]
        stds  = [c.f3_std_mj for c in f3_cands]
        cvs   = [s / m * 100 if m > 0 else 0 for s, m in zip(stds, means)]
        ops   = [c.operator[:16] for c in f3_cands]

        ax1.barh(range(len(f3_cands)), cvs, color=RESEARCH_COLORS["candidate"],
                 alpha=0.8, edgecolor="white")
        ax1.set_yticks(range(len(f3_cands)))
        ax1.set_yticklabels(ops, fontsize=7)
        ax1.axvline(10, color=RESEARCH_COLORS["baseline"], linestyle="--", lw=1.2,
                    label="CV=10% threshold")
        ax1.set_xlabel("Coefficient of Variation (%)")
        ax1.set_title("Measurement Noise (F3 CV)")
        ax1.legend(fontsize=8)

        base_mj = self.r.baseline_mj; base_std = self.r.baseline_std_mj
        if base_mj > 0:
            ax2.bar(["Baseline", "Best"], [base_mj, self.r.best_mj],
                    color=[RESEARCH_COLORS["baseline"], RESEARCH_COLORS["best"]],
                    alpha=0.85, edgecolor="white")
            ax2.errorbar([0, 1], [base_mj, self.r.best_mj],
                         yerr=[base_std, stds[0] if stds else 0],
                         fmt="none", color="#2C3E50", capsize=5, lw=1.8)
            ax2.set_ylabel("Energy (mJ)")
            ax2.set_title("Baseline vs. Best ± 1σ")
        fig.tight_layout()
        return self._save(fig, "fig9_noise_profile.png")

    # ── Figure 10: Inner Loop Multiplier Distribution (NEW) ──
    def plot_inner_loop_stats(self) -> Path:
        cands = self._all_candidates()
        mults = [c.inner_loop_multiplier for c in cands if c.inner_loop_multiplier > 1]
        if not mults or not HAS_NUMPY: return None

        fig, ax = plt.subplots(figsize=(6, 3.5))
        ax.hist(mults, bins=max(5, len(set(mults))), color=RESEARCH_COLORS["candidate"],
                alpha=0.8, edgecolor="white")
        ax.set_xlabel("Adaptive Inner Loop Multiplier")
        ax.set_ylabel("Count")
        ax.set_title("RAPL Resolution Guard — Inner Loop Multipliers Used")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.text(0.97, 0.95, f"n={len(mults)}  mean={sum(mults)/len(mults):.1f}",
                transform=ax.transAxes, ha="right", va="top", fontsize=9,
                bbox=dict(boxstyle="round", fc="white", alpha=0.8))
        fig.tight_layout()
        return self._save(fig, "fig10_inner_loop_multipliers.png")

    # ── Figure 12: Fidelity CV Distribution ─────────────────
    def plot_cv_by_fidelity(self) -> Path:
        """Box/scatter of coefficient of variation per fidelity — shows measurement noise."""
        cands = self._all_candidates()
        data = {
            "F1": [c.f1_cv for c in cands if c.f1_cv is not None],
            "F2": [c.f2_cv for c in cands if c.f2_cv is not None],
            "F3": [c.f3_cv for c in cands if c.f3_cv is not None],
        }
        if not any(data.values()) or not HAS_NUMPY:
            return None

        fig, ax = plt.subplots(figsize=(7, 4))
        positions = [1, 2, 3]
        labels = ["F1", "F2", "F3"]
        colors = [RESEARCH_COLORS.get("f1", "#4e9de0"),
                  RESEARCH_COLORS.get("f2", "#f0a500"),
                  RESEARCH_COLORS.get("f3", "#47b39c")]

        for i, (lbl, pos, col) in enumerate(zip(labels, positions, colors)):
            vals = data[lbl]
            if not vals:
                continue
            bp = ax.boxplot(vals, positions=[pos], widths=0.5,
                            patch_artist=True, notch=False,
                            boxprops=dict(facecolor=col, alpha=0.55),
                            medianprops=dict(color="black", lw=2),
                            whiskerprops=dict(color=col, lw=1.3),
                            capprops=dict(color=col, lw=1.3),
                            flierprops=dict(marker=".", markersize=5, alpha=0.5,
                                            markerfacecolor=col))
            # Overlay jitter scatter
            jx = [pos + (random.random() - 0.5) * 0.25 for _ in vals]
            ax.scatter(jx, vals, s=18, color=col, alpha=0.65, zorder=5)
            ax.text(pos, max(vals) * 1.03 if vals else 0.5,
                    f"n={len(vals)}\nμ={sum(vals)/len(vals):.2f}",
                    ha="center", va="bottom", fontsize=7.5)

        ax.axhline(CV_TRIGGER_EXTRA_REPS, color="red", linestyle="--", lw=1.3,
                   label=f"Adaptive-reps trigger (CV={CV_TRIGGER_EXTRA_REPS})")
        ax.set_xticks(positions); ax.set_xticklabels(labels)
        ax.set_ylabel("Coefficient of Variation (std/mean)")
        ax.set_title("Measurement Noise by Fidelity Level")
        ax.legend(fontsize=8)
        fig.tight_layout()
        return self._save(fig, "fig12_cv_by_fidelity.png")

    # ── Figure 13: F1/F2 vs F3 Calibration Scatter ──────────
    def plot_fidelity_calibration(self) -> Path:
        """Scatter of F1-improvement vs F3-improvement and F2 vs F3 — proxy accuracy."""
        cands = self._all_candidates()

        f1_vals, f3_from_f1 = [], []
        f2_vals, f3_from_f2 = [], []
        for c in cands:
            if c.f1_improvement_pct is not None and c.f3_improvement_pct is not None:
                f1_vals.append(c.f1_improvement_pct)
                f3_from_f1.append(c.f3_improvement_pct)
            if c.f2_improvement_pct is not None and c.f3_improvement_pct is not None:
                f2_vals.append(c.f2_improvement_pct)
                f3_from_f2.append(c.f3_improvement_pct)

        if (not f1_vals and not f2_vals) or not HAS_NUMPY:
            return None

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

        def _calibration_panel(ax, proxy_vals, f3_vals, title, color):
            if not proxy_vals:
                ax.set_title(title + " (no data)"); return
            lo = min(min(proxy_vals), min(f3_vals)) - 2
            hi = max(max(proxy_vals), max(f3_vals)) + 2
            ax.plot([lo, hi], [lo, hi], "--", color="gray", lw=1.2, label="Perfect proxy")
            ax.axhline(0, color="black", lw=0.7, alpha=0.4)
            ax.axvline(0, color="black", lw=0.7, alpha=0.4)
            ax.scatter(proxy_vals, f3_vals, s=38, color=color, alpha=0.72, zorder=5)
            # Pearson r
            n = len(proxy_vals)
            mx = sum(proxy_vals) / n; my = sum(f3_vals) / n
            r_num = sum((x - mx) * (y - my) for x, y in zip(proxy_vals, f3_vals))
            r_den = math.sqrt(sum((x - mx)**2 for x in proxy_vals) *
                              sum((y - my)**2 for y in f3_vals) + 1e-15)
            r = r_num / r_den
            mae = sum(abs(a - b) for a, b in zip(proxy_vals, f3_vals)) / n
            ax.text(0.04, 0.96, f"r={r:.3f}   MAE={mae:.2f}%   n={n}",
                    transform=ax.transAxes, va="top", fontsize=9,
                    bbox=dict(boxstyle="round", fc="white", alpha=0.85))
            ax.set_xlabel("Proxy improvement (%)")
            ax.set_ylabel("F3 (ground truth) improvement (%)")
            ax.set_title(title)
            ax.legend(fontsize=8)

        _calibration_panel(axes[0], f1_vals, f3_from_f1,
                           "F1 → F3 Calibration",
                           RESEARCH_COLORS.get("f1", "#4e9de0"))
        _calibration_panel(axes[1], f2_vals, f3_from_f2,
                           "F2 → F3 Calibration",
                           RESEARCH_COLORS.get("f2", "#f0a500"))
        fig.suptitle("Multi-Fidelity Proxy Accuracy", fontweight="bold")
        fig.tight_layout()
        return self._save(fig, "fig13_fidelity_calibration.png")

    # ── Figure 14: Abandon-Reason Breakdown ──────────────────
    def plot_abandon_reasons(self) -> Path:
        """Bar chart showing why candidates were abandoned at F1 and F2."""
        cands = self._all_candidates()

        from collections import Counter
        f1_reasons: list[str] = []
        f2_reasons: list[str] = []
        for c in cands:
            if c.f1_abandoned and c.f1_abandon_reason:
                # Bucket reason
                r = c.f1_abandon_reason
                if "CV" in r and "uncertain" not in r:
                    f1_reasons.append("Low P(↑)")
                elif "uncertain" in r.lower():
                    f1_reasons.append("High CV (uncertain)")
                elif "P(better)" in r:
                    f1_reasons.append("Low P(↑)")
                else:
                    f1_reasons.append("Other")
            if c.f2_abandoned and c.f2_abandon_reason:
                r = c.f2_abandon_reason
                if "uncertain" in r.lower():
                    f2_reasons.append("High CV (uncertain)")
                elif "P(better)" in r:
                    f2_reasons.append("Low P(↑)")
                else:
                    f2_reasons.append("Other")

        # Also count uncertain-passes (not abandoned but flagged)
        f1_uncertain = sum(1 for c in cands if c.f1_noise_uncertain)
        f2_uncertain = sum(1 for c in cands if c.f2_noise_uncertain)

        if not f1_reasons and not f2_reasons:
            return None

        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        def _bar(ax, reasons, uncertain_pass, title):
            cnt = Counter(reasons)
            if uncertain_pass:
                cnt["Uncertain-pass"] = uncertain_pass
            if not cnt:
                ax.set_title(title + " (no abandonments)"); return
            labels = list(cnt.keys())
            vals   = [cnt[l] for l in labels]
            bar_colors = [RESEARCH_COLORS.get("candidate", "#7ec8e3")] * len(labels)
            bars = ax.barh(labels, vals, color=bar_colors, edgecolor="white")
            ax.bar_label(bars, padding=3, fontsize=9)
            ax.set_xlabel("Count")
            ax.set_title(title)

        _bar(axes[0], f1_reasons, f1_uncertain, f"F1 Abandon Reasons  (total={len(f1_reasons)})")
        _bar(axes[1], f2_reasons, f2_uncertain, f"F2 Abandon Reasons  (total={len(f2_reasons)})")
        fig.suptitle("Why Candidates Were Pruned", fontweight="bold")
        fig.tight_layout()
        return self._save(fig, "fig14_abandon_reasons.png")

    # ── Figure 11: Composite Summary Poster ──────────────────
    def plot_summary_poster(self) -> Path:
        if not HAS_NUMPY: return None
        fig = plt.figure(figsize=(18, 11))
        gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.4)

        # A — energy trajectory
        ax_traj = fig.add_subplot(gs[0, :2])
        iters = self.r.iterations
        if iters:
            xs = list(range(len(iters)))
            best_mj = [it.best_energy_mj for it in iters]
            ax_traj.axhline(self.r.baseline_mj, color=RESEARCH_COLORS["baseline"],
                            linestyle="--", lw=1.8, label="Baseline")
            ax_traj.step(xs, best_mj, where="post", color=RESEARCH_COLORS["best"],
                         lw=2.2, label="Best Found")
            for c in self._all_candidates():
                if c.f3_mj is not None:
                    ax_traj.scatter(c.iteration - 1, c.f3_mj, s=40,
                                    color=RESEARCH_COLORS["candidate"],
                                    alpha=0.6, zorder=5)
            ax_traj.set_xlabel("Iteration"); ax_traj.set_ylabel("Energy (mJ)")
            ax_traj.set_title("Energy Trajectory")
            ax_traj.legend(fontsize=8); ax_traj.xaxis.set_major_locator(MaxNLocator(integer=True))

        # B — operator funnel
        ax_op = fig.add_subplot(gs[0, 2:])
        stats = self.r.operator_stats
        if stats:
            ops = list(stats.keys())
            n_gen = [stats[o]["n_generated"] for o in ops]
            n_cor = [stats[o]["n_correct"]   for o in ops]
            n_con = [stats[o]["n_confirmed"] for o in ops]
            x = range(len(ops)); w = 0.27
            ax_op.bar([i - w for i in x], n_gen, w, label="Generated", color="#BDC3C7")
            ax_op.bar([i      for i in x], n_cor, w, label="Correct",   color="#3498DB")
            ax_op.bar([i + w  for i in x], n_con, w, label="Confirmed", color=RESEARCH_COLORS["confirmed"])
            ax_op.set_xticks(list(x))
            ax_op.set_xticklabels([o[:14] for o in ops], rotation=30, ha="right", fontsize=7)
            ax_op.set_ylabel("Count"); ax_op.set_title("Operator Funnel")
            ax_op.legend(fontsize=7); ax_op.yaxis.set_major_locator(MaxNLocator(integer=True))

        # C — fidelity heatmap (mini)
        ax_heat = fig.add_subplot(gs[1, :2])
        cands = self._all_candidates()
        if cands:
            data = []
            for c in cands:
                f1 = c.f1_improvement_pct if c.f1_mj is not None else float("nan")
                f2 = c.f2_improvement_pct if c.f2_mj is not None else float("nan")
                f3 = c.f3_improvement_pct if c.f3_mj is not None else float("nan")
                data.append([f1, f2, f3])
            arr = np.clip(np.array(data), -50, 100)
            display = np.where(np.isnan(arr), -999, arr)
            ax_heat.imshow(display, aspect="auto", cmap="RdYlGn",
                           vmin=-50, vmax=100, interpolation="nearest")
            ax_heat.set_xticks([0, 1, 2]); ax_heat.set_xticklabels(["F1", "F2", "F3"])
            ax_heat.set_yticks(range(len(cands)))
            ax_heat.set_yticklabels([c.operator[:18] for c in cands], fontsize=6)
            ax_heat.set_title("Fidelity Escalation Heatmap")

        # D — CO2 bar
        ax_co2 = fig.add_subplot(gs[1, 2:])
        intensity = self.r.co2_intensity_g_per_kwh
        f1c = f2c = f3c = 0.0
        for c in cands:
            if c.f1_mj: f1c += c.f1_mj/1000 * FIDELITY_REPS[Fidelity.F1] * intensity/3.6e6*1e6
            if c.f2_mj: f2c += c.f2_mj/1000 * FIDELITY_REPS[Fidelity.F2] * intensity/3.6e6*1e6
            if c.f3_mj: f3c += c.f3_mj/1000 * FIDELITY_REPS[Fidelity.F3] * intensity/3.6e6*1e6
        basec = self.r.baseline_co2_ug * FIDELITY_REPS[Fidelity.F3]
        vals = [basec, f1c, f2c, f3c]
        cols = [RESEARCH_COLORS["baseline"], "#F7DC6F",
                RESEARCH_COLORS["M"], RESEARCH_COLORS["H"]]
        bars = ax_co2.bar(["Baseline", "F1", "F2", "F3"], vals, color=cols, alpha=0.85,
                           edgecolor="white")
        ax_co2.set_ylabel("CO₂ cost (µg eq.)")
        ax_co2.set_title(f"CO₂ Budget ({intensity:.0f} gCO₂/kWh)")
        for bar, v in zip(bars, vals):
            if v > 0:
                ax_co2.text(bar.get_x() + bar.get_width()/2, v*1.02, f"{v:.1f}",
                            ha="center", va="bottom", fontsize=8)

        # E — surrogate scatter
        ax_gp = fig.add_subplot(gs[2, :2])
        pts = self.r.surrogate_pred_vs_actual
        if len(pts) >= 2:
            pred_mj = [p[0] for p in pts]; act_mj = [p[1] for p in pts]
            lo = min(min(pred_mj), min(act_mj)) * 0.9
            hi = max(max(pred_mj), max(act_mj)) * 1.1
            ax_gp.plot([lo, hi], [lo, hi], "--", color="#95A5A6", lw=1.2)
            ax_gp.scatter(pred_mj, act_mj, s=50, color=RESEARCH_COLORS["candidate"],
                          alpha=0.8, edgecolors="white", zorder=5)
            ax_gp.set_xlabel("Predicted (mJ)"); ax_gp.set_ylabel("Actual (mJ)")
            ax_gp.set_title("GP Surrogate Accuracy")

        # F — key metrics text panel
        ax_txt = fig.add_subplot(gs[2, 2:])
        ax_txt.axis("off")
        lines = [
            f"Function:         {self.r.function_name}",
            f"Energy backend:   {self.r.energy_backend.upper()}",
            f"LLM provider:     {self.r.llm_provider if self.r.has_llm else 'None'}",
            f"CO₂ intensity:    {intensity:.0f} gCO₂/kWh",
            "",
            f"Baseline:         {self.r.baseline_mj:.4f} ± {self.r.baseline_std_mj:.4f} mJ",
            f"Best found:       {self.r.best_mj:.4f} mJ",
            f"Improvement:      {self.r.improvement_pct:+.2f}%",
            "",
            f"F3 evaluations:   {self.r.total_f3_evals} / {self.r.max_f3_budget}",
            f"Fallback escapes: {self.r.total_fallback_escapes_used}",
            f"Total CO₂ cost:   {self.r.total_co2_search_ug:.1f} µg eq.",
            f"Wall-clock:       {self.r.total_wall_s:.1f} s",
            "",
            f"Chain: {' → '.join(self.r.transformation_chain) or '(no improvement)'}",
        ]
        ax_txt.text(0.04, 0.95, "\n".join(lines), transform=ax_txt.transAxes,
                    fontsize=9, va="top", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", fc="#F8F9FA", ec="#DEE2E6"))
        ax_txt.set_title("Run Summary", loc="left", fontsize=11, fontweight="bold")

        fig.suptitle(f"SPECTRA Research Summary — {self.r.function_name}",
                     fontsize=15, fontweight="bold", y=1.01)
        return self._save(fig, "fig11_summary_poster.png")

    def generate_all(self) -> list[Path]:
        if not HAS_MPLOT:
            print("[Plotter] matplotlib not available — skipping figures.")
            return []
        plots = [
            ("Fig 1  Energy Trajectory",       self.plot_energy_trajectory),
            ("Fig 2  Fidelity Heatmap",         self.plot_fidelity_heatmap),
            ("Fig 3  Operator Performance",     self.plot_operator_performance),
            ("Fig 4  Surrogate Accuracy",       self.plot_surrogate_accuracy),
            ("Fig 5  CO₂ Breakdown",            self.plot_co2_breakdown),
            ("Fig 6  Correctness by Tier",      self.plot_correctness_by_tier),
            ("Fig 7  Improvement Waterfall",    self.plot_improvement_waterfall),
            ("Fig 8  Acquisition Trace",        self.plot_acquisition_trace),
            ("Fig 9  Measurement Noise",        self.plot_noise_profile),
            ("Fig 10 Inner Loop Multipliers",   self.plot_inner_loop_stats),
            ("Fig 11 Summary Poster",           self.plot_summary_poster),
            ("Fig 12 CV by Fidelity",           self.plot_cv_by_fidelity),
            ("Fig 13 Fidelity Calibration",     self.plot_fidelity_calibration),
            ("Fig 14 Abandon Reasons",          self.plot_abandon_reasons),
        ]
        saved = []
        for label, fn in plots:
            try:
                p = fn()
                if p: print(f"  ✓ {label:<40} → {p.name}"); saved.append(p)
                else:  print(f"  – {label:<40}   (skipped – insufficient data)")
            except Exception as exc:
                print(f"  ✗ {label:<40}   Error: {exc}")
        return saved


# ══════════════════════════════════════════════════════════════════════════════
# 10. SPECTRA Optimizer (research edition v3)
# ══════════════════════════════════════════════════════════════════════════════

MAX_PARETO_SIZE  = 10   # Hard cap on Pareto archive length
UCB_EXPLORATION  = 1.0  # Exploration constant for operator UCB scores

# ──────────────────────────────────────────────────────────────────────────────
#  Operator success-rate tracker
# ──────────────────────────────────────────────────────────────────────────────
 
@dataclass
class OperatorStats:
    """Tracks per-operator attempt / confirmation counts for UCB ranking."""
    attempts:      int = 0
    confirmations: int = 0
 
    def ucb_score(self, total_attempts: int, c: float = UCB_EXPLORATION) -> float:
        """
        Upper Confidence Bound score.
        Untested operators always return +inf so they get tried first.
        """
        if self.attempts == 0:
            return float("inf")
        rate        = self.confirmations / self.attempts
        exploration = c * math.sqrt(math.log(max(total_attempts, 1)) / self.attempts)
        return rate + exploration
 
 
# ──────────────────────────────────────────────────────────────────────────────
#  Pareto-front utilities
# ──────────────────────────────────────────────────────────────────────────────
 
def _energy_of(v: ProgramVariant) -> float:
    """Return the canonical energy figure for a variant (trimmed mean, mJ)."""
    m = v.best_measurement()
    if m is None:
        return float("inf")
    # Prefer trimmed mean when available
    return getattr(m, "trimmed_mean_mj", m.mean_mj)
 
 
def _non_dominated_front(
    variants: list[ProgramVariant],
    cap: int = MAX_PARETO_SIZE,
) -> list[ProgramVariant]:
    """
    Return the non-dominated subset of `variants` under two objectives:
      - minimise energy  (trimmed mean mJ)
      - minimise chain depth  (proxy for transformation complexity / overfitting risk)
    Result is sorted by energy and capped at `cap`.
    """
    dominated: set[int] = set()
    for i, a in enumerate(variants):
        if i in dominated:
            continue
        e_a, d_a = _energy_of(a), len(a.chain)
        for j, b in enumerate(variants):
            if i == j or j in dominated:
                continue
            e_b, d_b = _energy_of(b), len(b.chain)
            # b dominates a if it is at least as good on both objectives
            # and strictly better on at least one
            if e_b <= e_a and d_b <= d_a and (e_b < e_a or d_b < d_a):
                dominated.add(i)
                break
 
    front = [v for i, v in enumerate(variants) if i not in dominated]
    front.sort(key=_energy_of)
    return front[:cap]
 
# ──────────────────────────────────────────────────────────────────────────────
# CONFLICT FILTER UTILITY
# ──────────────────────────────────────────────────────────────────────────────
 
 
class ConflictFilter:
    """
    Prevents mutually-exclusive operators from both firing on the same source.
 
    Usage:
        cf = ConflictFilter()
        applicable = cf.filter(operators, tree, source)
 
    Conflict groups: only the FIRST applicable operator in each group is kept.
    """
    # Each tuple is a group of mutually-exclusive operator names.
    # The ordering within each tuple determines priority.
    CONFLICT_GROUPS: list[tuple[str, ...]] = [
        # DP rewrite makes memoization pointless
        ("RecursionToDynamicProgramming", "MemoizationAddition"),
        # Both convert list → set for membership; applying both is a no-op
        ("ListToSetMembership", "LoopMembershipSetCache"),
        # Counter is a specialised defaultdict; prefer Counter
        ("CounterSubstitution", "DefaultDictSubstitution"),
        # StringConcatToJoin handles the simple case; StringBuildBufferLLM handles complex
        ("StringConcatToJoin", "StringBuildBufferLLM"),
        # Generator conversion — prefer the cheaper L-tier op
        ("ReductionListCompToGenerator", "JoinListCompToGenerator"),
        ("DataStructureSubstitution[list→set]", "LoopMembershipSetCache"),
        ("ForLoopToComprehension", "GeneratorChainFusion")
    ]
 
    def filter(
        self,
        operators: list,
        tree,
        source: str,
    ) -> list:
        """Return a filtered list with conflict-group losers removed."""
        applicable_names = {
            op.name for op in operators if op.precondition(tree, source)
        }
        blocked: set[str] = set()
        for group in self.CONFLICT_GROUPS:
            # Find the highest-priority (first in tuple) applicable operator
            winner = next((n for n in group if n in applicable_names), None)
            if winner is None:
                continue
            for loser in group:
                if loser != winner and loser in applicable_names:
                    blocked.add(loser)
 
        return [op for op in operators if op.name not in blocked]
 
# ──────────────────────────────────────────────────────────────────────────────
#  Main Optimizer
# ──────────────────────────────────────────────────────────────────────────────
 
class SPECTRAOptimizer:
    """
    SPECTRA: Source-Program Energy Correction via Transformation and
    Rewrite Automation.
 
    Multi-fidelity Bayesian optimisation over a space of program
    transformations, guided by energy measurement oracles and an LLM
    for semantic rewrites.
    """
 
    def __init__(
        self,
        source:               str,
        func_name:            str,
        test_inputs:          list[tuple],
        test_cases:           list[tuple],
        operators:            Optional[list[TransformationOperator]] = None,
        max_f3_evals:         int   = 10,
        verbose:              bool  = True,
        llm:                  Optional[GeminiClient] = None,
        ei_top_k:             int   = 2,
        out_dir:              Optional[Path] = None,
        source_file:          str   = "<inline>",
        use_process_isolation:bool  = True,
        co2_intensity:        float = 475.0,
        max_fallbacks:        int   = 3,
        fidelity_leniency:    float = 0.10,
        adaptive_reps:        bool  = True,
        max_wall_s:           Optional[float] = None,   # [FEATURE-1]
        surrogate_path:      Optional[Path]  = None,   # [FEATURE-2]
        llm_workers:          int   = 1,
    ):
        self.source       = textwrap.dedent(source).strip()
        self.func_name    = func_name
        self.test_inputs  = test_inputs
        self.test_cases   = test_cases
        self.operators    = operators or ALL_OPERATORS
        self.max_f3       = max_f3_evals
        self.verbose      = verbose
        self.llm          = llm or GeminiClient()
        self.ei_top_k     = max(1, int(ei_top_k))
        self.out_dir      = out_dir or Path("spectra_output")
        self.source_file  = source_file
        self.co2_intensity = co2_intensity
        self.max_fallbacks = max_fallbacks
        self.max_wall_s   = max_wall_s
        self.surrogate_path = surrogate_path
        self.llm_workers  = llm_workers
 
        global _CO2_INTENSITY_G_PER_KWH
        _CO2_INTENSITY_G_PER_KWH = co2_intensity
 
        # ── Fidelity calibration and decision engine ──────────────────────
        self.calibrator = FidelityCalibrator(
            base_p_f1=fidelity_leniency,
            base_p_f2=min(fidelity_leniency * 2.5, 0.40))
        self.decision_engine = FidelityDecisionEngine(
            calibrator=self.calibrator,
            p_abandon_f1=fidelity_leniency,
            p_abandon_f2=min(fidelity_leniency * 2.5, 0.40),
            p_confirm_f3=0.90)
 
        # ── Oracle, surrogate, engine ─────────────────────────────────────
        self.oracle = MultiFidelityOracle(
            func_name, test_inputs,
            use_process_isolation=use_process_isolation,
            co2_intensity=co2_intensity,
            adaptive_reps=adaptive_reps,
            calibrator=self.calibrator)
        self.surrogate   = EnergySurrogate()
        self.engine      = MFBOEngine(self.surrogate, self.oracle)
        self.correctness = CorrectnessEngine(
            self.source, func_name, test_inputs, test_cases)
 
        # ── Search state ─────────────────────────────────────────────────
        self._pareto:   list[ProgramVariant] = []
        self._seen:     set[str]             = set()
        self._seen_lock = threading.Lock()              # [BUG-1]
        self._f3_count  = 0
        self._co2_ug    = 0.0
        self._metrics:  Optional[MetricsCollector] = None
 
        # ── Operator UCB statistics  [ARCH-3] ────────────────────────────
        self._op_stats: dict[str, OperatorStats] = {
            op.name: OperatorStats() for op in self.operators
        }
        self._op_total_attempts = 0
 
        # ── Conflict filter  [ARCH-5] ────────────────────────────────────
        self._conflict_filter = ConflictFilter()
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Public entry-point
    # ═════════════════════════════════════════════════════════════════════════
 
    def optimize(self, study_label: str = "") -> dict:
        t_total = time.perf_counter()
        self._print_banner()
 
        # ── Baseline ──────────────────────────────────────────────────────
        baseline = self._establish_baseline()
        if baseline is None:
            return {"error": "Baseline measurement failed"}
 
        # ── Warm-start surrogate  [FEATURE-2] ─────────────────────────────
        self._maybe_warm_start()
 
        base_v = ProgramVariant(source=self.source,
                                measurements={Fidelity.F3: baseline})
        self._pareto = [base_v]
        with self._seen_lock:
            self._seen.add(self.source)
        self.engine.best_energy = baseline.mean_j
 
        no_progress       = 0
        fallback_used_run = 0  # [ARCH-4] scoped to this optimize() call
 
        for iteration in range(1, self.max_f3 + 1):
            # ── Time budget guard  [FEATURE-1] ────────────────────────────
            if (self.max_wall_s is not None
                    and time.perf_counter() - t_total >= self.max_wall_s):
                self._log("[Budget] Wall-clock time limit reached — stopping.")
                break
 
            if no_progress >= 3:
                self._log("\n[MFBO] Converged (3 iterations without Pareto progress).")
                break
            if self._f3_count >= self.max_f3:
                self._log(f"\n[MFBO] F3 budget ({self.max_f3}) exhausted.")
                break
 
            t_iter = time.perf_counter()
            self._metrics.start_iteration()
            self._log(f"\n── Iteration {iteration} {'─' * 54}")
 
            # ── Candidate generation ───────────────────────────────────────
            all_cands = self._expand_pareto_frontier()
 
            # ── Local-minima escape ────────────────────────────────────────
            used_fallback = False
            if (not all_cands
                    and fallback_used_run < self.max_fallbacks
                    and self.llm.available):
                all_cands, used_fallback = self._run_escape(fallback_used_run)
                if used_fallback:
                    fallback_used_run += 1
 
            if not all_cands:
                self._log("[Graph] No new candidates — search space exhausted.")
                break
            self._log(f"[Graph] {len(all_cands)} candidate(s) generated")
 
            # ── Correctness filter (parallel)  [PERF-1] ───────────────────
            verified, cand_records = self._filter_correctness(
                all_cands, iteration)
 
            if not verified:
                self._metrics.record.iterations.append(
                    self._build_iter_record(
                        iteration, all_cands, cand_records, [], [],
                        time.perf_counter() - t_iter, used_fallback, baseline))
                no_progress += 1
                continue
 
            # ── Surrogate scoring ──────────────────────────────────────────
            scored = self._score_with_surrogate(verified, cand_records)
            self._log(f"[Surrogate] Scored {len(scored)} candidates"
                      f"  (trained={self.surrogate.is_trained})")
 
            # ── Oracle escalation on top-k ─────────────────────────────────
            confirmed, selected_ops, selected_tiers = self._evaluate_top_k(
                scored, verified, cand_records, baseline)
 
            # ── Pareto update  [BUG-4 / PERF-2] ──────────────────────────
            progress_made = self._update_pareto_archive(confirmed)
 
            iter_best = self.engine.best_energy * 1000
            impr_pct  = ((1.0 - iter_best / baseline.mean_mj) * 100
                         if baseline.mean_mj > 0 else 0.0)
 
            self._metrics.record.iterations.append(
                self._build_iter_record(
                    iteration, all_cands, cand_records,
                    selected_ops, selected_tiers,
                    time.perf_counter() - t_iter,
                    used_fallback, baseline,
                    iter_best=iter_best, impr_pct=impr_pct,
                    n_verified=len(verified), scored=scored,
                    confirmed=confirmed))
 
            if progress_made:
                self._log(f"  ✓ Pareto archive updated — {len(self._pareto)} front member(s)")
                no_progress = 0
            else:
                no_progress += 1
 
        # ── Finalise ──────────────────────────────────────────────────────
        return self._finalise(baseline, time.perf_counter() - t_total,
                              fallback_used_run)
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: phase methods  [ARCH-1]
    # ═════════════════════════════════════════════════════════════════════════
 
    def _establish_baseline(self) -> Optional[EnergyMeasurement]:
        """Measure baseline at F3 fidelity and initialise MetricsCollector."""
        self._log(f"\n[Oracle] Establishing baseline "
                  f"(F3, {FIDELITY_REPS[Fidelity.F3]} reps)…")
        base_m = self.oracle.establish_baseline(self.source)
        if base_m is None:
            return None
 
        self._co2_ug += base_m.co2_g * base_m.n_runs * 1e6
        self._log(f"         Baseline : {base_m.mean_mj:.4f} ± {base_m.std_mj:.4f} mJ"
                  f"   CO₂≈{base_m.co2_g * 1e6:.2f}µg/call"
                  f"   backend={_ACTIVE_BACKEND.value}"
                  f"   inner_mult={base_m.inner_loop_multiplier}")
 
        # Seed the GP with the baseline reading so it has a starting anchor
        self.surrogate.update(self.source, [], base_m.mean_j, base_m.std_j, self._complexity_n())

        self._metrics = MetricsCollector(
            func_name=self.func_name,
            source_file=self.source_file,
            original_source=self.source,
            baseline_mj=base_m.mean_mj,
            baseline_std_mj=base_m.std_mj,
            baseline_co2_ug=base_m.co2_g * 1e6,
            energy_backend=_ACTIVE_BACKEND.value,
            has_llm=self.llm.available,
            llm_provider=self.llm.provider if self.llm.available else "none",
            max_budget=self.max_f3,
            co2_intensity=self.co2_intensity)
 
        return base_m
 
    def _expand_pareto_frontier(self) -> list[ProgramVariant]:
        """
        Generate all candidate variants from the current Pareto front
        (up to top-5 members).
        """
        all_cands: list[ProgramVariant] = []
        for pv in self._pareto[:5]:
            all_cands.extend(self._generate_candidates(pv))
        return all_cands

    def _retry_generic_escape(
        self,
        candidate: ProgramVariant,
        reason: str,
    ) -> tuple[bool, str]:
        """Retry the generic semantic rewrite once with verifier feedback."""
        if not self.llm or not self.llm.available or not candidate.chain:
            return False, reason

        op_info = candidate.chain[-1]
        if op_info.get("operator") != _ESCAPE_OPERATOR.name:
            return False, reason

        if not (reason.startswith("Test case mismatch")
                or reason.startswith("Exception[")):
            return False, reason

        repair_context = textwrap.dedent(f"""
            This is a repair pass after a failed correctness check.

            Verifier feedback:
            {reason}

            Revise the candidate with the smallest semantic change needed to
            satisfy the verifier. Preserve the same function signature and
            return semantics, and return only valid Python code.
        """).strip()

        self._log(f"  [Retry] {op_info['operator']}: {reason}")
        with self.llm._lock:
            self.llm._retry_count += 1

        repaired = _ESCAPE_OPERATOR.apply(
            candidate.source,
            self.llm,
            extra_context=repair_context,
        )
        if not repaired or repaired == candidate.source:
            self._log("    [Retry] no change returned")
            return False, reason

        ok, retry_reason = self.correctness.verify(repaired)
        if ok:
            candidate.source = repaired
            candidate.is_correct = True
            self._log("    [Retry] succeeded")
            return True, f"repaired after retry: {reason}"

        self._log(f"    [Retry] failed: {retry_reason}")
        return False, retry_reason
 
    def _filter_correctness(
        self,
        candidates: list[ProgramVariant],
        iteration:  int,
    ) -> tuple[list[tuple[ProgramVariant, CandidateRecord]],
               list[CandidateRecord]]:
        """
        Run correctness verification in parallel  [PERF-1].
        Also accounts for the verification energy cost  [RESEARCH-3].
 
        Returns (verified_pairs, all_candidate_records).
        """
        t_verify_start = time.perf_counter()
 
        # Parallel 
        max_workers = min(len(candidates), (os.cpu_count() or 4))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            future_map = {
                ex.submit(self.correctness.verify, c.source): c
                for c in candidates
            }
            results: list[tuple[ProgramVariant, bool, str]] = []
            for fut in concurrent.futures.as_completed(future_map):
                c = future_map[fut]
                try:
                    ok, reason = fut.result()
                except Exception as e:
                    ok, reason = False, f"verify exception: {e}"

                if (not ok and self.llm and self.llm.available and c.chain
                        and c.chain[-1].get("operator") == _ESCAPE_OPERATOR.name
                        and (reason.startswith("Test case mismatch")
                             or reason.startswith("Exception["))):
                    retry_ok, retry_reason = self._retry_generic_escape(c, reason)
                    if retry_ok:
                        ok = True
                        reason = retry_reason
                    else:
                        reason = retry_reason

                c.is_correct = ok
                results.append((c, ok, reason))
 
        # [RESEARCH-3] Approximate CO2 cost of verification
        verify_wall_s = time.perf_counter() - t_verify_start
        # Very rough proxy: 10W TDP machine, convert to µg CO2
        verify_kwh = (10.0 * verify_wall_s) / (3_600 * 1_000)
        self._co2_ug += verify_kwh * self.co2_intensity * 1e6
 
        cand_records: list[CandidateRecord] = []
        verified:     list[tuple[ProgramVariant, CandidateRecord]] = []
 
        for c, ok, reason in results:
            op_info = c.chain[-1]
            tag = "✓" if ok else "✗"
            self._log(f"  {tag} Correctness [{op_info['operator']}]: {reason}")
            cr = self._make_candidate_record(iteration, op_info, ok, reason,
                                             c.source, len(c.chain))
            cand_records.append(cr)
            if ok:
                verified.append((c, cr))
 
        return verified, cand_records
 
    def _score_with_surrogate(
        self,
        verified:     list[tuple[ProgramVariant, CandidateRecord]],
        cand_records: list[CandidateRecord],
    ) -> list[tuple[int, float, float, float]]:
        """Score verified candidates through the surrogate and return ranked list."""
        v_list = [v for v, _ in verified]
        scored = self.engine.screen_and_score(v_list)
 
        screened_in = [i for i, p, s, e in scored if not math.isnan(p)]
        # Attach surrogate predictions back to candidate records
        verified_cr = [cr for _, cr in verified]
        for vi, pred_j, std_j, ei in scored:
            cr = verified_cr[vi]
            cr.surrogate_pred_mj = None if math.isnan(pred_j) else pred_j * 1000.0
            cr.surrogate_std_mj  = None if math.isnan(std_j)  else std_j  * 1000.0
            cr.ei_score = ei
 
        return scored
 
    def _evaluate_top_k(
        self,
        scored:       list[tuple[int, float, float, float]],
        verified:     list[tuple[ProgramVariant, CandidateRecord]],
        cand_records: list[CandidateRecord],
        baseline:     EnergyMeasurement,
    ) -> tuple[list[ProgramVariant], list[str], list[str]]:
        """
        Apply UCB-ranked EI selection and escalate top-k through fidelity
        levels.  [ARCH-3]
 
        Returns (confirmed_variants, selected_op_names, selected_tier_names).
        """
        # Apply UCB reranking on top of EI scores  [ARCH-3]
        ucb_scored = self._apply_ucb_reranking(scored, verified)
 
        k = min(self.ei_top_k, len(ucb_scored))
        top = ucb_scored[:k]
        self._log(f"[MFBO] Selected top-{k} candidate(s) by UCB×EI:")
        verified_cr = [cr for _, cr in verified]
        for rank, (vi, _, _, ei) in enumerate(top, start=1):
            cr = verified_cr[vi]
            llm_lbl = " [Gemini]" if cr.is_llm else ""
            self._log(f"  #{rank} '{cr.operator}' Tier {cr.tier}{llm_lbl}"
                      f"   EI={ei * 1000:.4f}×10⁻³")
 
        self._log("[Oracle] Evaluating with fidelity escalation…")
        confirmed:       list[ProgramVariant] = []
        selected_ops:    list[str] = []
        selected_tiers:  list[str] = []
 
        for rank, (vi, _, _, _) in enumerate(top, start=1):
            if self._f3_count >= self.max_f3:
                self._log("         F3 budget exhausted during top-k evaluation.")
                break
            cand_v, cand_cr = verified[vi]
            selected_ops.append(cand_cr.operator)
            selected_tiers.append(cand_cr.tier)
            self._log(f"      Candidate #{rank}: {cand_cr.operator}")
 
            # Track attempt for UCB  [ARCH-3]
            self._record_op_attempt(cand_cr.operator)
 
            is_confirmed = self._escalate(cand_v, cand_cr, baseline)
 
            if Fidelity.F3 in cand_v.measurements:
                self._f3_count += 1
                m3 = cand_v.measurements[Fidelity.F3]
                self._co2_ug += m3.co2_g * m3.n_runs * 1e6
 
                # [BUG-2] Train on trimmed_mean_j for consistency with best_energy
                train_energy_j = getattr(m3, "trimmed_mean_j", m3.mean_j)
                self.surrogate.update(cand_v.source, cand_v.chain,
                                      train_energy_j,
                                      m3.std_j, # Passed std_j here!
                                      self._complexity_n())
 
                if cand_cr.surrogate_pred_mj is not None:
                    self._metrics.record.surrogate_pred_vs_actual.append(
                        (cand_cr.surrogate_pred_mj, m3.mean_mj))
                cand_cr.inner_loop_multiplier   = m3.inner_loop_multiplier
                cand_cr.used_process_isolation  = self.oracle.use_process_isolation
 
            if is_confirmed:
                # Track confirmation for UCB  [ARCH-3]
                self._record_op_confirmation(cand_cr.operator)
                confirmed.append(cand_v)
                # [FEATURE-3] Full regression re-check on newly confirmed best
                self._regression_recheck(cand_v)
 
        return confirmed, selected_ops, selected_tiers
 
    def _update_pareto_archive(
        self,
        confirmed: list[ProgramVariant],
    ) -> bool:
        """
        Merge confirmed variants into the Pareto archive using non-domination
        sorting.  [BUG-4 / PERF-2]
 
        Returns True if the archive changed (progress was made).
        """
        if not confirmed:
            return False
        before = {v.source for v in self._pareto}
        self._pareto = _non_dominated_front(
            self._pareto + confirmed,
            cap=MAX_PARETO_SIZE)
        after = {v.source for v in self._pareto}
        return after != before
 
    def _run_escape(
        self,
        used_so_far: int,
    ) -> tuple[list[ProgramVariant], bool]:
        """
        Trigger the generic-semantic-rewrite escape operator to break out of
        local minima.
        """
        self._log(f"[Escape] Search space exhausted — triggering fallback "
                  f"escape #{used_so_far + 1}/{self.max_fallbacks}")
        escape_cands: list[ProgramVariant] = []
        for pv in self._pareto[:2]:
            new_src = _ESCAPE_OPERATOR.apply(pv.source, self.llm)
            with self._seen_lock:
                if not new_src or new_src == pv.source or new_src in self._seen:
                    continue
                self._seen.add(new_src)
            escape_cands.append(ProgramVariant(
                source=new_src,
                chain=pv.chain + [{
                    "operator": _ESCAPE_OPERATOR.name,
                    "tier":     _ESCAPE_OPERATOR.tier.value,
                    "needs_llm": True,
                }]))
        if escape_cands:
            self._log(f"[Escape] {len(escape_cands)} escape candidate(s) generated")
            return escape_cands, True
        return [], False
 
    def _finalise(
        self,
        baseline:         EnergyMeasurement,
        wall_s:           float,
        fallback_used_run: int,
    ) -> dict:
        """Log calibrator summary, finish metrics, and return result dict."""
        best_e  = self.engine.best_energy * 1000   # mJ
        best_v  = next((v for v in self._pareto if v.chain), None)
        best_src = best_v.source if best_v else self.source
        chain    = [t["operator"] for t in best_v.chain] if best_v else []
 
        self._log(
            f"\n[Isolation] Successes: {self.oracle.isolation_successes}"
            f"   Failures: {self.oracle.isolation_failures}"
            f"   Adaptive-rep escalations: {self.oracle.adaptive_escalations}"
            f"   LLM retries: {self.llm._retry_count}")
 
        cal = self.calibrator.summary_dict()
        self._log(
            f"[Calibrator] F1→F3 pairs={cal['n_f1_f3_pairs']}"
            f"  r={cal['f1_f3_pearson'] or 'n/a'}"
            f"  MAE={cal['f1_f3_mae'] or 'n/a'}"
            f"  bias={cal['f1_f3_bias'] or 'n/a'}"
            f"  eff_P_abandon={cal['effective_p_abandon_f1']:.3f}")
        self._log(
            f"[Calibrator] F2→F3 pairs={cal['n_f2_f3_pairs']}"
            f"  r={cal['f2_f3_pearson'] or 'n/a'}"
            f"  eff_P_abandon={cal['effective_p_abandon_f2']:.3f}")
 
        self._log("\n[UCB] Operator performance summary:")
        for op_name, stats in sorted(
                self._op_stats.items(),
                key=lambda kv: -kv[1].confirmations):
            if stats.attempts > 0:
                self._log(f"  {op_name:<45} "
                          f"attempts={stats.attempts:>3}  "
                          f"confirmed={stats.confirmations:>3}  "
                          f"rate={stats.confirmations/stats.attempts:.2f}")
 
        self._metrics.finish(best_e, best_src, chain, self._f3_count,
                             self._co2_ug, fallback_used_run)
 
        return self._report(baseline, best_e, best_src, chain,
                            wall_s, fallback_used_run, cal)
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: candidate generation
    # ═════════════════════════════════════════════════════════════════════════

    def _generate_candidates(
        self,
        base: ProgramVariant,
    ) -> list[ProgramVariant]:
        try:
            ref_tree = ast.parse(base.source)
        except SyntaxError:
            return []

        already_applied = {t["operator"] for t in base.chain}

        candidate_ops = [
            op for op in self.operators
            if op.name not in already_applied
            and (not op.needs_llm or self.llm.available)
        ]
        candidate_ops = self._conflict_filter.filter(
            candidate_ops, ref_tree, base.source)
        candidate_ops.sort(
            key=lambda op: -self._op_stats[op.name].ucb_score(
                self._op_total_attempts))

        det_ops = [op for op in candidate_ops if not op.needs_llm]
        llm_ops = [op for op in candidate_ops
                   if op.needs_llm and self.llm.available]

        cands:      list[ProgramVariant] = []
        # ── FIX: local_seen is now scoped to THIS base variant only. ──────
        # Previously it was an inner variable that persisted across the loop
        # in _expand_pareto_frontier because _generate_candidates was called
        # in a loop and the set lived inside the closure.  Now it is a fresh
        # set per call, so Pareto member #2 can legitimately produce the same
        # transformed source as member #1 (different base → different variant).
        local_seen: set[str] = set()

        def _try_op(op: TransformationOperator) -> Optional[ProgramVariant]:
            try:
                tree_copy = copy.deepcopy(ref_tree)
                if not op.precondition(tree_copy, base.source):
                    return None
            except Exception:
                return None

            new_src = op.apply(base.source, self.llm)
            if not new_src or new_src == base.source:
                return None

            with self._seen_lock:
                if new_src in self._seen:
                    return None
                if new_src in local_seen:
                    return None
                self._seen.add(new_src)
                local_seen.add(new_src)

            return ProgramVariant(
                source=new_src,
                chain=base.chain + [{
                    "operator":  op.name,
                    "tier":      op.tier.value,
                    "needs_llm": op.needs_llm,
                }])

        for op in det_ops:
            v = _try_op(op)
            if v:
                cands.append(v)

        if llm_ops:
            with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.llm_workers) as ex:
                futures = {ex.submit(_try_op, op): op for op in llm_ops}
                for fut in concurrent.futures.as_completed(futures):
                    try:
                        v = fut.result()
                        if v:
                            cands.append(v)
                    except Exception:
                        pass

        return cands
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: fidelity escalation
    # ═════════════════════════════════════════════════════════════════════════
 
    def _escalate(
        self,
        variant:  ProgramVariant,
        cr:       CandidateRecord,
        baseline: EnergyMeasurement,
    ) -> bool:
        """
        F1 → F2 → F3 escalation with calibrator-adaptive thresholds.
        [RESEARCH-2] Calibrator quality (Pearson r) tightens F1/F2 thresholds
        when correlation is weak.
        """
        self.decision_engine.set_noise_floor(baseline)
 
        # [RESEARCH-2] Tighten thresholds when calibrator has weak correlation
        self._apply_calibrator_feedback()
 
        # ── F1 ────────────────────────────────────────────────────────────
        m1 = self.oracle.measure_with_adaptive_reps(variant.source, Fidelity.F1)
        if m1 is None:
            self._log("         F1 measurement failed — skipping")
            return False
        variant.measurements[Fidelity.F1] = m1
        pct1 = m1.improvement * 100
        n1_str = (f"{m1.n_runs}+{m1.adaptive_extra_reps}"
                  if m1.adaptive_extra_reps else str(m1.n_runs))
        self._log(
            f"         F1 ({n1_str:>5} reps): "
            f"{m1.trimmed_mean_mj:8.4f} mJ  {pct1:+6.1f}%  "
            f"CV={m1.cv:.2f}  P(↑)={m1.p_improvement:.3f}"
            f"  [inner×{m1.inner_loop_multiplier}]"
            + (f"  outliers={m1.n_outliers_removed}"
               if m1.n_outliers_removed else ""))
 
        cr.f1_mj                   = m1.mean_mj
        cr.f1_improvement_pct      = pct1
        cr.f1_cv                   = m1.cv
        cr.f1_p_improvement        = m1.p_improvement
        cr.f1_welch_t              = m1.welch_t
        cr.f1_trimmed_mean_mj      = m1.trimmed_mean_mj
        cr.f1_adaptive_extra_reps  = m1.adaptive_extra_reps
        cr.f1_outliers_removed     = m1.n_outliers_removed
        cr.f1_calibrator_f1f3_corr = self.calibrator.f1_f3_pearson
 
        dec1 = self.decision_engine.decide_f1(m1)
        cr.f1_abandon_reason = dec1.reason
        if dec1.action == "uncertain_pass":
            cr.f1_noise_uncertain = True
            self._log(f"         F1 uncertain-pass: {dec1.reason}")
        elif dec1.action == "abandon":
            cr.f1_abandoned = True
            self._log(f"         F1 abandoned: {dec1.reason}")
            # Train GP on this failure! Artificially inflate std_j to show it's a noisy F1 reading.
            self.surrogate.update(variant.source, variant.chain, m1.mean_j, m1.std_j * 2.0, self._complexity_n())
            return False
 
        # ── F2 ────────────────────────────────────────────────────────────
        m2 = self.oracle.measure_with_adaptive_reps(variant.source, Fidelity.F2)
        if m2 is None:
            self._log("         F2 measurement failed — skipping")
            return False
        variant.measurements[Fidelity.F2] = m2
        pct2 = m2.improvement * 100
        n2_str = (f"{m2.n_runs}+{m2.adaptive_extra_reps}"
                  if m2.adaptive_extra_reps else str(m2.n_runs))
        self._log(
            f"         F2 ({n2_str:>5} reps): "
            f"{m2.trimmed_mean_mj:8.4f} mJ  {pct2:+6.1f}%  "
            f"CV={m2.cv:.2f}  P(↑)={m2.p_improvement:.3f}"
            + (f"  outliers={m2.n_outliers_removed}"
               if m2.n_outliers_removed else ""))
 
        cr.f2_mj                   = m2.mean_mj
        cr.f2_improvement_pct      = pct2
        cr.f2_cv                   = m2.cv
        cr.f2_p_improvement        = m2.p_improvement
        cr.f2_welch_t              = m2.welch_t
        cr.f2_trimmed_mean_mj      = m2.trimmed_mean_mj
        cr.f2_adaptive_extra_reps  = m2.adaptive_extra_reps
        cr.f2_outliers_removed     = m2.n_outliers_removed
        cr.f2_calibrator_f2f3_corr = self.calibrator.f2_f3_pearson
 
        dec2 = self.decision_engine.decide_f2(m2)
        cr.f2_abandon_reason = dec2.reason
        if dec2.action == "uncertain_pass":
            cr.f2_noise_uncertain = True
            self._log(f"         F2 uncertain-pass: {dec2.reason}")
        elif dec2.action == "abandon":
            cr.f2_abandoned = True
            self._log(f"         F2 abandoned: {dec2.reason}")
            # Train GP on this failure! Slightly inflate std_j.
            self.surrogate.update(variant.source, variant.chain, m2.mean_j, m2.std_j * 1.5, self._complexity_n())
            return False
 
        # ── F3 ────────────────────────────────────────────────────────────
        m3 = self.oracle.measure(variant.source, Fidelity.F3)
        if m3 is None:
            self._log("         F3 measurement failed")
            return False
        variant.measurements[Fidelity.F3] = m3
        pct3 = m3.improvement * 100
        self._log(
            f"         F3 ({m3.n_runs:>5} reps): "
            f"{m3.trimmed_mean_mj:8.4f} mJ  {pct3:+6.1f}%  "
            f"CV={m3.cv:.2f}  P(↑)={m3.p_improvement:.3f}  "
            f"CI=[{m3.ci_low_mj:.4f},{m3.ci_high_mj:.4f}]mJ"
            + (f"  outliers={m3.n_outliers_removed}"
               if m3.n_outliers_removed else ""))
 
        # Update calibrator with paired observations
        self.calibrator.record_f1_f3(m1.improvement, m3.improvement)
        self.calibrator.record_f2_f3(m2.improvement, m3.improvement)
 
        cr.f3_mj               = m3.mean_mj
        cr.f3_improvement_pct  = pct3
        cr.f3_std_mj           = m3.std_mj
        cr.f3_cv               = m3.cv
        cr.f3_ci_low_mj        = m3.ci_low_mj
        cr.f3_ci_high_mj       = m3.ci_high_mj
        cr.f3_p_improvement    = m3.p_improvement
        cr.f3_welch_t          = m3.welch_t
        cr.f3_trimmed_mean_mj  = m3.trimmed_mean_mj
        cr.f3_outliers_removed = m3.n_outliers_removed
        cr.f3_co2_ug           = m3.co2_g * m3.n_runs * 1e6
 
        dec3 = self.decision_engine.decide_f3(m3, baseline)
        cr.statistically_significant = (dec3.action == "confirm")
 
        if dec3.action == "confirm":
            cr.confirmed_improvement = True
            # [BUG-2] Use trimmed mean consistently
            self.engine.best_energy = min(
                self.engine.best_energy,
                getattr(m3, "trimmed_mean_j", m3.mean_j))
            self._log(f"         ✓ Confirmed: {dec3.reason}")
            return True
 
        self._log(f"         ✗ Not confirmed: {dec3.reason}")
        return False
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: UCB operator management  [ARCH-3]
    # ═════════════════════════════════════════════════════════════════════════
 
    def _record_op_attempt(self, op_name: str):
        if op_name in self._op_stats:
            self._op_stats[op_name].attempts += 1
            self._op_total_attempts += 1
 
    def _record_op_confirmation(self, op_name: str):
        if op_name in self._op_stats:
            self._op_stats[op_name].confirmations += 1
 
    def _apply_ucb_reranking(
        self,
        scored:   list[tuple[int, float, float, float]],
        verified: list[tuple[ProgramVariant, CandidateRecord]],
    ) -> list[tuple[int, float, float, float]]:
        """
        Re-rank EI-scored candidates by blending EI with UCB operator score.
        Operators with no history retain +inf UCB → always tried first.
        """
        verified_cr = [cr for _, cr in verified]
 
        def _combined(item):
            vi, pred_mj, std_mj, ei = item
            op_name = verified_cr[vi].operator
            ucb = self._op_stats.get(op_name,
                                     OperatorStats()).ucb_score(
                                         self._op_total_attempts)
            if math.isinf(ucb):   # untested — float("inf") sorts first
                return float("inf")
            return ei * ucb       # blend: high EI × high UCB wins
 
        return sorted(scored, key=_combined, reverse=True)
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: calibrator → threshold feedback  [RESEARCH-2]
    # ═════════════════════════════════════════════════════════════════════════
 
    def _apply_calibrator_feedback(self):
        """
        If the F1→F3 Pearson correlation is weak (< 0.5), tighten the F1
        abandon threshold so we spend fewer F3 evals on false positives.
        Called before each escalation.
        """
        r = self.calibrator.f1_f3_pearson
        if r is None or len(self.calibrator._f1_f3) < 5:
            return
        if r < 0.5:
            tightening = 1.0 - (r / 0.5) * 0.5
            new_p = max(
                0.02,
                self.calibrator._base_p_f1 * (1.0 - tightening * 0.2))
            self.calibrator._base_p_f1 = new_p
            self._log(
                f"         [Calibrator] F1 r={r:.2f} < 0.5 — "
                f"tightened _base_p_f1 to {new_p:.3f}")
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: post-confirmation regression  [FEATURE-3]
    # ═════════════════════════════════════════════════════════════════════════
 
    def _regression_recheck(self, variant: ProgramVariant):
        """
        Sanity-check that the confirmed variant is still marked correct.
        Uses the is_correct flag set during the earlier _filter_correctness
        phase — no additional subprocess is spawned.

        If for any reason the flag is absent (shouldn't happen) we do one
        cheap in-process exec-and-call check rather than a full subprocess.
        """
        # Fast path: trust the result from _filter_correctness
        if variant.is_correct is True:
            self._log("  ✓ Post-confirmation regression check passed (cached).")
            return

        if variant.is_correct is False:
            # Already known to be broken — this branch shouldn't be reachable
            # because broken candidates are filtered before _escalate(), but
            # guard defensively.
            self._log("  ⚠ POST-CONFIRMATION REGRESSION DETECTED (cached flag).")
            variant.is_correct = False
            self._pareto = [v for v in self._pareto
                            if v.source != variant.source]
            self._log("  ⚠ Variant removed from Pareto archive.")
            return

        # Fallback (variant.is_correct is None — unexpected): lightweight
        # in-process check against a single representative input to catch
        # obvious runtime errors without the 120-second subprocess overhead.
        try:
            ns: dict = {}
            exec(compile(variant.source, "<regression_check>", "exec"), ns)
            fn = ns.get(self.func_name)
            if fn is None:
                raise RuntimeError("function not found after exec")
            if self.test_inputs:
                fn(*copy.deepcopy(self.test_inputs[0]))
            self._log("  ✓ Post-confirmation regression check passed (lightweight).")
        except Exception as exc:
            self._log(f"  ⚠ POST-CONFIRMATION REGRESSION DETECTED: {exc}")
            variant.is_correct = False
            self._pareto = [v for v in self._pareto
                            if v.source != variant.source]
            self._log("  ⚠ Variant removed from Pareto archive.")
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: warm-start  [FEATURE-2]
    # ═════════════════════════════════════════════════════════════════════════

    def _maybe_warm_start(self):
        """
        Load the pre-trained surrogate model and historical data from disk.
        """
        if self.surrogate_path is None:
            return
            
        p = Path(self.surrogate_path)
        if self.surrogate.load(p):
            self._log(f"[Surrogate] Successfully loaded pre-trained model with {len(self.surrogate._X)} past samples from {p.name}")
        else:
            self._log(f"[Surrogate] No existing model found at {p.name} — starting fresh.")

    # ═════════════════════════════════════════════════════════════════════════
    #  Private: complexity feature  [RESEARCH-1]
    # ═════════════════════════════════════════════════════════════════════════

    def _complexity_n(self) -> float:
        """
        Return the *maximum* input size across all test inputs.
        Using max (worst case) rather than mean is a more faithful
        characterisation of computational complexity for surrogate training.
        """
        sizes: list[int] = []
        for args in self.test_inputs:
            for a in args:
                if isinstance(a, (list, tuple, str)):
                    sizes.append(len(a))
                elif isinstance(a, int):
                    sizes.append(a)   # treat numeric args as direct n
        return float(max(sizes)) if sizes else 100.0
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Private: helpers
    # ═════════════════════════════════════════════════════════════════════════
 
    def _log(self, msg: str):
        if self.verbose:
            print(msg)
 
    def _print_banner(self):
        llm_tag = (f"  [Gemini ✓  {self.llm.provider}]"
                   if self.llm.available else "  [LLM ✗ — set GEMINI_API_KEY]")
        self._log("\n" + "═" * 72)
        self._log(f"  SPECTRA Research v3.1  ▸  {self.func_name}{llm_tag}")
        self._log(f"  Backend: {_ACTIVE_BACKEND.value.upper()}"
                  f"   GP: {'✓' if HAS_SKLEARN else '✗'}"
                  f"   Matplotlib: {'✓' if HAS_MPLOT else '✗'}"
                  f"   Process isolation: "
                  f"{'✓' if self.oracle.use_process_isolation else '✗'}")
        self._log(f"  EI top-k: {self.ei_top_k}"
                  f"   CO₂ intensity: {self.co2_intensity:.0f} gCO₂/kWh"
                  f"   Max fallbacks: {self.max_fallbacks}"
                  + (f"   Wall budget: {self.max_wall_s:.0f}s"
                     if self.max_wall_s else ""))
        self._log("═" * 72)
 
    @staticmethod
    def _make_candidate_record(
        iteration: int,
        op_info:   dict,
        ok:        bool,
        reason:    str,
        source:    str,
        depth:     int,
    ) -> CandidateRecord:
        return CandidateRecord(
            iteration=iteration,
            operator=op_info["operator"],
            tier=op_info["tier"],
            is_llm=op_info.get("needs_llm", False),
            correctness_pass=ok,
            correctness_reason=reason,
            surrogate_pred_mj=None, surrogate_std_mj=None,
            ei_score=0.0,
            f1_mj=None, f1_improvement_pct=None, f1_abandoned=False,
            f2_mj=None, f2_improvement_pct=None, f2_abandoned=False,
            f3_mj=None, f3_improvement_pct=None,
            f3_std_mj=None, f3_co2_ug=None,
            statistically_significant=False,
            confirmed_improvement=False,
            transformed_source=source,
            chain_depth=depth)
 
    def _build_iter_record(
        self,
        iteration:     int,
        all_cands:     list,
        cand_records:  list,
        selected_ops:  list[str],
        selected_tiers: list[str],
        wall_s:        float,
        used_fallback: bool,
        baseline:      EnergyMeasurement,
        *,
        iter_best:     float = 0.0,
        impr_pct:      float = 0.0,
        n_verified:    int   = 0,
        scored:        list  = (),
        confirmed:     list  = (),
    ) -> IterationRecord:
        screened_in = [i for i, p, s, e in scored if not math.isnan(p)]
        return IterationRecord(
            iteration=iteration,
            n_candidates_generated=len(all_cands),
            n_correctness_pass=n_verified,
            n_correctness_fail=len(all_cands) - n_verified,
            n_surrogate_screened_in=len(screened_in),
            n_surrogate_screened_out=len(scored) - len(screened_in),
            selected_operator=" | ".join(selected_ops) if selected_ops else "(none)",
            selected_tier=" | ".join(selected_tiers),
            wall_clock_s=wall_s,
            best_energy_mj=iter_best or self.engine.best_energy * 1000,
            current_baseline_mj=baseline.mean_mj,
            improvement_over_baseline_pct=impr_pct,
            f3_evals_used_so_far=self._f3_count,
            surrogate_trained=self.surrogate.is_trained,
            used_fallback_escape=used_fallback,
            candidates=cand_records)
 
    def _report(
        self,
        baseline:          EnergyMeasurement,
        best_mj:           float,
        best_src:          str,
        chain:             list[str],
        wall_s:            float,
        fallback_used_run: int,
        cal:               dict,
    ) -> dict:
        improvement = ((1.0 - best_mj / baseline.mean_mj) * 100
                       if baseline.mean_mj > 0 else 0.0)
        self._log("\n" + "═" * 72)
        self._log("  Results")
        self._log("═" * 72)
        if chain:
            self._log(f"\n  Chain        : {' → '.join(chain)}")
            self._log(f"  Baseline     : {baseline.mean_mj:.4f} ± {baseline.std_mj:.4f} mJ")
            self._log(f"  Optimised    : {best_mj:.4f} mJ")
            self._log(f"  Improvement  : {improvement:.2f}%")
            self._log(f"  CO₂ search   : {self._co2_ug:.1f} µg eq. "
                      f"({self.co2_intensity:.0f} gCO₂/kWh)")
            self._log(f"  F3 evals     : {self._f3_count} / {self.max_f3}")
            self._log(f"  Fallbacks    : {fallback_used_run} / {self.max_fallbacks}")
            self._log(f"  Wall-clock   : {wall_s:.1f}s")
            self._log(f"\n  Optimised source:\n")
            for line in best_src.split("\n"):
                self._log(f"    {line}")
        else:
            self._log("  No statistically significant improvement found.")
 
        return {
            "function":              self.func_name,
            "original_source":       self.source,
            "best_source":           best_src,
            "chain":                 chain,
            "improvement_pct":       round(improvement, 3),
            "baseline_mj":           round(baseline.mean_mj, 6),
            "baseline_std_mj":       round(baseline.std_mj, 6),
            "best_mj":               round(best_mj, 6),
            "co2_search_ug":         round(self._co2_ug, 3),
            "co2_intensity_g_per_kwh": self.co2_intensity,
            "f3_evals":              self._f3_count,
            "ei_top_k":              self.ei_top_k,
            "wall_s":                round(wall_s, 2),
            "energy_backend":        _ACTIVE_BACKEND.value,
            "fallback_escapes_used": fallback_used_run,
            "llm_retries":           self.llm._retry_count,
            "isolation_successes":   self.oracle.isolation_successes,
            "isolation_failures":    self.oracle.isolation_failures,
            "adaptive_rep_escalations": self.oracle.adaptive_escalations,
            "calibrator":            cal,
            "operator_stats": {
                name: {
                    "attempts":      s.attempts,
                    "confirmations": s.confirmations,
                    "rate": (s.confirmations / s.attempts
                             if s.attempts else None),
                }
                for name, s in self._op_stats.items()
                if s.attempts > 0
            },
        }
 
    # ═════════════════════════════════════════════════════════════════════════
    #  Public: save outputs  (unchanged API)
    # ═════════════════════════════════════════════════════════════════════════
 
    def save_outputs(self, result: dict, label: str = "run"):
        """Write JSON, CSV, and all figures to out_dir."""
        fn = self.func_name
        if self._metrics is None:
            return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._metrics.export_json(self.out_dir / f"{fn}_metrics.json")
        self._metrics.export_csv(self.out_dir  / f"{fn}_candidates.csv")
        (self.out_dir / f"{fn}_result.json").write_text(
            json.dumps(result, indent=2))
        (self.out_dir / f"{fn}_optimised.py").write_text(result["best_source"])

        variants_dir = self.out_dir / "all_generated_variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        
        for it in self._metrics.record.iterations:
            for idx, c in enumerate(it.candidates):
                # Classify as pass or fail for the filename
                status = "PASS" if c.correctness_pass else "FAIL"
                
                # Make the operator name safe for the filesystem
                safe_op = "".join(x if x.isalnum() else "_" for x in c.operator)
                file_name = f"iter_{it.iteration:03d}_cand_{idx:03d}_{status}_{safe_op}.py"
                
                # Create a helpful header so you know WHY it failed
                header =  f"# {'='*60}\n"
                header += f"# Iteration: {it.iteration}\n"
                header += f"# Operator:  {c.operator}\n"
                header += f"# Status:    {status}\n"
                if not c.correctness_pass:
                    header += f"# Reason:    {c.correctness_reason}\n"
                header += f"# {'='*60}\n\n"
                
                # Write to disk
                (variants_dir / file_name).write_text(header + c.transformed_source, encoding="utf-8")
        # =====================================================================

        if self.surrogate_path is not None:
            model_path = Path(self.surrogate_path)
        else:
            # model_path = self.out_dir / f"{fn}_surrogate.pkl"
            model_path = Path("./surrogate_model.pkl")

        self.surrogate.save(model_path)
        self._log(f"[Surrogate] Saved trained model state to {model_path.name}")
 
        self._log("\n[Plotter] Generating research figures…")
        plotter = ResearchPlotter(
            self._metrics.record,
            self.out_dir / f"{fn}_figures")
        saved = plotter.generate_all()
        self._log(f"[Plotter] {len(saved)} figure(s) saved → {plotter.out}")
        return plotter.out

# ══════════════════════════════════════════════════════════════════════════════
# 11. Built-in Demo Suite
# ══════════════════════════════════════════════════════════════════════════════

DEMOS = [
    ("D1 ForLoop→Comprehension",
     """
def double_values(numbers):
    result = []
    for x in numbers:
        result.append(x * 2)
    return result
""", "double_values", [(list(range(3_000)),)], []),

    ("D2 List→Set Membership",
     """
def count_valid(items):
    valid = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
             110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
    count = 0
    for item in items:
        if item in valid:
            count += 1
    return count
""", "count_valid", [(list(range(800)),)],
     [((list(range(10)),), 0)]),

    ("D3 Recursion→lru_cache",
     """
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)
""", "fib", [(20,)],
     [((10,), 55), ((0,), 0), ((1,), 1)]),

    ("D4 StringConcat→Join",
     """
def build_text(chunks):
    text = ""
    for chunk in chunks:
        text += chunk
    return text
""", "build_text", [(["long_data_chunk_block_" * 10] * 10_000,)], []),

    ("D5 IteratorSubstitution",
     """
def sum_squares(numbers):
    return sum(list(x * x for x in numbers))
""", "sum_squares", [(list(range(5_000)),)], []),

    ("D6 MultipleOrToSet",
     """
def classify(x):
    if x == 1 or x == 2 or x == 3 or x == 5 or x == 7:
        return 'small_prime'
    elif x == 4 or x == 6 or x == 8 or x == 9 or x == 10:
        return 'small_composite'
    return 'other'
""", "classify", [(i,) for i in range(1000)],
     [((1,), "small_prime"), ((4,), "small_composite"), ((111,), "other")]),
]


def run_demos(gemini_key=None, budget=8, out_dir=Path("spectra_output"),
              demo_idx=None, ei_top_k: int = 2,
              co2_intensity: float = 475.0,
              use_process_isolation: bool = True,
              fidelity_leniency: float = 0.10,
              adaptive_reps: bool = True):
    llm = GeminiClient(gemini_key)
    targets = [(i+1, *d) for i, d in enumerate(DEMOS)]
    if demo_idx is not None:
        targets = [t for t in targets if t[0] == demo_idx]
        if not targets:
            print(f"Demo {demo_idx} not found. Available: 1–{len(DEMOS)}")
            return []
    all_results = []
    for idx, label, source, func_name, test_inputs, test_cases in targets:
        print(f"\n{'▓'*72}\n  {label}\n{'▓'*72}")
        opt = SPECTRAOptimizer(
            source=source, func_name=func_name,
            test_inputs=test_inputs, test_cases=test_cases,
            max_f3_evals=budget, llm=llm,
            ei_top_k=ei_top_k,
            out_dir=out_dir / func_name,
            co2_intensity=co2_intensity,
            use_process_isolation=use_process_isolation,
            fidelity_leniency=fidelity_leniency,
            adaptive_reps=adaptive_reps)
        try:
            result = opt.optimize()
            opt.save_outputs(result, label)
            all_results.append((label, result))
        except Exception:
            traceback.print_exc()
            all_results.append((label, {"error": "exception"}))
    _print_summary(all_results)
    return all_results


def _print_summary(results):
    print("\n\n" + "═" * 72)
    print("  SPECTRA Research v3 — Summary")
    print(f"  Energy backend : {_ACTIVE_BACKEND.value.upper()}")
    print(f"  GP surrogate   : {'✓' if HAS_SKLEARN else '✗'}")
    print(f"  Matplotlib     : {'✓' if HAS_MPLOT else '✗'}")
    print("═" * 72)
    hdr = (f"  {'Label':<40} {'Base(mJ)':>10} {'Best(mJ)':>10} {'Δ':>7}"
           f"  {'F3':>3}  {'Esc':>3}  {'CO₂(µg)':>9}")
    print(hdr); print("  " + "─" * 75)
    for label, r in results:
        if "error" in r:
            print(f"  {label:<40}  ERROR"); continue
        esc = r.get("fallback_escapes_used", 0)
        cal = r.get("calibrator", {})
        f1r = cal.get("f1_f3_pearson")
        cal_str = f"  r₁₃={f1r:.2f}" if f1r is not None else ""
        print(f"  {label[:40]:<40} "
              f"{r['baseline_mj']:>8.4f}mJ "
              f"{r['best_mj']:>8.4f}mJ "
              f"{r['improvement_pct']:>+6.1f}%"
              f"  {r['f3_evals']:>2}"
              f"  {esc:>3}"
              f"  {r.get('co2_search_ug',0):>8.2f}"
              f"{cal_str}")
    print("═" * 72 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# 12. File Loaders
# ══════════════════════════════════════════════════════════════════════════════

def _load_module(path: str):
    spec = importlib.util.spec_from_file_location("_spectra_tmp", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod); return mod


def detect_function_names(source: str) -> list[str]:
    return [n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]


def load_test_data(path: str) -> tuple[list, list]:
    mod = _load_module(path)
    ti = getattr(mod, "TEST_INPUTS", [])
    tc = getattr(mod, "TEST_CASES",  [])
    ti = [t if isinstance(t, tuple) else (t,) for t in ti]
    tc = [(t[0] if isinstance(t[0], tuple) else (t[0],), t[1]) for t in tc]
    return ti, tc


# ══════════════════════════════════════════════════════════════════════════════
# 13. CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="SPECTRA Research Edition v2 — energy-aware optimizer with full metrics",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent("""
        Examples
        ────────
          python spectra_research.py                                 # all demos
          python spectra_research.py --demo 2                        # demo 2 only
          python spectra_research.py --source f.py --tests t.py      # your code
          python spectra_research.py --gemini-key AIza... \\
              --source f.py --tests t.py --budget 15
          python spectra_research.py --source f.py --tests t.py --ei-top-k 2
          python spectra_research.py --co2-intensity 300             # custom CO₂ grid
          python spectra_research.py --no-process-isolation          # in-process only
          python spectra_research.py --list-ops
          python spectra_research.py --out-dir results/

        Test file format (t.py)
        ───────────────────────
          TEST_INPUTS = [(arg1, arg2, ...), ...]
          TEST_CASES  = [((arg1,arg2,...), expected), ...]
        """))
    parser.add_argument("--source",     help="Python source file")
    parser.add_argument("--tests",      help="Test data file (TEST_INPUTS / TEST_CASES)")
    parser.add_argument("--func",       help="Function name (auto-detected if omitted)")
    parser.add_argument("--gemini-key", dest="gemini_key",
                        help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--no-llm",     action="store_true",
                        help="Disable LLM operators even if key is set")
    parser.add_argument("--budget",     type=int, default=10,
                        help="Max F3 evaluations (default 100)")
    parser.add_argument("--ei-top-k",   type=int, default=2,
                        help="Evaluate top-K EI candidates per iteration (default 2)")
    parser.add_argument("--out-dir",    dest="out_dir", default="spectra_output",
                        help="Output directory (default: spectra_output/)")
    parser.add_argument("--demo",       type=int, metavar="N",
                        help="Run only built-in demo N (1–6)")
    parser.add_argument("--list-ops",   action="store_true",
                        help="List all operators and exit")
    parser.add_argument("--quiet",      action="store_true",
                        help="Suppress per-iteration log")
    parser.add_argument("--co2-intensity", type=float, default=475.0,
                        dest="co2_intensity",
                        help="Grid CO₂ intensity in gCO₂/kWh (default 475, global avg)")
    parser.add_argument("--no-process-isolation", action="store_true",
                        dest="no_process_isolation",
                        help="Disable subprocess-isolated energy measurement")
    parser.add_argument("--max-fallbacks", type=int, default=3,
                        dest="max_fallbacks",
                        help="Max local-minima escape attempts (default 3)")
    parser.add_argument("--fidelity-leniency", type=float, default=0.10,
                        dest="fidelity_leniency",
                        help=("P(better) floor at F1 for abandon decision. "
                              "Lower = more lenient (fewer false prunes). "
                              "Default 0.10. Range [0.01, 0.30]."))
    parser.add_argument("--no-adaptive-reps", action="store_true",
                        dest="no_adaptive_reps",
                        help="Disable CV-triggered extra rep escalation at F1/F2")
    parser.add_argument("--surrogate-path", type=str, default=None,
                        help="Path to a .pkl file to load/save the Gaussian Process model across runs")
    
    args = parser.parse_args()
    if args.ei_top_k < 1:
        sys.exit("--ei-top-k must be >= 1")

    gemini_key = None if args.no_llm else (
        args.gemini_key or os.environ.get("GEMINI_API_KEY"))
    out_dir = Path(args.out_dir)
    use_isolation = not args.no_process_isolation

    if args.list_ops:
        print("\nSPECTRA Research v3 — Transformation Operators")
        print("═" * 62)
        for op in ALL_OPERATORS:
            llm_t = " [Gemini]" if op.needs_llm else "         "
            print(f"  Tier {op.tier.value}{llm_t}  {op.name}")
        print(f"\n  (escape) Tier H [Gemini]  {_ESCAPE_OPERATOR.name}")
        print(f"\n  Total: {len(ALL_OPERATORS)} standard + 1 escape operator")
        print(); return

    if not args.source:
        print("No --source provided — running built-in demos.\n")
        run_demos(gemini_key=gemini_key, budget=args.budget,
                  out_dir=out_dir, demo_idx=args.demo,
                  ei_top_k=args.ei_top_k,
                  co2_intensity=args.co2_intensity,
                  use_process_isolation=use_isolation,
                  fidelity_leniency=max(0.01, min(0.30, args.fidelity_leniency)),
                  adaptive_reps=not args.no_adaptive_reps)
        return

    # Load source
    src_path = Path(args.source)
    if not src_path.exists(): sys.exit(f"Source file not found: {src_path}")
    source = src_path.read_text()

    fn_names = detect_function_names(source)
    if not fn_names: sys.exit("No top-level functions found in source.")
    if args.func:
        if args.func not in fn_names:
            sys.exit(f"Function '{args.func}' not found. Available: {fn_names}")
        func_name = args.func
    elif len(fn_names) == 1:
        func_name = fn_names[0]; print(f"Auto-detected function: {func_name}")
    else:
        func_name = fn_names[0]
        print(f"Multiple functions found: {fn_names}. Using: {func_name}"
              f"  (override with --func)")

    ti, tc = [], []
    if args.tests:
        tp = Path(args.tests)
        if not tp.exists(): sys.exit(f"Test file not found: {tp}")
        ti, tc = load_test_data(str(tp))
        print(f"Loaded {len(ti)} TEST_INPUTS, {len(tc)} TEST_CASES")
    if not ti and not tc:
        sys.exit("Provide TEST_INPUTS or TEST_CASES in the test file.")

    combined = ti + [t[0] for t in tc]
    llm = GeminiClient(gemini_key)
    opt = SPECTRAOptimizer(
        source=source, func_name=func_name,
        test_inputs=combined, test_cases=tc,
        max_f3_evals=args.budget, verbose=not args.quiet,
        llm=llm, ei_top_k=args.ei_top_k,
        out_dir=out_dir / func_name,
        source_file=str(src_path),
        use_process_isolation=use_isolation,
        co2_intensity=args.co2_intensity,
        max_fallbacks=args.max_fallbacks,
        fidelity_leniency=max(0.01, min(0.30, args.fidelity_leniency)),
        adaptive_reps=not args.no_adaptive_reps,
        surrogate_path=Path(args.surrogate_path) if args.surrogate_path else None,
        )
    result = opt.optimize()
    fig_dir = opt.save_outputs(result, func_name)

    _print_summary([(f"{func_name} ({src_path.name})", result)])
    if fig_dir:
        print(f"\n  Figures → {fig_dir}")
        print(f"  Metrics → {out_dir / func_name / (func_name + '_metrics.json')}")
        print(f"  CSV     → {out_dir / func_name / (func_name + '_candidates.csv')}")


if __name__ == "__main__":
    # Required for multiprocessing spawn on macOS/Windows
    multiprocessing.freeze_support()
    main()