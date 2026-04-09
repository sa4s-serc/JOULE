# Architecture and Design

This document explains how JOULE is structured today, how a run moves through the system, and which design decisions define the current v0.

## 1. System Overview

JOULE treats Python optimization as a measured search problem:

1. Resolve a target function or method
2. Resolve workloads that can exercise that target
3. Measure the baseline
4. Generate candidate refactors
5. Reject invalid candidates early through correctness and surrogate checks
6. Measure promising candidates through increasing fidelity
7. Persist everything to SQLite and artifact files
8. Optionally profile hotspot behavior and optimization-process metrics
9. Optionally apply an accepted candidate back to source

The system is intentionally local-first and artifact-driven. The database is the durable state store, while run directories hold human-facing outputs and snapshots.

## 2. Main Subsystems

### CLI layer

Primary entrypoint: [src/joule/cli.py](/home/prakhar/dev/prakhar479/hedge/src/joule/cli.py)

Responsibilities:
- bootstrap settings, artifact directories, database, and terminal reporting
- expose end-user commands: `doctor`, `baseline`, `run`, `apply`, `discover`, `dashboard`, `inspect`
- emit `.joule.lock` and run artifact files
- gate optional `--hotspots` and `--analysis` workflows for deeper reporting
- enforce v0 policies such as dependency-bearing candidates being review-only

### Config and artifact layer

Primary files:
- [src/joule/config.py](/home/prakhar/dev/prakhar479/hedge/src/joule/config.py)
- [src/joule/utils/artifacts.py](/home/prakhar/dev/prakhar479/hedge/src/joule/utils/artifacts.py)

Responsibilities:
- load `tool.joule` settings from project `pyproject.toml`
- derive artifact and database paths
- generate run ids
- write `.joule.lock` with reproducibility and configuration metadata

### Discovery and workload resolution

Primary files:
- [src/joule/discovery/resolver.py](/home/prakhar/dev/prakhar479/hedge/src/joule/discovery/resolver.py)
- [src/joule/discovery/workloads.py](/home/prakhar/dev/prakhar479/hedge/src/joule/discovery/workloads.py)
- [src/joule/discovery/profiler.py](/home/prakhar/dev/prakhar479/hedge/src/joule/discovery/profiler.py)
- [src/joule/discovery/synthesizer.py](/home/prakhar/dev/prakhar479/hedge/src/joule/discovery/synthesizer.py)
- [src/joule/discovery/purity.py](/home/prakhar/dev/prakhar479/hedge/src/joule/discovery/purity.py)

Responsibilities:
- resolve supported targets: top-level sync functions, top-level async functions, class methods
- reject impure or unsupported targets early
- prefer explicit workload selectors
- heuristically discover pytest workloads
- fall back to safe default-argument invocation when appropriate

Design notes:
- Nested/local functions are intentionally out of scope for v0.
- Async targets are supported, but meaningful evaluation is usually strongest with explicit workloads.
- Purity analysis is heuristic and conservative.

### Runtime and correctness

Primary files:
- [src/joule/runtime.py](/home/prakhar/dev/prakhar479/hedge/src/joule/runtime.py)
- [src/joule/evaluators/correctness.py](/home/prakhar/dev/prakhar479/hedge/src/joule/evaluators/correctness.py)
- [src/joule/integrations/libcst_tools.py](/home/prakhar/dev/prakhar479/hedge/src/joule/integrations/libcst_tools.py)

Responsibilities:
- execute workloads in subprocesses
- normalize imports and overlay paths for candidate execution
- support sync and async callables
- patch only the target function or method while preserving the rest of the module

Design notes:
- Candidate correctness uses overlay materialization instead of editing the original project during evaluation.
- LibCST-based replacement preserves the surrounding module better than raw string editing.

### Measurement backends

Primary files:
- [src/joule/evaluators/oracle.py](/home/prakhar/dev/prakhar479/hedge/src/joule/evaluators/oracle.py)
- [src/joule/evaluators/backends/mock.py](/home/prakhar/dev/prakhar479/hedge/src/joule/evaluators/backends/mock.py)
- [src/joule/evaluators/backends/rapl.py](/home/prakhar/dev/prakhar479/hedge/src/joule/evaluators/backends/rapl.py)

Responsibilities:
- calibrate inner repetitions
- measure workloads across fidelity stages
- aggregate per-sample metrics into run-level reports
- abstract energy measurements behind backend interfaces

Current backend behavior:
- `mock`: derives an energy estimate from CPU time, wall time, and memory
- `rapl`: reads Intel RAPL counters when available

Design notes:
- The adaptive repetition logic is meant to stabilize fast workloads without requiring massive outer repetition counts.
- Backend abstraction is intentionally small so new backends can slot in later.

### Hotspot profiling

Primary files:
- [src/joule/runtime.py](/home/prakhar/dev/prakhar479/hedge/src/joule/runtime.py)
- [src/joule/evaluators/oracle.py](/home/prakhar/dev/prakhar479/hedge/src/joule/evaluators/oracle.py)
- [src/joule/utils/analysis.py](/home/prakhar/dev/prakhar479/hedge/src/joule/utils/analysis.py)

Responsibilities:
- run an opt-in profiling pass after baseline measurement
- capture cumulative-time and ownership summaries from the worker subprocess
- persist hotspot payloads per workload and as a merged run summary

Design notes:
- Hotspot profiling is separated from measurement so it does not distort baseline latency or energy results.
- v1 focuses on function-level and ownership-level hotspots, not a full trace UI or flamegraph server.

### Optimization engine

Primary files:
- [src/joule/orchestrator/mfbo.py](/home/prakhar/dev/prakhar479/hedge/src/joule/orchestrator/mfbo.py)
- [src/joule/orchestrator/pareto.py](/home/prakhar/dev/prakhar479/hedge/src/joule/orchestrator/pareto.py)
- [src/joule/orchestrator/explainer.py](/home/prakhar/dev/prakhar479/hedge/src/joule/orchestrator/explainer.py)
- [src/joule/surrogate/gp.py](/home/prakhar/dev/prakhar479/hedge/src/joule/surrogate/gp.py)
- [src/joule/transformers/registry.py](/home/prakhar/dev/prakhar479/hedge/src/joule/transformers/registry.py)
- [src/joule/transformers/deterministic.py](/home/prakhar/dev/prakhar479/hedge/src/joule/transformers/deterministic.py)
- [src/joule/transformers/generative.py](/home/prakhar/dev/prakhar479/hedge/src/joule/transformers/generative.py)

Responsibilities:
- run the optimization loop
- rank operators
- generate candidate source variants
- screen candidates using correctness and surrogate logic
- promote or reject candidates across `F1`, `F2`, and `F3`
- summarize accepted or rejected outcomes
- persist search events and per-candidate analysis metadata for optional deep analysis

Current design limitations:
- Search still expands from the baseline instead of true iterative parent selection from the Pareto front.
- The surrogate is lightweight and feature-based, not a fully modeled GP stack.
- Dependency-bearing candidates are visible but not automatically actionable.

### Persistence and reporting

Primary files:
- [src/joule/utils/db.py](/home/prakhar/dev/prakhar479/hedge/src/joule/utils/db.py)
- [src/joule/utils/reporting.py](/home/prakhar/dev/prakhar479/hedge/src/joule/utils/reporting.py)
- [src/joule/dashboard/app.py](/home/prakhar/dev/prakhar479/hedge/src/joule/dashboard/app.py)

Responsibilities:
- persist runs, workloads, candidates, measurements, artifacts, apply audits, and operator stats
- persist search events and hotspot profiles
- shape textual and JSON reports
- serve a simple HTML dashboard backed by SQLite

Design notes:
- SQLite is the system of record for run state.
- Run directories are convenience artifacts for operator workflows and debugging.
- The dashboard is deliberately simple in v0: it favors inspectability over UI sophistication, while now surfacing funnel and hotspot summaries.

## 3. End-to-End Command Flows

### `baseline`

1. Load settings and initialize artifacts
2. Resolve target and workloads
3. Write `.joule.lock`
4. Create a run record in SQLite
5. Measure the baseline at `F3`
6. Optionally profile hotspots from the resolved workloads
7. Persist results and render a dashboard snapshot

### `run`

1. Do the same setup and target/workload resolution as `baseline`
2. Measure the baseline
3. Rank operators and generate candidate sources
4. Run syntax and correctness checks in an overlay
5. Run surrogate screening
6. Measure promising candidates through `F1`, `F2`, `F3`
7. Persist candidate metadata, measurements, provenance, explanations, and search events
8. Optionally persist deeper per-candidate artifacts and hotspot summaries
9. Write run summary and dashboard snapshot

### `apply`

1. Load the run and candidate from SQLite
2. Verify the current target file hash matches the measured run
3. Refuse candidates with dependency requirements
4. Patch the target in place using LibCST-guided replacement
5. Optionally create a branch and commit the result
6. Persist an apply audit

## 4. Data Model

### TargetSpec

Key fields:
- `module`
- `file_path`
- `function_name`
- `qualname`
- `owner_path`
- `is_async`
- `metadata`

Why it matters:
- `owner_path` allows class methods to be patched and imported correctly
- `qualname` improves clarity in inspection and diagnostics
- `metadata` carries purity and target-kind annotations

### WorkloadSpec and WorkloadBundle

Each workload includes:
- kind: `pytest`, `property`, `harness`, or `golden_trace`
- selector
- provenance metadata

The bundle adds:
- notes about how resolution happened
- workload ordering already reflecting JOULE’s preference rules

### Run metadata

Run metadata includes:
- source and file hashes
- selected backend
- config snapshot
- workload provenance
- lockfile path

This is what makes runs reproducible and inspectable after the fact.

## 5. Artifact Model

JOULE writes two kinds of output:

### Persistent state

Stored in SQLite:
- runs
- workloads
- candidates
- measurements
- artifacts
- apply audits
- operator statistics

### Human-facing artifacts

Stored in `.joule/`:
- `.joule.lock`
- `baseline.json`
- `baseline_analysis.json`
- `run_summary.json`
- `optimization_analysis.json`
- `hotspots.json`
- `dashboard.html`
- `best.patch`
- `best_candidate.py`
- `candidates/<candidate_id>/...` when `--analysis` is enabled

## 6. Design Decisions

### Local-first execution

Why:
- easier debugging
- no service dependency
- easier reproducibility for operators

Tradeoff:
- less centralized coordination and fewer multi-user workflows

### Explicit workloads over inference

Why:
- performance claims are only meaningful when the workload is meaningful
- async and stateful targets are hard to infer safely

Tradeoff:
- more manual input for complex cases

### Review-only dependency policy

Why:
- automatic dependency edits are high-risk without rollback and audit support

Tradeoff:
- some promising candidates cannot be auto-applied yet

### SQLite as the primary state store

Why:
- simple deployment model
- easy local querying and dashboard integration
- good enough for current v0 scale

Tradeoff:
- not built for distributed scheduling or high-concurrency orchestration

## 7. Known Limitations

- Heuristic pytest alignment can miss meaningful tests or rank them imperfectly
- Purity checks are static and incomplete
- The dashboard is a snapshot/table view rather than a full visual explorer
- Search depth is still shallow compared with the longer-term roadmap
- The `mock` backend is useful for development, not for hardware-truth claims

## 8. Near-Term Evolution

Expected next architecture steps:

1. True iterative search from accepted Pareto parents
2. Better lineage tracking between candidates
3. Stronger surrogate features and operator analytics
4. Richer dashboard exploration
5. Safer dependency automation once rollback and policy handling exist

## 9. Related Docs

- [README.md](/home/prakhar/dev/prakhar479/hedge/README.md)
- [QUICKSTART.md](/home/prakhar/dev/prakhar479/hedge/QUICKSTART.md)
- [GUIDE.md](/home/prakhar/dev/prakhar479/hedge/GUIDE.md)
