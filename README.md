# JOULE

JOULE is a local Python optimization toolkit for measuring refactor candidates against energy, latency, and memory signals while preserving correctness.

It is designed for practical, inspectable optimization work on well-scoped Python targets. Today that means top-level functions, async functions, and class methods, measured through explicit or heuristically resolved workloads, with every run persisted to SQLite and mirrored into reproducible local artifacts. v1 adds optional deep analysis for hotspot profiling, candidate persistence, and richer optimization-process reporting.

## What JOULE Does

- Measures a baseline implementation across `F1`, `F2`, and `F3` fidelity stages
- Generates refactor candidates from deterministic operators and optional LLM prompts
- Verifies candidate correctness in isolated subprocess execution
- Tracks runs, candidates, measurements, artifacts, search events, and hotspot profiles in SQLite
- Produces inspectable summaries, diff artifacts, hotspot reports, and a lightweight HTML dashboard
- Applies accepted candidates back to source code with file-hash protection

## Current v0 Scope

JOULE is currently optimized for a dependable local workflow rather than fully autonomous large-scale optimization.

In scope:
- supported targets: top-level sync functions, top-level async functions, class methods
- supported workloads: explicit pytest/property/harness selectors, heuristic pytest discovery, safe default-arg fallback
- supported backends: `mock`, `rapl`
- reviewable local artifacts: `.joule.lock`, run summaries, dashboard snapshots, stored measurements, hotspot reports, and candidate analysis packs

Out of scope for now:
- automatic dependency installation or dependency-file edits
- background dashboard launch from `run`
- security scanning beyond current execution isolation and purity checks
- multi-hop search seeded from prior Pareto candidates

## Installation

For local development:

```bash
make install-dev
```

That creates `.venv` and installs the project in editable mode with dev dependencies.

If you want optional LLM-backed candidate generation as well:

```bash
./.venv/bin/python -m pip install -e .[dev,llm]
```

## Common Commands

```bash
make test ARGS='-q'
make smoke-example
./joule doctor example/mock_repo
./joule baseline example/mock_repo/sample_pkg/algos.py --function membership_total --tests tests/test_algos.py::test_membership_total --hotspots --output json
./joule run example/mock_repo/sample_pkg/algos.py --function unreferenced_total --budget 4 --analysis --output human
./joule dashboard example/mock_repo --once
```

## Repository Layout

```text
.
├── src/joule/              # CLI, discovery, evaluators, orchestrator, integrations, dashboard
├── tests/                  # unit and CLI tests
├── example/mock_repo/      # small self-contained smoke-test project
├── scripts/smoke_example.py
├── GUIDE.md                # roadmap and v0 scope
├── QUICKSTART.md           # task-oriented setup and first run guide
└── docs/ARCHITECTURE.md    # architecture and design reference
```

## Example Workflow

The fastest end-to-end check is the bundled smoke project:

```bash
make smoke-example
```

That command runs `doctor`, `baseline`, `run`, `inspect`, and `dashboard --once` against [example/mock_repo](/home/prakhar/dev/prakhar479/hedge/example/mock_repo) and verifies that the expected artifacts are produced.

## Outputs and Artifacts

Each run writes to the target project’s artifact directory, usually `.joule/`.

Important files:
- `.joule.lock`: seed, run id, target identity, backend, config snapshot, and source hashes
- `.joule/joule.db`: SQLite state for runs, candidates, measurements, artifacts, apply audits, search events, hotspot profiles, and operator stats
- `.joule/runs/<run_id>/baseline.json`: baseline measurement report when using `baseline`
- `.joule/runs/<run_id>/baseline_analysis.json`: baseline summary plus optional hotspot analysis
- `.joule/runs/<run_id>/run_summary.json`: human-readable summary for optimization runs
- `.joule/runs/<run_id>/optimization_analysis.json`: funnel, operator, and hotspot analysis for a run
- `.joule/runs/<run_id>/dashboard.html`: HTML dashboard snapshot
- `.joule/runs/<run_id>/best.patch`: diff for the best accepted candidate when one exists
- `.joule/runs/<run_id>/candidates/<candidate_id>/`: per-candidate analysis pack when `--analysis` is enabled

## Documentation

- [QUICKSTART.md](/home/prakhar/dev/prakhar479/hedge/QUICKSTART.md): first successful setup and first run
- [docs/ARCHITECTURE.md](/home/prakhar/dev/prakhar479/hedge/docs/ARCHITECTURE.md): architecture, execution flow, and design decisions
- [GUIDE.md](/home/prakhar/dev/prakhar479/hedge/GUIDE.md): roadmap, scope boundaries, and deferred work

## Notes

- Candidates with new dependencies are stored and visible, but `apply` refuses them in v0.
- Explicit workload selectors are the most reliable way to evaluate async, stateful, or method-bound targets.
- Use `--hotspots` for baseline profiling and `--analysis` for deeper optimization reporting when you want richer artifacts.
- The `mock` backend is best for development and CI-style verification; `rapl` is for hardware-grounded measurements on supported systems.
