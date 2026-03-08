"""
Energy Proxy Filter - Static Code Metric Pre-screening for Mutations

Uses static AST features grounded in EnCoDe's empirical findings
(EASE 2026: "Energy Estimation of Source Code At Design-Time") to
conservatively discard mutations that are very likely to be worse
than the original code — without executing them.

Design principles:
  - Conservative: false negatives (discarding a good mutation) are
    much more costly than false positives (measuring a bad mutation).
    We only discard when MULTIPLE independent metrics agree.
  - Fast: pure AST, no subprocess, no external dependencies.
  - Calibrated: thresholds and required-agreement count are tunable.

Feature selection rationale (from EnCoDe Table 1 / consensus ranking):
  1. operator_density     — #1 Pearson (0.245), #1 avg consensus rank
  2. conditionals_count   — #1 consensus avg_rank overall
  3. cognitive_complexity — Spearman 0.225, consistent across models
  4. nesting_complexity   — Spearman 0.215, consistent
  5. cyclomatic_complexity— Spearman 0.203, consistent
  6. loops_count          — top ExtraTrees importance
  7. literal_density      — Pearson 0.152, Spearman 0.207

All seven have a POSITIVE relationship with energy:
increasing these metrics → increasing energy consumption.

Deliberately excluded:
  - node_type_entropy (negatively correlated: −0.294 Spearman; likely a
    block-type artifact not useful for intra-mutation comparison)
  - functions_count (strongly categorical, distinguishes block types)
  - Engineered/interaction features (too costly to compute, raw features
    provide sufficient signal)
"""

import ast
import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

@dataclass
class _ProxyFeatures:
    """Minimal set of energy-correlated features for proxy filtering."""
    total_nodes: int
    operator_count: int          # total operator tokens (BinOp + Compare + BoolOp)
    literal_count: int           # total literal tokens
    conditionals_count: int      # ast.If nodes
    loops_count: int             # ast.For + ast.While nodes
    cyclomatic_complexity: int   # 1 + branches
    cognitive_complexity: float  # penalty-weighted nesting
    nesting_complexity: float    # average control-flow nesting depth

    @property
    def operator_density(self) -> float:
        return self.operator_count / self.total_nodes if self.total_nodes else 0.0

    @property
    def literal_density(self) -> float:
        return self.literal_count / self.total_nodes if self.total_nodes else 0.0


class _FeatureExtractor(ast.NodeVisitor):
    """Lightweight AST visitor that extracts the 7 proxy features."""

    def __init__(self):
        self.total_nodes = 0
        self.operator_count = 0
        self.literal_count = 0
        self.conditionals_count = 0
        self.loops_count = 0
        self.cyclomatic = 1          # base = 1
        self.cognitive = 0.0
        # nesting tracking
        self._cf_depth = 0           # current control-flow nesting depth
        self._nesting_samples: list[float] = []

    def generic_visit(self, node: ast.AST):
        self.total_nodes += 1
        super().generic_visit(node)

    # -- operators --
    def visit_BinOp(self, node: ast.BinOp):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        self.operator_count += len(node.ops)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        self.operator_count += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.operator_count += 1
        self.generic_visit(node)

    # -- literals --
    def visit_Constant(self, node: ast.Constant):
        self.literal_count += 1
        self.generic_visit(node)

    # keep compatibility with Python < 3.8 AST
    visit_Num = visit_Constant
    visit_Str = visit_Constant

    # -- control flow --
    def visit_If(self, node: ast.If):
        self.conditionals_count += 1
        self.cyclomatic += 1
        self.cognitive += 1 + self._cf_depth   # EnCoDe cognitive complexity formula
        self._nesting_samples.append(self._cf_depth)

        self._cf_depth += 1
        # visit body
        for child in node.body:
            self.visit(child)
        # elif/else: orelse
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # elif — don't increase nesting depth extra
                self.visit(node.orelse[0])
            else:
                for child in node.orelse:
                    self.visit(child)
        self._cf_depth -= 1

    def visit_For(self, node: ast.For):
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

    def visit_While(self, node: ast.While):
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

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self.cyclomatic += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension):
        # list/set/dict comprehensions embed an implicit loop
        self.loops_count += 1
        self.cyclomatic += 1
        self.generic_visit(node)

    def features(self) -> _ProxyFeatures:
        nesting = (
            sum(self._nesting_samples) / len(self._nesting_samples)
            if self._nesting_samples
            else 0.0
        )
        return _ProxyFeatures(
            total_nodes=max(self.total_nodes, 1),
            operator_count=self.operator_count,
            literal_count=self.literal_count,
            conditionals_count=self.conditionals_count,
            loops_count=self.loops_count,
            cyclomatic_complexity=self.cyclomatic,
            cognitive_complexity=self.cognitive,
            nesting_complexity=nesting,
        )


def _extract_features(source: str) -> Optional[_ProxyFeatures]:
    """Parse source and extract proxy features. Returns None on parse error."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    extractor = _FeatureExtractor()
    extractor.visit(tree)
    return extractor.features()


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

@dataclass
class FilterConfig:
    """
    Tunable thresholds for the proxy filter.

    ``min_delta_*`` — the minimum *increase* in a metric for it to
    count as a "worse" signal.  Set conservatively (positive/non-zero).

    ``discard_threshold`` — how many metrics must simultaneously signal
    "worse" before we discard the mutation.  3 out of 7 is the
    recommended starting point; raise to 4 to be even more conservative.
    """
    # Minimum absolute increase to count as "worse"
    min_delta_operator_density: float = 0.012    # ~1σ for small code
    min_delta_conditionals: float = 1.0          # at least one new branch
    min_delta_cognitive: float = 2.0             # noticeable jump
    min_delta_nesting: float = 0.5               # half a level deeper
    min_delta_cyclomatic: float = 1.0            # at least one new path
    min_delta_loops: float = 1.0                 # at least one new loop
    min_delta_literal_density: float = 0.012     # ~1σ for small code

    # How many of the 7 metrics must agree to discard
    discard_threshold: int = 3


class FilterDecision:
    DISCARD = "discard"
    MEASURE = "measure"


class EnergyProxyFilter:
    """
    Conservative pre-screening filter based on EnCoDe static code metrics.

    Usage::

        filter = EnergyProxyFilter()
        if filter.should_discard(original_code, mutated_code):
            # skip expensive energy measurement
            pass
        else:
            # run and measure
            pass
    """

    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config or FilterConfig()
        self._skipped = 0
        self._evaluated = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_discard(self, original_code: str, mutated_code: str) -> bool:
        """
        Return True only if static metrics strongly indicate the mutation
        is worse than the original code.  When in doubt, returns False
        (i.e., always measure when uncertain).
        """
        orig = _extract_features(original_code)
        mut = _extract_features(mutated_code)

        if orig is None or mut is None:
            # Can't parse → let it through (measure)
            return False

        cfg = self.config
        worse_count = 0

        # 1. operator_density
        if (mut.operator_density - orig.operator_density) > cfg.min_delta_operator_density:
            worse_count += 1

        # 2. conditionals_count
        if (mut.conditionals_count - orig.conditionals_count) >= cfg.min_delta_conditionals:
            worse_count += 1

        # 3. cognitive_complexity
        if (mut.cognitive_complexity - orig.cognitive_complexity) >= cfg.min_delta_cognitive:
            worse_count += 1

        # 4. nesting_complexity
        if (mut.nesting_complexity - orig.nesting_complexity) >= cfg.min_delta_nesting:
            worse_count += 1

        # 5. cyclomatic_complexity
        if (mut.cyclomatic_complexity - orig.cyclomatic_complexity) >= cfg.min_delta_cyclomatic:
            worse_count += 1

        # 6. loops_count
        if (mut.loops_count - orig.loops_count) >= cfg.min_delta_loops:
            worse_count += 1

        # 7. literal_density
        if (mut.literal_density - orig.literal_density) > cfg.min_delta_literal_density:
            worse_count += 1

        discard = worse_count >= self.config.discard_threshold

        if discard:
            self._skipped += 1
            logger.debug(
                f"[ProxyFilter] DISCARD: {worse_count}/7 metrics worse "
                f"(threshold={self.config.discard_threshold})"
            )
        else:
            self._evaluated += 1

        return discard

    def breakdown(self, original_code: str, mutated_code: str) -> dict:
        """
        Return per-metric deltas for debugging/analysis.
        Does NOT affect skip/evaluate counters.
        """
        orig = _extract_features(original_code)
        mut = _extract_features(mutated_code)
        if orig is None or mut is None:
            return {"error": "parse failure"}

        return {
            "operator_density_delta": mut.operator_density - orig.operator_density,
            "conditionals_count_delta": mut.conditionals_count - orig.conditionals_count,
            "cognitive_complexity_delta": mut.cognitive_complexity - orig.cognitive_complexity,
            "nesting_complexity_delta": mut.nesting_complexity - orig.nesting_complexity,
            "cyclomatic_complexity_delta": mut.cyclomatic_complexity - orig.cyclomatic_complexity,
            "loops_count_delta": mut.loops_count - orig.loops_count,
            "literal_density_delta": mut.literal_density - orig.literal_density,
            "original": {
                "operator_density": orig.operator_density,
                "conditionals_count": orig.conditionals_count,
                "cognitive_complexity": orig.cognitive_complexity,
                "nesting_complexity": orig.nesting_complexity,
                "cyclomatic_complexity": orig.cyclomatic_complexity,
                "loops_count": orig.loops_count,
                "literal_density": orig.literal_density,
            },
            "mutated": {
                "operator_density": mut.operator_density,
                "conditionals_count": mut.conditionals_count,
                "cognitive_complexity": mut.cognitive_complexity,
                "nesting_complexity": mut.nesting_complexity,
                "cyclomatic_complexity": mut.cyclomatic_complexity,
                "loops_count": mut.loops_count,
                "literal_density": mut.literal_density,
            },
        }

    @property
    def stats(self) -> dict:
        total = self._skipped + self._evaluated
        return {
            "proxy_filtered": self._skipped,
            "proxy_passed": self._evaluated,
            "total_screened": total,
            "filter_rate": self._skipped / total if total else 0.0,
        }
