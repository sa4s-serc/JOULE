"""
Phase 1: Scaffold isolated mini-repos for each prepared snippet.

Creates:
  workspaces/<unique_index>/
    pyproject.toml
    target.py
    tests/
      __init__.py
      test_target.py
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from experiment_config import (  # noqa: E402
    JOULE_BACKEND,
    LOGS_DIR,
    OPTIMIZATION_BUDGET,
    RESULTS_DIR,
    WORKSPACES_DIR,
)
from harness.snippet_wrapper import wrap_snippet  # noqa: E402
from harness.test_generator import generate_test_file  # noqa: E402

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOGS_DIR / "experiment.log")],
)
log = logging.getLogger(__name__)

_PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "joule-snippet-{idx}"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.joule]
default_backend = "{backend}"
optimization_budget = {budget}
promotion_scalar_min = 0.0
final_improvement_min = 0.0
terminal_verbosity = "quiet"

[tool.joule.surrogate]
model = "hist_gbdt"
objective = "multi_metric"
"""


def scaffold_one(rec: dict) -> dict:
    """
    Scaffold one workspace. Returns a status dict.
    """
    idx = rec["unique_index"]
    tier = rec["tier"]
    fn_name = rec["target_function_name"]
    target_code = rec["target_code"]

    ws = WORKSPACES_DIR / str(idx)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "tests").mkdir(exist_ok=True)

    # pyproject.toml
    (ws / "pyproject.toml").write_text(
        _PYPROJECT_TEMPLATE.format(
            idx=idx, backend=JOULE_BACKEND, budget=OPTIMIZATION_BUDGET
        )
    )

    # target.py
    try:
        wrapped = wrap_snippet(target_code, tier, fn_name)
    except Exception as e:
        return {"unique_index": idx, "status": "scaffold_error", "error": str(e)}
    (ws / "target.py").write_text(wrapped)

    # Resolve the actual callable name in the wrapped file
    # For tier A with module-level code, wrap_snippet creates fn_name_run
    import ast as _ast
    actual_fn = fn_name
    try:
        tree = _ast.parse(wrapped)
        fn_names_in_file = [
            n.name for n in tree.body
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
        ]
        run_variant = f"{fn_name}_run"
        if run_variant in fn_names_in_file:
            actual_fn = run_variant
        elif fn_name not in fn_names_in_file and fn_names_in_file:
            # Pick the last non-private function (likely the entrypoint)
            candidates = [n for n in fn_names_in_file if not n.startswith("_")]
            if candidates:
                actual_fn = candidates[-1]
    except Exception:
        pass

    # tests/__init__.py
    (ws / "tests" / "__init__.py").write_text("")

    # tests/test_target.py
    test_content = generate_test_file(idx, actual_fn, tier, target_code)
    (ws / "tests" / "test_target.py").write_text(test_content)

    # Write the resolved function name for downstream phases
    meta = {"unique_index": idx, "actual_function_name": actual_fn, "tier": tier}
    (ws / ".scaffold_meta.json").write_text(json.dumps(meta))

    return {"unique_index": idx, "status": "ok", "workspace": str(ws), "actual_fn": actual_fn}


def main() -> None:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    prep_path = RESULTS_DIR / "prep" / "prepared_records.jsonl"
    if not prep_path.exists():
        log.error("Run 00_prep_dataset.py first — %s not found", prep_path)
        sys.exit(1)

    with open(prep_path) as f:
        records = [json.loads(l) for l in f]

    log.info("Scaffolding %d workspaces...", len(records))

    errors = []
    ok = 0
    for i, rec in enumerate(records):
        result = scaffold_one(rec)
        if result["status"] != "ok":
            errors.append(result)
            log.warning("scaffold_error idx=%s: %s", rec["unique_index"], result.get("error"))
        else:
            ok += 1
        if (i + 1) % 500 == 0:
            log.info("  %d / %d scaffolded...", i + 1, len(records))

    out_dir = RESULTS_DIR / "scaffold"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "errors.jsonl", "w") as f:
        for e in errors:
            f.write(json.dumps(e) + "\n")

    log.info("Done: %d ok, %d errors", ok, len(errors))


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
