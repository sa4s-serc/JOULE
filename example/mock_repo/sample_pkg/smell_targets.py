"""
Energy-smell example targets for Phases 1-3 validation.

Each function demonstrates one or more Energy-Smells taxonomy categories.
These are intentionally written with known inefficiencies so that JOULE's
smell-aware operator routing can find and apply the right transformations.

Run optimization with:
  joule run example/mock_repo/sample_pkg/smell_targets.py \
      --function <name> \
      --tests example/mock_repo/tests/test_smell_targets.py::<test_name> \
      --profile standard
"""
from __future__ import annotations

import re


# ── C3 + C10: range(len(x)) anti-pattern ──────────────────────────────────

def index_based_sum(values: list[float]) -> float:
    """Sums values using explicit index access instead of direct iteration.

    Detected smells: C3.S1 (inefficient iteration construct),
                     C10.S5 (scope lookup — range/len in loop condition).
    Target operators: EnumerateSubstitution, ForLoopToComprehension,
                      LoopGlobalToLocalHoisting.
    """
    total = 0.0
    for i in range(len(values)):
        total += values[i]
    return total


# ── C10.S4: string concatenation in loop ──────────────────────────────────

def build_report(records: list[dict[str, str]], rounds: int = 10) -> str:
    """Builds a formatted report by concatenating strings in a loop.

    Detected smells: C10.S4 (inefficient string concatenation),
                     C3.S1 (iteration construct).
    Target operators: StringConcatToJoin, StringBuildBufferLLM.
    """
    report = ""
    for _ in range(rounds):
        for record in records:
            name = record.get("name", "")
            value = record.get("value", "")
            if name and value:
                report += name + "=" + value + ";"
    return report


# ── C5: list membership in hot loop ───────────────────────────────────────

def classify_events(event_ids: list[int], priority_ids: list[int]) -> dict[str, list[int]]:
    """Classifies event IDs as priority or normal by membership check.

    Detected smells: C5.S1 (inefficient data structure choice — list for
                     membership), C3.S2 (recomputing membership per iteration).
    Target operators: ContainerMembershipOperator, LoopMembershipSetCache.
    """
    result: dict[str, list[int]] = {"priority": [], "normal": []}
    for _ in range(100):
        for eid in event_ids:
            if eid in priority_ids:
                result["priority"].append(eid)
            else:
                result["normal"].append(eid)
    return result


# ── C4.S6: exception as control flow ──────────────────────────────────────

def safe_lookup(mapping: dict[str, int], keys: list[str]) -> list[int]:
    """Looks up keys, returning 0 for missing keys via try/except.

    Detected smells: C4.S6 (expensive exception control flow — KeyError used
                     as common-case control flow).
    Target operators: DictGetWithDefault, TryExceptFastPathLLM.
    """
    results = []
    for key in keys:
        try:
            results.append(mapping[key])
        except KeyError:
            results.append(0)
    return results


# ── C6.S7: mutable default argument ───────────────────────────────────────

def collect_tokens(text: str, acc: list[str] = []) -> list[str]:  # noqa: B006
    """Collects tokens from text, accumulating into a default list.

    Detected smells: C6.S7 (leaking mutable default arguments — the default
                     list persists across calls and grows silently).
    Target operators: MutableDefaultArgFix (Phase 5 operator).
    Note: This function has intentional state leakage for demonstration.
    """
    tokens = text.strip().split()
    acc.extend(tokens)
    return list(acc)


# ── C8.S1 + C7.S3: repeated recursive computation ─────────────────────────

def path_count(grid_rows: int, grid_cols: int) -> int:
    """Counts unique paths in a grid using naive recursion (no memoization).

    Detected smells: C8.S1 (missing memoization cache — same subproblems
                     recomputed), C7.S3 (avoidable recursive implementation).
    Target operators: MemoizationAddition, RecursionToDynamicProgramming.
    """
    if grid_rows == 1 or grid_cols == 1:
        return 1
    return path_count(grid_rows - 1, grid_cols) + path_count(grid_rows, grid_cols - 1)


# ── C8.S2: regex compiled on every call ──────────────────────────────────

def extract_numbers(texts: list[str]) -> list[list[str]]:
    """Extracts all numbers from each text string.

    Detected smells: C8.S2 (missing derived-value reuse — regex pattern
                     compiled on every loop iteration instead of once).
    Target operators: RegexPrecompilationLLM, RegexPrecompilationDeterministic.
    """
    results = []
    for text in texts:
        found = re.findall(r"\d+", text)
        results.append(found)
    return results


# ── C3.S4 + C7: nested iteration → O(n²) search ──────────────────────────

def find_common_elements(list_a: list[int], list_b: list[int]) -> list[int]:
    """Finds elements common to both lists using nested iteration.

    Detected smells: C3.S4 (inefficient nested iteration — O(n²) when O(n)
                     set intersection exists), C7.S1 (suboptimal algorithm).
    Target operators: LoopMembershipIndexingLLM, NaiveSearchToIndexed.
    """
    common = []
    for a in list_a:
        for b in list_b:
            if a == b and a not in common:
                common.append(a)
    return common


# ── C1 + C3: loop-invariant computation inside loop ───────────────────────

def score_items(
    items: list[dict[str, float]],
    weights: dict[str, float],
    scale: float = 100.0,
) -> list[float]:
    """Scores items by computing a weighted sum, with invariants inside loop.

    Detected smells: C1.S4 (repeated computation — len and sum of weights
                     recomputed each iteration), C3.S2 (loop-invariant values
                     not hoisted).
    Target operators: LoopInvariantHoistingLLM, LoopGlobalToLocalHoisting.
    """
    scores = []
    for item in items:
        # These are loop-invariant but recomputed every iteration
        n_weights = len(weights)
        total_weight = sum(weights.values())
        if n_weights == 0 or total_weight == 0:
            scores.append(0.0)
            continue
        raw = sum(item.get(k, 0.0) * v for k, v in weights.items())
        scores.append((raw / total_weight) * scale)
    return scores


# ── C5.S2 + C3: dict membership without .keys() elision ──────────────────

def tally_categories(
    items: list[tuple[str, int]],
    valid_categories: list[str],
) -> dict[str, int]:
    """Tallies item counts, filtering to only valid categories.

    Detected smells: C5.S2 (missing helper index — valid_categories scanned
                     as list on every iteration), C5.S4 (unnecessary list
                     for set-semantics operation).
    Target operators: ContainerMembershipOperator, LoopMembershipSetCache,
                      DictKeysMembershipElision.
    """
    counts: dict[str, int] = {}
    for category, value in items:
        if category in valid_categories:
            if category in counts.keys():
                counts[category] += value
            else:
                counts[category] = value
    return counts
