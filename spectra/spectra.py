#!/usr/bin/env python3
"""
SPECTRA Research Edition
════════════════════════
Structured Program Evaluation and Cost-modeling via
Transformation Retrieval with Adaptation

Exploratory study harness: captures every measurable signal from the
optimization process and renders a full research-grade figure suite.

CLI
───
  python spectra_research.py                              # built-in demos
  python spectra_research.py --source f.py --tests t.py  # your own code
  python spectra_research.py --gemini-key AIza...        # enable LLM operators
  python spectra_research.py --out-dir results/          # output directory
  python spectra_research.py --ei-top-k 2                # evaluate top-2 by EI
  python spectra_research.py --list-ops                  # operator catalogue
  python spectra_research.py --demo 2                    # single demo

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
import csv
import importlib.util
import json
import math
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
                 max_budget: int):
        self.record = StudyRecord(
            function_name=func_name,
            source_file=source_file,
            original_source=original_source,
            best_source=original_source,
            energy_backend=energy_backend,
            has_rapl=(energy_backend == "rapl"),
            has_llm=has_llm,
            llm_provider=llm_provider,
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
               f3_count: int, total_co2_ug: float):
        self.record.total_wall_s = time.perf_counter() - self._t0
        self.record.best_mj = best_mj
        self.record.best_source = best_source
        self.record.improvement_pct = (
            (1.0 - best_mj / self.record.baseline_mj) * 100
            if self.record.baseline_mj > 0 else 0.0)
        self.record.transformation_chain = chain
        self.record.total_f3_evals = f3_count
        self.record.total_co2_search_ug = total_co2_ug
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
                    "f1_mj": c.f1_mj,
                    "f1_improvement_pct": c.f1_improvement_pct,
                    "f1_abandoned": c.f1_abandoned,
                    "f2_mj": c.f2_mj,
                    "f2_improvement_pct": c.f2_improvement_pct,
                    "f2_abandoned": c.f2_abandoned,
                    "f3_mj": c.f3_mj,
                    "f3_improvement_pct": c.f3_improvement_pct,
                    "f3_std_mj": c.f3_std_mj,
                    "f3_co2_ug": c.f3_co2_ug,
                    "statistically_significant": c.statistically_significant,
                    "confirmed_improvement": c.confirmed_improvement,
                    "chain_depth": c.chain_depth,
                    "iteration_best_mj": it.best_energy_mj,
                    "iteration_wall_s": it.wall_clock_s,
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


@dataclass
class EnergyReading:
    joules: float
    duration_s: float
    backend: EnergyBackend

    @property
    def co2_g(self) -> float:
        return self.joules * 475 / 3_600_000


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
# 2.  Core Data Structures
# ══════════════════════════════════════════════════════════════════════════════

class Tier(Enum):
    H = "H"; M = "M"; L = "L"


class Fidelity(Enum):
    F0 = 0; F1 = 1; F2 = 2; F3 = 3


FIDELITY_REPS = {Fidelity.F1: 5, Fidelity.F2: 8, Fidelity.F3: 20}


@dataclass
class EnergyMeasurement:
    mean_j: float; std_j: float; n_runs: int
    fidelity: Fidelity; improvement: float = 0.0; co2_g: float = 0.0

    @property
    def mean_mj(self): return self.mean_j * 1000

    @property
    def std_mj(self): return self.std_j * 1000


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
# 3.  Gemini LLM Client
# ══════════════════════════════════════════════════════════════════════════════

class GeminiClient:
    """
    Calls Gemini via the REST API (no google-generativeai package needed).
    Model: gemini-2.5-flash
    """
    BASE_URL = ("https://generativelanguage.googleapis.com/v1beta/models"
                "/gemini-2.5-flash:generateContent")

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.available = bool(self.api_key)
        self.provider = "gemini-2.5-flash"
        self._call_count = 0
        self._total_tokens_est = 0

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024
                 ) -> Optional[str]:
        if not self.available: return None
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system}]} if system else None,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
        }).encode()
        url = f"{self.BASE_URL}?key={self.api_key}"
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            self._call_count += 1
            self._total_tokens_est += len(text.split())
            return text
        except Exception as exc:
            print(f"[Gemini] API error: {exc}", file=sys.stderr)
            return None

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
        raw = raw.strip()
        if raw.upper().startswith("INAPPLICABLE"): return None
        raw = re.sub(r"^```python\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
        try: ast.parse(raw); return raw
        except SyntaxError: return None


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

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef): continue
            assigned, tested = set(), set()
            for s in ast.walk(fn):
                if (isinstance(s, ast.Assign) and len(s.targets) == 1
                        and isinstance(s.targets[0], ast.Name)
                        and isinstance(s.value, ast.List)):
                    assigned.add(s.targets[0].id)
                if isinstance(s, ast.Compare):
                    for op, comp in zip(s.ops, s.comparators):
                        if isinstance(op, ast.In) and isinstance(comp, ast.Name):
                            tested.add(comp.id)
            if assigned & tested: return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._vars: set = set()
            def visit_FunctionDef(self, node):
                assigned, tested = set(), set()
                for s in ast.walk(node):
                    if (isinstance(s, ast.Assign) and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and isinstance(s.value, ast.List)):
                        assigned.add(s.targets[0].id)
                    if isinstance(s, ast.Compare):
                        for op, comp in zip(s.ops, s.comparators):
                            if isinstance(op, ast.In) and isinstance(comp, ast.Name):
                                tested.add(comp.id)
                self._vars = assigned & tested
                self.generic_visit(node); return node
            def visit_Assign(self, node):
                if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in self._vars
                        and isinstance(node.value, ast.List)):
                    node.value = ast.Set(elts=node.value.elts); self.changed = True
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class MemoizationAddition(TransformationOperator):
    tier, name = Tier.H, "MemoizationAddition"

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for child in ast.walk(fn):
                    if (child is not fn and isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == fn.name): return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False; self._recurs: set = set()
            def visit_Module(self, node):
                for s in node.body:
                    if isinstance(s, ast.FunctionDef):
                        for child in ast.walk(s):
                            if (child is not s and isinstance(child, ast.Call)
                                    and isinstance(child.func, ast.Name)
                                    and child.func.id == s.name):
                                self._recurs.add(s.name); break
                self.generic_visit(node)
                if self._recurs and not any(
                        isinstance(s, ast.Import) and
                        any(a.name == "functools" for a in s.names)
                        for s in node.body):
                    node.body.insert(0, ast.Import(names=[ast.alias(name="functools")]))
                return node
            def visit_FunctionDef(self, node):
                if node.name in self._recurs and not node.decorator_list:
                    node.decorator_list = [ast.Call(
                        func=ast.Attribute(value=ast.Name(id="functools", ctx=ast.Load()),
                                           attr="lru_cache", ctx=ast.Load()),
                        args=[], keywords=[ast.keyword(arg="maxsize",
                                                        value=ast.Constant(None))])]
                    self.changed = True
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
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
    tier, name = Tier.L, "StringConcatToJoin"

    def precondition(self, tree, source):
        return bool(re.search(
            r'(\w+)\s*=\s*["\']["\'].*?for\s+\w+.*?:\s*\1\s*\+=', source, re.DOTALL))

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

    def precondition(self, tree, source):
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "sorted"
                    and node.value.args
                    and isinstance(node.value.args[0], ast.Name)
                    and node.value.args[0].id == node.targets[0].id): return True
        return False

    def apply(self, source, llm=None):
        class _T(ast.NodeTransformer):
            def __init__(self): self.changed = False
            def visit_Assign(self, node):
                if (len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "sorted"
                        and node.value.args
                        and isinstance(node.value.args[0], ast.Name)
                        and node.value.args[0].id == node.targets[0].id):
                    vn = node.targets[0].id
                    sort_call = ast.Expr(value=ast.Call(
                        func=ast.Attribute(value=ast.Name(id=vn, ctx=ast.Load()),
                                           attr="sort", ctx=ast.Load()),
                        args=[], keywords=node.value.keywords))
                    self.changed = True
                    return ast.copy_location(sort_call, node)
                return node
        try:
            t = ast.parse(source); tr = _T(); nt = tr.visit(t)
            if tr.changed: ast.fix_missing_locations(nt); return ast.unparse(nt)
        except Exception: pass
        return None


class LocalImportHoisting(TransformationOperator):
    tier, name = Tier.L, "LocalImportHoisting"

    def precondition(self, tree, source):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for s in fn.body:
                    if isinstance(s, (ast.Import, ast.ImportFrom)): return True
        return False

    def apply(self, source, llm=None):
        try:
            tree = ast.parse(source); hoisted = []
            class _T(ast.NodeTransformer):
                def visit_FunctionDef(self, node):
                    new_body = []
                    for s in node.body:
                        if isinstance(s, (ast.Import, ast.ImportFrom)):
                            hoisted.append(s)
                        else: new_body.append(s)
                    node.body = new_body or [ast.Pass()]; return node
            new_tree = _T().visit(tree)
            if hoisted:
                existing = {ast.unparse(s) for s in new_tree.body
                            if isinstance(s, (ast.Import, ast.ImportFrom))}
                to_add = [s for s in hoisted if ast.unparse(s) not in existing]
                if to_add:
                    new_tree.body = to_add + new_tree.body
                    ast.fix_missing_locations(new_tree)
                    return ast.unparse(new_tree)
        except Exception: pass
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


# ─── Tier H/M: LLM-based semantic operators ──────────────────

class LLMOperator(TransformationOperator):
    needs_llm = True
    _extra: str = ""

    def precondition(self, tree, source): return True

    def apply(self, source, llm=None):
        if not llm or not llm.available: return None
        return llm.transform(source, self.name, self._extra)


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


ALL_OPERATORS: list[TransformationOperator] = [
    ForLoopToComprehension(),
    IteratorSubstitution(),
    ReductionListCompToGenerator(),
    DictKeysMembershipElision(),
    StringConcatToJoin(),
    SortedToInPlaceSort(),
    LocalImportHoisting(),
    ListToSetMembership(),
    LoopMembershipSetCache(),
    SeenSetForAppendDedup(),
    MemoizationAddition(),
    RecursionToDynamicProgramming(),
    NaiveSearchToIndexed(),
    AlgorithmComplexityReduction(),
    VectorizationDelegate(),
    LoopMembershipIndexingLLM(),
    SeenSetDeduplicationLLM(),
    GeneratorChainFusion(),
    ManualReductionToBuiltinsLLM(),
    LoopInvariantHoistingLLM(),
    EarlyExitOptimization(),
    CachingWrapper(),
]


# ══════════════════════════════════════════════════════════════════════════════
# 5.  Multi-Fidelity Energy Oracle
# ══════════════════════════════════════════════════════════════════════════════

def _abandon_threshold(fid: Fidelity) -> float:
    """Return minimum improvement to not abandon at this fidelity level."""
    if _ACTIVE_BACKEND == EnergyBackend.RAPL:
        return 0.02 if fid == Fidelity.F1 else 0.01
    return -0.15 if fid == Fidelity.F1 else -0.05


def _is_significant(base: EnergyMeasurement, cand: EnergyMeasurement) -> bool:
    z = 1.96 if _ACTIVE_BACKEND == EnergyBackend.RAPL else 1.28
    se = math.sqrt(base.std_j ** 2 / base.n_runs + cand.std_j ** 2 / cand.n_runs)
    if se < 1e-15: return cand.mean_j < base.mean_j
    return (base.mean_j - cand.mean_j) > z * se


class MultiFidelityOracle:

    def __init__(self, func_name: str, test_inputs: list[tuple]):
        self.func_name = func_name
        self.test_inputs = test_inputs
        self._baseline: Optional[EnergyMeasurement] = None

    def establish_baseline(self, source: str) -> Optional[EnergyMeasurement]:
        m = self.measure(source, Fidelity.F3)
        self._baseline = m; return m

    def measure(self, source: str, fidelity: Fidelity,
                warmup: int = 1) -> Optional[EnergyMeasurement]:
        if fidelity == Fidelity.F0: return None
        n = FIDELITY_REPS[fidelity]
        readings: list[EnergyReading] = []
        try:
            ns: dict = {}
            exec(compile(source, "<spectra>", "exec"), ns)
            fn: Callable = ns[self.func_name]
            for _ in range(warmup):
                for args in self.test_inputs[:1]: fn(*args)
            for _ in range(n):
                with EnergyMeter() as m:
                    for args in self.test_inputs: fn(*args)
                readings.append(m.result)
        except Exception:
            return None
        joules = [r.joules for r in readings]
        mean = sum(joules) / len(joules)
        std  = math.sqrt(sum((j - mean) ** 2 for j in joules) / len(joules))
        co2  = sum(r.co2_g for r in readings) / len(readings)
        improvement = (1.0 - mean / self._baseline.mean_j
                       if self._baseline and self._baseline.mean_j > 0 else 0.0)
        return EnergyMeasurement(mean_j=mean, std_j=std, n_runs=n,
                                 fidelity=fidelity, improvement=improvement,
                                 co2_g=co2)


# ══════════════════════════════════════════════════════════════════════════════
# 6.  Energy Surrogate (GP)
# ══════════════════════════════════════════════════════════════════════════════

class EnergySurrogate:

    def __init__(self):
        self._X: list = []; self._y: list = []
        self._model = None; self._trained = False

    def _featurize(self, source: str, chain: list[dict], mean_n: float) -> list:
        try: tree = ast.parse(source)
        except SyntaxError: return [0.0] * 12
        def c(cls): return sum(1 for _ in ast.walk(tree) if isinstance(_, cls))
        llm_tier = max({"H": 3, "M": 2, "L": 1}.get(t.get("tier", "L"), 1)
                       for t in chain) if chain else 0
        return [float(c(ast.For)), float(c(ast.While)), float(c(ast.ListComp)),
                float(c(ast.Set)) + float(c(ast.DictComp)), float(c(ast.Call)),
                float(len(source)) / 500.0, float(c(ast.Compare)),
                float(sum(1 for n in ast.walk(tree) if isinstance(n, ast.Compare)
                          and any(isinstance(op, ast.In) for op in n.ops))),
                float(llm_tier), float(len(chain)),
                float(sum(1 for t in chain if t.get("needs_llm"))),
                math.log1p(mean_n) / 10.0]

    def update(self, source: str, chain: list[dict], energy_j: float, mean_n: float):
        self._X.append(self._featurize(source, chain, mean_n))
        self._y.append(energy_j)
        if len(self._X) >= 3 and HAS_SKLEARN and HAS_NUMPY: self._retrain()

    def predict(self, source: str, chain: list[dict],
                mean_n: float) -> tuple[Optional[float], float]:
        if not self._trained or not HAS_SKLEARN: return None, float("inf")
        x = np.array([self._featurize(source, chain, mean_n)])
        m, s = self._model.predict(x, return_std=True)
        return float(m[0]), float(s[0])

    def _retrain(self):
        X = np.array(self._X); y = np.array(self._y)
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            length_scale=np.ones(X.shape[1]), nu=2.5)
        self._model = GaussianProcessRegressor(
            kernel=kernel, alpha=1e-6, normalize_y=True, n_restarts_optimizer=2)
        self._model.fit(X, y); self._trained = True

    @property
    def is_trained(self) -> bool: return self._trained


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
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    @staticmethod
    def _npdf(z):
        return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)

    def expected_improvement(self, mean: float, std: float) -> float:
        if std <= 0: return 0.0
        z = (self.best_energy - mean) / std
        return max(0.0, (self.best_energy - mean) * self._ncdf(z) + std * self._npdf(z))

    def screen_and_score(self, candidates: list[ProgramVariant]
                         ) -> list[tuple[int, float, float, float]]:
        """Returns [(idx, pred_mj, std_mj, ei)] sorted by EI descending."""
        results = []
        for i, c in enumerate(candidates):
            pred, std = self.surrogate.predict(c.source, c.chain, 100.0)
            if pred is not None:
                ei = self.expected_improvement(pred / 1000.0, std / 1000.0)
                if pred / 1000.0 < self.best_energy * 1.1:  # loose screen
                    results.append((i, pred, std, ei))
            else:
                results.append((i, float("nan"), float("nan"), 1.0))
        if not results: results = [(i, float("nan"), float("nan"), 1.0)
                                    for i in range(len(candidates))]
        results.sort(key=lambda x: -x[3])
        return results


# ══════════════════════════════════════════════════════════════════════════════
# 8.  Correctness Engine
# ══════════════════════════════════════════════════════════════════════════════

class CorrectnessEngine:

    def __init__(self, orig_source: str, func_name: str,
                 test_inputs: list[tuple], test_cases: list[tuple],
                 epsilon: float = 1e-9):
        self.func_name = func_name
        self.test_inputs = test_inputs
        self.test_cases = test_cases
        self.epsilon = epsilon
        self._orig = self._load(orig_source)

    def _load(self, source: str) -> Optional[Callable]:
        try:
            ns: dict = {}; exec(compile(source, "<spectra>", "exec"), ns)
            return ns.get(self.func_name)
        except Exception: return None

    def verify(self, source: str) -> tuple[bool, str]:
        if self._orig is None: return False, "Original failed to load"
        cand = self._load(source)
        if cand is None: return False, "Candidate failed to compile"
        for args, exp in self.test_cases:
            try:
                actual = cand(*args)
                if not self._eq(exp, actual): return False, f"Test case mismatch: args={args}"
            except Exception as e: return False, f"Exception on test case {args}: {e}"
        for args in self.test_inputs:
            try:
                exp = self._orig(*args); actual = cand(*args)
                if not self._eq(exp, actual): return False, f"Regression mismatch on {args}"
            except Exception as e: return False, f"Exception on regression input {args}: {e}"
        for args in self._fuzz_inputs():
            try:
                exp = self._orig(*args); actual = cand(*args)
                if not self._eq(exp, actual): return False, f"Fuzz mismatch on {args}"
            except Exception: pass
        return True, "OK"

    def _eq(self, a, b) -> bool:
        if isinstance(a, float):
            return (math.isnan(a) and math.isnan(b)) or abs(a - b) < self.epsilon
        if isinstance(a, (list, tuple)):
            return len(a) == len(b) and all(self._eq(x, y) for x, y in zip(a, b))
        if isinstance(a, dict):
            return a.keys() == b.keys() and all(self._eq(a[k], b[k]) for k in a)
        return a == b

    def _fuzz_inputs(self) -> list[tuple]:
        if not self.test_inputs: return []
        sample = self.test_inputs[0]; fuzz = []
        for i, arg in enumerate(sample):
            def swap(v): return tuple(v if j == i else a for j, a in enumerate(sample))
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


# ══════════════════════════════════════════════════════════════════════════════
# 9.  Research Plotter
# ══════════════════════════════════════════════════════════════════════════════

RESEARCH_COLORS = {
    "baseline": "#E74C3C", "best":     "#2ECC71",
    "candidate": "#3498DB", "fail":    "#95A5A6",
    "H": "#E74C3C", "M": "#F39C12",  "L": "#27AE60",
    "confirmed": "#2ECC71", "rejected": "#E74C3C", "partial": "#F39C12",
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
    Produces individual PDFs + one composite summary figure.
    """

    def __init__(self, record: StudyRecord, out_dir: Path):
        self.r = record
        self.out = out_dir
        self.out.mkdir(parents=True, exist_ok=True)
        if HAS_MPLOT: _apply_research_style()

    # ── helpers ─────────────────────────────────────────────

    def _all_candidates(self) -> list[CandidateRecord]:
        return [c for it in self.r.iterations for c in it.candidates]

    def _save(self, fig, name: str):
        p = self.out / name
        fig.savefig(p)
        plt.close(fig)
        return p

    # ── Figure 1: Energy Trajectory ─────────────────────────
    def plot_energy_trajectory(self) -> Path:
        iters = self.r.iterations
        if not iters: return None
        xs = list(range(len(iters)))
        best_mj  = [it.best_energy_mj  for it in iters]
        base_mj  = [self.r.baseline_mj] * len(iters)
        # confirmed candidates per iteration
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
        # Matrix: rows=candidates, cols=[F1, F2, F3]
        data = []
        for c in cands:
            f1 = c.f1_improvement_pct if c.f1_mj is not None else float("nan")
            f2 = c.f2_improvement_pct if c.f2_mj is not None else float("nan")
            f3 = c.f3_improvement_pct if c.f3_mj is not None else float("nan")
            data.append([f1, f2, f3])
        if not HAS_NUMPY: return None
        arr = np.array(data)
        # Clip for display
        arr_disp = np.clip(arr, -50, 100)

        fig, ax = plt.subplots(figsize=(5, max(4, n * 0.45 + 1.5)))
        # Replace NaN with sentinel for display
        display = np.where(np.isnan(arr_disp), -999, arr_disp)
        im = ax.imshow(display, aspect="auto", cmap="RdYlGn",
                       vmin=-50, vmax=100, interpolation="nearest")
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Improvement (%)", fontsize=9)
        ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["F1", "F2", "F3"])
        ax.set_yticks(range(n))
        short_ops = [o[:22] for o in ops]
        ax.set_yticklabels(short_ops, fontsize=7)
        # Annotate cells
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
        # Pearson r
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
        # Breakdown: baseline measurement vs. F1 vs F2 vs F3
        f1_co2 = f2_co2 = f3_co2 = 0.0
        for c in self._all_candidates():
            if c.f1_mj is not None:
                f1_co2 += (c.f1_mj / 1000) * FIDELITY_REPS[Fidelity.F1] * 475 / 3.6e6 * 1e6
            if c.f2_mj is not None:
                f2_co2 += (c.f2_mj / 1000) * FIDELITY_REPS[Fidelity.F2] * 475 / 3.6e6 * 1e6
            if c.f3_mj is not None:
                f3_co2 += (c.f3_mj / 1000) * FIDELITY_REPS[Fidelity.F3] * 475 / 3.6e6 * 1e6
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
        ax1.set_title("CO₂ Budget by Phase")

        # Cumulative CO2 over iterations
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
        from collections import Counter
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

        # Improvement distribution per tier
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
        ax.bar(range(len(labels)), energies, color=colors, alpha=0.85, edgecolor="white")
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
        # plot running max EI
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

        # Baseline std profile across baseline measurement
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

    # ── Figure 10: Composite Summary Poster ──────────────────
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
        f1c = f2c = f3c = 0.0
        for c in cands:
            if c.f1_mj: f1c += c.f1_mj/1000 * FIDELITY_REPS[Fidelity.F1] * 475/3.6e6*1e6
            if c.f2_mj: f2c += c.f2_mj/1000 * FIDELITY_REPS[Fidelity.F2] * 475/3.6e6*1e6
            if c.f3_mj: f3c += c.f3_mj/1000 * FIDELITY_REPS[Fidelity.F3] * 475/3.6e6*1e6
        basec = self.r.baseline_co2_ug * FIDELITY_REPS[Fidelity.F3]
        vals = [basec, f1c, f2c, f3c]
        cols = [RESEARCH_COLORS["baseline"], "#F7DC6F",
                RESEARCH_COLORS["M"], RESEARCH_COLORS["H"]]
        bars = ax_co2.bar(["Baseline", "F1", "F2", "F3"], vals, color=cols, alpha=0.85,
                           edgecolor="white")
        ax_co2.set_ylabel("CO₂ cost (µg eq.)")
        ax_co2.set_title("CO₂ Budget by Phase")
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
            "",
            f"Baseline:         {self.r.baseline_mj:.4f} ± {self.r.baseline_std_mj:.4f} mJ",
            f"Best found:       {self.r.best_mj:.4f} mJ",
            f"Improvement:      {self.r.improvement_pct:+.2f}%",
            "",
            f"F3 evaluations:   {self.r.total_f3_evals} / {self.r.max_f3_budget}",
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
        return self._save(fig, "fig10_summary_poster.png")

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
            ("Fig 10 Summary Poster",           self.plot_summary_poster),
        ]
        saved = []
        for label, fn in plots:
            try:
                p = fn()
                if p: print(f"  ✓ {label:<35} → {p.name}"); saved.append(p)
                else:  print(f"  – {label:<35}   (skipped – insufficient data)")
            except Exception as exc:
                print(f"  ✗ {label:<35}   Error: {exc}")
        return saved


# ══════════════════════════════════════════════════════════════════════════════
# 10. SPECTRA Optimizer (research edition)
# ══════════════════════════════════════════════════════════════════════════════

class SPECTRAOptimizer:

    def __init__(self, source: str, func_name: str,
                 test_inputs: list[tuple], test_cases: list[tuple],
                 operators: Optional[list[TransformationOperator]] = None,
                 max_f3_evals: int = 10, verbose: bool = True,
                 llm: Optional[GeminiClient] = None,
                 ei_top_k: int = 2,
                 out_dir: Optional[Path] = None,
                 source_file: str = "<inline>"):
        self.source      = textwrap.dedent(source).strip()
        self.func_name   = func_name
        self.test_inputs = test_inputs
        self.test_cases  = test_cases
        self.operators   = operators or ALL_OPERATORS
        self.max_f3      = max_f3_evals
        self.verbose     = verbose
        self.llm         = llm or GeminiClient()
        self.ei_top_k    = max(1, int(ei_top_k))
        self.out_dir     = out_dir or Path("spectra_output")
        self.source_file = source_file

        self.oracle      = MultiFidelityOracle(func_name, test_inputs)
        self.surrogate   = EnergySurrogate()
        self.engine      = MFBOEngine(self.surrogate, self.oracle)
        self.correctness = CorrectnessEngine(
            self.source, func_name, test_inputs, test_cases)

        self._pareto: list[ProgramVariant] = []
        self._seen: set[str] = set()
        self._f3_count = 0
        self._co2_ug   = 0.0
        self._metrics: Optional[MetricsCollector] = None

    def _log(self, msg: str):
        if self.verbose: print(msg)

    def _mean_n(self) -> float:
        lens = [len(a) for args in self.test_inputs for a in args
                if isinstance(a, (list, tuple, str))]
        return sum(lens) / len(lens) if lens else 100.0

    def _generate_candidates(self, base: ProgramVariant) -> list[ProgramVariant]:
        try: tree = ast.parse(base.source)
        except SyntaxError: return []
        cands = []
        local_seen = set()
        for op in self.operators:
            if op.needs_llm and not self.llm.available: continue
            try:
                if not op.precondition(tree, base.source): continue
            except Exception: continue
            new_src = op.apply(base.source, self.llm)
            if not new_src or new_src == base.source: continue
            if new_src in self._seen or new_src in local_seen: continue
            local_seen.add(new_src)
            self._seen.add(new_src)
            cands.append(ProgramVariant(
                source=new_src,
                chain=base.chain + [{"operator": op.name, "tier": op.tier.value,
                                     "needs_llm": op.needs_llm}]))
        return cands

    def optimize(self, study_label: str = "") -> dict:
        t_total = time.perf_counter()
        llm_tag = (f"  [Gemini ✓  {self.llm.provider}]"
                   if self.llm.available else "  [LLM ✗ — set GEMINI_API_KEY]")
        self._log("\n" + "═" * 72)
        self._log(f"  SPECTRA Research  ▸  {self.func_name}{llm_tag}")
        self._log(f"  Backend: {_ACTIVE_BACKEND.value.upper()}"
                  f"   GP: {'✓' if HAS_SKLEARN else '✗'}"
                  f"   Matplotlib: {'✓' if HAS_MPLOT else '✗'}")
        self._log(f"  EI top-k: {self.ei_top_k}")
        self._log("═" * 72)

        # ── Baseline ──
        self._log(f"\n[Oracle] Establishing baseline "
                  f"(F3, {FIDELITY_REPS[Fidelity.F3]} reps)…")
        base_m = self.oracle.establish_baseline(self.source)
        if base_m is None: return {"error": "Baseline measurement failed"}

        self._co2_ug += base_m.co2_g * base_m.n_runs * 1e6
        self._log(f"         Baseline : {base_m.mean_mj:.4f} ± {base_m.std_mj:.4f} mJ"
                  f"   CO₂≈{base_m.co2_g * 1e6:.2f}µg/call"
                  f"   backend={_ACTIVE_BACKEND.value}")

        self._metrics = MetricsCollector(
            func_name=self.func_name, source_file=self.source_file,
            original_source=self.source,
            baseline_mj=base_m.mean_mj, baseline_std_mj=base_m.std_mj,
            baseline_co2_ug=base_m.co2_g * 1e6,
            energy_backend=_ACTIVE_BACKEND.value,
            has_llm=self.llm.available,
            llm_provider=self.llm.provider if self.llm.available else "none",
            max_budget=self.max_f3)

        base_v = ProgramVariant(
            source=self.source, measurements={Fidelity.F3: base_m})
        self._pareto = [base_v]
        self._seen.add(self.source)
        self.engine.best_energy = base_m.mean_j
        no_progress = 0

        for iteration in range(1, self.max_f3 + 1):
            if no_progress >= 3:
                self._log("\n[MFBO] Converged (3 iterations without progress).")
                break
            if self._f3_count >= self.max_f3:
                self._log(f"\n[MFBO] F3 budget ({self.max_f3}) exhausted.")
                break

            t_iter = time.perf_counter()
            self._metrics.start_iteration()
            self._log(f"\n── Iteration {iteration} {'─' * 54}")

            # Generate
            all_cands: list[ProgramVariant] = []
            for pv in self._pareto[:5]:
                all_cands.extend(self._generate_candidates(pv))
            if not all_cands:
                self._log("[Graph] No new candidates — search space exhausted.")
                break
            self._log(f"[Graph] {len(all_cands)} candidate(s) generated")

            # Correctness filter — build CandidateRecords
            cand_records: list[CandidateRecord] = []
            verified: list[ProgramVariant] = []
            for ci, c in enumerate(all_cands):
                op_info = c.chain[-1]
                ok, reason = self.correctness.verify(c.source)
                c.is_correct = ok
                tag = "✓" if ok else "✗"
                self._log(f"  {tag} Correctness [{op_info['operator']}]: {reason}")
                cr = CandidateRecord(
                    iteration=iteration, operator=op_info["operator"],
                    tier=op_info["tier"], is_llm=op_info.get("needs_llm", False),
                    correctness_pass=ok, correctness_reason=reason,
                    surrogate_pred_mj=None, surrogate_std_mj=None, ei_score=0.0,
                    f1_mj=None, f1_improvement_pct=None, f1_abandoned=False,
                    f2_mj=None, f2_improvement_pct=None, f2_abandoned=False,
                    f3_mj=None, f3_improvement_pct=None, f3_std_mj=None,
                    f3_co2_ug=None, statistically_significant=False,
                    confirmed_improvement=False,
                    transformed_source=c.source, chain_depth=len(c.chain))
                cand_records.append(cr)
                if ok: verified.append((c, cr))

            if not verified:
                iter_rec = IterationRecord(
                    iteration=iteration,
                    n_candidates_generated=len(all_cands),
                    n_correctness_pass=0, n_correctness_fail=len(all_cands),
                    n_surrogate_screened_in=0, n_surrogate_screened_out=0,
                    selected_operator="(none)", selected_tier="",
                    wall_clock_s=time.perf_counter() - t_iter,
                    best_energy_mj=self.engine.best_energy * 1000,
                    current_baseline_mj=base_m.mean_mj,
                    improvement_over_baseline_pct=0.0,
                    f3_evals_used_so_far=self._f3_count,
                    surrogate_trained=self.surrogate.is_trained,
                    candidates=cand_records)
                self._metrics.record.iterations.append(iter_rec)
                no_progress += 1
                continue

            # Surrogate scoring
            v_list = [v for v, _ in verified]
            scored = self.engine.screen_and_score(v_list)
            screened_in = [i for i, p, s, e in scored if not math.isnan(p)]
            self._log(f"[Surrogate] Scored {len(scored)} candidates"
                      f"  (trained={self.surrogate.is_trained})")

            # Annotate CandidateRecords with surrogate scores
            for vi, pred_mj, std_mj, ei in scored:
                _, cr = verified[vi]
                cr.surrogate_pred_mj = None if math.isnan(pred_mj) else pred_mj
                cr.surrogate_std_mj  = None if math.isnan(std_mj)  else std_mj
                cr.ei_score = ei

            # Select top-k EI candidates
            k = min(self.ei_top_k, len(scored))
            top_scored = scored[:k]
            self._log(f"[MFBO] Selected top-{k} candidate(s) by EI:")
            for rank, (vi, _, _, ei) in enumerate(top_scored, start=1):
                _, sel_cr = verified[vi]
                llm_lbl = " [Gemini]" if sel_cr.is_llm else ""
                self._log(f"  #{rank} '{sel_cr.operator}' Tier {sel_cr.tier}{llm_lbl}"
                          f"   EI={ei * 1000:.4f}×10⁻³")

            # Fidelity escalation + full metric capture for top-k
            self._log("[Oracle] Evaluating with fidelity escalation…")
            confirmed_variants: list[ProgramVariant] = []
            selected_ops: list[str] = []
            selected_tiers: list[str] = []
            for rank, (vi, _, _, _) in enumerate(top_scored, start=1):
                if self._f3_count >= self.max_f3:
                    self._log("         F3 budget exhausted during top-k evaluation.")
                    break
                cand_v, cand_cr = verified[vi]
                selected_ops.append(cand_cr.operator)
                selected_tiers.append(cand_cr.tier)
                self._log(f"      Candidate #{rank}: {cand_cr.operator}")
                confirmed = self._escalate(cand_v, cand_cr, base_m)
                if Fidelity.F3 in cand_v.measurements:
                    self._f3_count += 1
                    m3 = cand_v.measurements[Fidelity.F3]
                    self._co2_ug += m3.co2_g * m3.n_runs * 1e6
                    self.surrogate.update(cand_v.source, cand_v.chain,
                                          m3.mean_j, self._mean_n())
                    if cand_cr.surrogate_pred_mj is not None:
                        self._metrics.record.surrogate_pred_vs_actual.append(
                            (cand_cr.surrogate_pred_mj, m3.mean_mj))
                if confirmed:
                    confirmed_variants.append(cand_v)
            op_name = " | ".join(selected_ops) if selected_ops else "(none)"
            tier = " | ".join(selected_tiers)
            any_confirmed = bool(confirmed_variants)

            iter_best = self.engine.best_energy * 1000
            impr_pct  = (1.0 - iter_best / base_m.mean_mj) * 100 if base_m.mean_mj > 0 else 0.0
            iter_rec = IterationRecord(
                iteration=iteration,
                n_candidates_generated=len(all_cands),
                n_correctness_pass=len(verified),
                n_correctness_fail=len(all_cands) - len(verified),
                n_surrogate_screened_in=len(screened_in),
                n_surrogate_screened_out=len(scored) - len(screened_in),
                selected_operator=op_name, selected_tier=tier,
                wall_clock_s=time.perf_counter() - t_iter,
                best_energy_mj=iter_best,
                current_baseline_mj=base_m.mean_mj,
                improvement_over_baseline_pct=impr_pct,
                f3_evals_used_so_far=self._f3_count,
                surrogate_trained=self.surrogate.is_trained,
                candidates=cand_records)
            self._metrics.record.iterations.append(iter_rec)

            if any_confirmed:
                self._log(f"  ✓ Confirmed improvement(s): {len(confirmed_variants)} — Pareto archive updated")
                self._pareto.extend(confirmed_variants)
                dedup_pareto = {}
                for pv in self._pareto:
                    dedup_pareto[pv.source] = pv
                self._pareto = list(dedup_pareto.values())
                self._pareto.sort(
                    key=lambda v: (v.best_measurement() or
                                   EnergyMeasurement(float("inf"), 0, 0, Fidelity.F1)).mean_j)
                no_progress = 0
            else:
                no_progress += 1

        # ── Finalise ──
        best_e = self.engine.best_energy * 1000  # mJ
        best_v = next((v for v in self._pareto if v.chain), None)
        best_src = best_v.source if best_v else self.source
        chain = [t["operator"] for t in best_v.chain] if best_v else []

        self._metrics.finish(best_e, best_src, chain, self._f3_count, self._co2_ug)
        return self._report(base_m, best_e, best_src, chain,
                            time.perf_counter() - t_total)

    def _escalate(self, variant: ProgramVariant, cr: CandidateRecord,
                  baseline: EnergyMeasurement) -> bool:
        for fid in [Fidelity.F1, Fidelity.F2, Fidelity.F3]:
            m = self.oracle.measure(variant.source, fid)
            if m is None:
                self._log(f"         F{fid.value} failed"); return False
            variant.measurements[fid] = m
            pct = m.improvement * 100
            co2_str = f"  CO₂≈{m.co2_g * 1e6:.2f}µg"
            self._log(f"         F{fid.value} ({FIDELITY_REPS[fid]:>2} reps): "
                      f"{m.mean_mj:8.4f} mJ  {pct:+6.1f}%{co2_str}")
            # Record per-fidelity metrics
            if fid == Fidelity.F1:
                cr.f1_mj = m.mean_mj; cr.f1_improvement_pct = pct
                thresh = _abandon_threshold(Fidelity.F1)
                if m.improvement < thresh:
                    cr.f1_abandoned = True
                    self._log(f"         F1 clear regression — abandoning"); return False
            elif fid == Fidelity.F2:
                cr.f2_mj = m.mean_mj; cr.f2_improvement_pct = pct
                thresh = _abandon_threshold(Fidelity.F2)
                if m.improvement < thresh:
                    cr.f2_abandoned = True
                    self._log(f"         F2 clear regression — abandoning"); return False
            elif fid == Fidelity.F3:
                cr.f3_mj = m.mean_mj; cr.f3_improvement_pct = pct
                cr.f3_std_mj = m.std_mj; cr.f3_co2_ug = m.co2_g * m.n_runs * 1e6
                sig = _is_significant(baseline, m)
                cr.statistically_significant = sig
                if sig:
                    cr.confirmed_improvement = True
                    self.engine.best_energy = min(self.engine.best_energy, m.mean_j)
                    return True
                else:
                    self._log(f"         Not statistically significant")
                    return False
        return False

    def _report(self, baseline: EnergyMeasurement, best_mj: float,
                best_src: str, chain: list[str], wall_s: float) -> dict:
        improvement = (1.0 - best_mj / baseline.mean_mj) * 100 if baseline.mean_mj > 0 else 0.0
        self._log("\n" + "═" * 72)
        self._log("  Results")
        self._log("═" * 72)
        if chain:
            self._log(f"\n  Chain        : {' → '.join(chain)}")
            self._log(f"  Baseline     : {baseline.mean_mj:.4f} ± {baseline.std_mj:.4f} mJ")
            self._log(f"  Optimised    : {best_mj:.4f} mJ")
            self._log(f"  Improvement  : {improvement:.2f}%")
            self._log(f"  CO₂ search   : {self._co2_ug:.1f} µg eq.")
            self._log(f"  F3 evals     : {self._f3_count} / {self.max_f3}")
            self._log(f"  Wall-clock   : {wall_s:.1f}s")
            self._log(f"\n  Optimised source:\n")
            for line in best_src.split("\n"): self._log(f"    {line}")
        else:
            self._log("  No statistically significant improvement found.")
        return {
            "function": self.func_name, "original_source": self.source,
            "best_source": best_src, "chain": chain,
            "improvement_pct": round(improvement, 3),
            "baseline_mj": round(baseline.mean_mj, 6),
            "baseline_std_mj": round(baseline.std_mj, 6),
            "best_mj": round(best_mj, 6),
            "co2_search_ug": round(self._co2_ug, 3),
            "f3_evals": self._f3_count,
            "ei_top_k": self.ei_top_k,
            "wall_s": round(wall_s, 2),
            "energy_backend": _ACTIVE_BACKEND.value,
        }

    def save_outputs(self, result: dict, label: str = "run"):
        """Write JSON, CSV, and all figures to out_dir."""
        fn = self.func_name
        if self._metrics is None: return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._metrics.export_json(self.out_dir / f"{fn}_metrics.json")
        self._metrics.export_csv(self.out_dir  / f"{fn}_candidates.csv")
        # Result JSON
        (self.out_dir / f"{fn}_result.json").write_text(
            json.dumps(result, indent=2))
        # Optimised source
        (self.out_dir / f"{fn}_optimised.py").write_text(result["best_source"])
        # Figures
        self._log("\n[Plotter] Generating research figures…")
        plotter = ResearchPlotter(self._metrics.record, self.out_dir / f"{fn}_figures")
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
def build_csv_row(values):
    row = ""
    for v in values:
        row += str(v) + ","
    return row
""", "build_csv_row", [(list(range(200)),)], []),

    ("D5 IteratorSubstitution",
     """
def sum_squares(numbers):
    return sum(list(x * x for x in numbers))
""", "sum_squares", [(list(range(5_000)),)], []),
]


def run_demos(gemini_key=None, budget=8, out_dir=Path("spectra_output"),
              demo_idx=None, ei_top_k: int = 2):
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
            out_dir=out_dir / func_name)
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
    print("  SPECTRA Research — Summary")
    print(f"  Energy backend : {_ACTIVE_BACKEND.value.upper()}")
    print(f"  GP surrogate   : {'✓' if HAS_SKLEARN else '✗'}")
    print(f"  Matplotlib     : {'✓' if HAS_MPLOT else '✗'}")
    print("═" * 72)
    hdr = f"  {'Label':<40} {'Base(mJ)':>10} {'Best(mJ)':>10} {'Δ':>7}  {'F3':>3}  {'CO₂(µg)':>9}"
    print(hdr); print("  " + "─" * 70)
    for label, r in results:
        if "error" in r:
            print(f"  {label:<40}  ERROR"); continue
        print(f"  {label[:40]:<40} "
              f"{r['baseline_mj']:>8.4f}mJ "
              f"{r['best_mj']:>8.4f}mJ "
              f"{r['improvement_pct']:>+6.1f}%"
              f"  {r['f3_evals']:>2}  "
              f"{r.get('co2_search_ug',0):>8.2f}")
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
        description="SPECTRA Research Edition — energy-aware optimizer with full metrics",
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
          python spectra_research.py --list-ops
          python spectra_research.py --out-dir results/              # output dir

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
                        help="Max F3 evaluations (default 10)")
    parser.add_argument("--ei-top-k",   type=int, default=2,
                        help="Evaluate top-K EI candidates per iteration (default 2)")
    parser.add_argument("--out-dir",    dest="out_dir", default="spectra_output",
                        help="Output directory for figures / JSON / CSV (default: spectra_output/)")
    parser.add_argument("--demo",       type=int, metavar="N",
                        help="Run only built-in demo N (1–5)")
    parser.add_argument("--list-ops",   action="store_true",
                        help="List all operators and exit")
    parser.add_argument("--quiet",      action="store_true",
                        help="Suppress per-iteration log")
    args = parser.parse_args()
    if args.ei_top_k < 1:
        sys.exit("--ei-top-k must be >= 1")

    gemini_key = None if args.no_llm else (
        args.gemini_key or os.environ.get("GEMINI_API_KEY"))
    out_dir = Path(args.out_dir)

    if args.list_ops:
        print("\nSPECTRA Research — Transformation Operators")
        print("═" * 58)
        for op in ALL_OPERATORS:
            llm_t = " [Gemini]" if op.needs_llm else "         "
            print(f"  Tier {op.tier.value}{llm_t}  {op.name}")
        print(); return

    if not args.source:
        print("No --source provided — running built-in demos.\n")
        run_demos(gemini_key=gemini_key, budget=args.budget,
                  out_dir=out_dir, demo_idx=args.demo,
                  ei_top_k=args.ei_top_k)
        return

    # Load source
    src_path = Path(args.source)
    if not src_path.exists(): sys.exit(f"Source file not found: {src_path}")
    source = src_path.read_text()

    # Detect function
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

    # Load tests
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
        source_file=str(src_path))
    result = opt.optimize()
    fig_dir = opt.save_outputs(result, func_name)

    _print_summary([(f"{func_name} ({src_path.name})", result)])
    if fig_dir:
        print(f"\n  Figures → {fig_dir}")
        print(f"  Metrics → {out_dir / func_name / (func_name + '_metrics.json')}")
        print(f"  CSV     → {out_dir / func_name / (func_name + '_candidates.csv')}")


if __name__ == "__main__":
    main()
