"""
Phase 0: Pre-process dataset.

- Merges energy data with LLM classifications (on unique_index)
- Identifies which snippet version (v0/v1) to target (the higher-energy one)
- Classifies each snippet into a processing tier (A–E)
- Determines the target function name for joule
- Outputs prepared_records.jsonl
"""

import ast
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from experiment_config import (  # noqa: E402
    CLASSIFIED_SMELLS_PATH,
    DATASET_PATH,
    LOGS_DIR,
    RESULTS_DIR,
    SKIP_TIERS,
)

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "experiment.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Tier classification ────────────────────────────────────────────────────


def classify_tier(code: str) -> str:
    """
    A  – top-level functions present + uses stdin (most common)
    B  – script style (no top-level functions) + uses stdin
    C  – clean functions (no stdin needed)
    D  – script style, no stdin
    E  – unsafe (subprocess/shell calls)
    """
    if "subprocess" in code or "os.system" in code or "os.popen" in code:
        return "E"
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "B"  # treat unparseable as script

    has_funcs = any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.col_offset == 0
        for n in tree.body
    )
    uses_stdin = "input()" in code or "sys.stdin" in code or "stdin.readline" in code

    if has_funcs and uses_stdin:
        return "A"
    if has_funcs and not uses_stdin:
        return "C"
    if not has_funcs and uses_stdin:
        return "B"
    return "D"


# ── Target function resolution ─────────────────────────────────────────────

_MAIN_NAMES = {"main", "solve", "solution", "run", "calc", "compute"}


def resolve_target_function(code: str, tier: str) -> str:
    """
    Returns the best function name to target with joule.
    Falls back to 'solution' for script-wrapped snippets.
    """
    if tier in ("B", "D"):
        return "solution"  # we will wrap the whole script

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "solution"

    top_funcs = [
        n.name
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    if not top_funcs:
        return "solution"

    # Prefer a well-known entry-point name
    for name in top_funcs:
        if name.lower() in _MAIN_NAMES:
            return name

    # Prefer longest function (likely most logic)
    try:
        ranked = sorted(
            [
                (n.name, n.end_lineno - n.lineno)  # type: ignore[attr-defined]
                for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            key=lambda x: -x[1],
        )
        return ranked[0][0]
    except Exception:
        return top_funcs[-1]  # last function (often the entrypoint in CP style)


# ── Dataset loading ────────────────────────────────────────────────────────


def load_classifications() -> dict[int, list]:
    """Load unique_index → final_classification from classified_smells."""
    classifications: dict[int, list] = {}
    if not CLASSIFIED_SMELLS_PATH.exists():
        log.warning("Classified smells file not found at %s — labels will be empty", CLASSIFIED_SMELLS_PATH)
        return classifications
    with open(CLASSIFIED_SMELLS_PATH) as f:
        for line in f:
            rec = json.loads(line)
            idx = rec.get("unique_index")
            if idx is not None:
                classifications[idx] = rec.get("final_classification", [])
    log.info("Loaded %d classifications", len(classifications))
    return classifications


def main() -> None:
    out_dir = RESULTS_DIR / "prep"
    out_dir.mkdir(parents=True, exist_ok=True)

    classifications = load_classifications()

    records = []
    skipped = []

    with open(DATASET_PATH) as f:
        raw = [json.loads(l) for l in f]

    log.info("Processing %d records...", len(raw))

    for rec in raw:
        idx = rec["unique_index"]
        e0 = rec["result_energy_v0"]
        e1 = rec["result_energy_v1"]

        # Which version is the worse (higher energy) one?
        if e0 >= e1:
            target_version = "v0"
            target_code = rec["code_v0_no_empty_lines"]
            ground_truth_improvement = e0 / e1 if e1 > 0 else None
        else:
            target_version = "v1"
            target_code = rec["code_v1_no_empty_lines"]
            ground_truth_improvement = e1 / e0 if e0 > 0 else None

        tier = classify_tier(target_code)

        if tier in SKIP_TIERS:
            skipped.append({"unique_index": idx, "reason": f"tier_{tier}", "tier": tier})
            continue

        target_fn = resolve_target_function(target_code, tier)

        prepared = {
            **rec,
            "target_version": target_version,
            "target_code": target_code,
            "tier": tier,
            "target_function_name": target_fn,
            "ground_truth_energy_improvement": ground_truth_improvement,
            "final_classification": classifications.get(idx, []),
            "loc": len(target_code.splitlines()),
            "energy_diff_abs": abs(e0 - e1),
        }
        records.append(prepared)

    # Write outputs
    out_path = out_dir / "prepared_records.jsonl"
    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    skipped_path = out_dir / "skipped.jsonl"
    with open(skipped_path, "w") as f:
        for r in skipped:
            f.write(json.dumps(r) + "\n")

    # Summary
    from collections import Counter
    tiers = Counter(r["tier"] for r in records)
    log.info("Prepared %d records, skipped %d", len(records), len(skipped))
    log.info("Tier distribution: %s", dict(tiers))
    log.info("Output: %s", out_path)


if __name__ == "__main__":
    main()
