# Quickstart

This quickstart gets JOULE running locally and walks through one complete example flow.

## 0. Choose Your Intent

- New user: follow sections 1 through 4, then run section 6 artifact checks.
- CI or automation: run sections 1, 2, 5, and 7 with `--output json --no-dashboard`.
- Advanced exploration: include `--analysis` and inspect `events.jsonl` plus candidate packs.

## 1. Install Dev Dependencies

```bash
make install-dev
```

This creates `.venv` and installs the project in editable mode with test tooling.

## 2. Run the Built-In Smoke Example

```bash
make smoke-example
```

This verifies the end-to-end toolchain against [example/mock_repo](example/mock_repo). It runs:

1. `doctor`
2. `baseline`
3. `run`
4. `inspect`
5. `dashboard --once`

If that succeeds, your local environment is ready for normal CLI use.

## 3. Inspect the Example Project Manually

Check environment readiness:

```bash
./joule doctor example/mock_repo
```

Measure a known test-backed baseline:

```bash
./joule baseline \
  example/mock_repo/sample_pkg/algos.py \
  --function membership_total \
  --tests tests/test_algos.py::test_membership_total \
  --hotspots \
  --output json \
  --no-dashboard
```

Run optimization on a simple default-arg function:

```bash
./joule run \
  example/mock_repo/sample_pkg/algos.py \
  --function unreferenced_total \
  --budget 4 \
  --analysis \
  --output human \
  --no-dashboard
```

Run optimization on a richer function with broader transformation surface:

```bash
./joule run \
  example/mock_repo/sample_pkg/algos.py \
  --function optimization_surface_demo \
  --tests tests/test_algos.py::test_optimization_surface_demo \
  --budget 6 \
  --analysis \
  --output human \
  --no-dashboard
```

Inspect the registered transformation catalog:

```bash
./joule transformations example/mock_repo --output human
```

Inspect the run:

```bash
./joule inspect example/mock_repo --run-id <run_id>
```

Render the dashboard HTML to stdout:

```bash
./joule dashboard example/mock_repo --once
```

## 4. Understand the Main Commands

`doctor`
- Validates the local runtime and separates required checks from optional capabilities.

`baseline`
- Measures the selected target against the resolved workloads and writes a baseline report, optional hotspot analysis, and a dashboard snapshot.

`run`
- Runs the optimization flow: baseline measurement, candidate generation, correctness checks, surrogate screening, multi-fidelity evaluation, and optional deep analysis artifacts.

`transformations`
- Lists deterministic, LLM, and escape transformations with tier and precheck metadata.

`inspect`
- Dumps persisted run state including metadata, candidates, measurements, artifacts, and apply audits.

`dashboard`
- Serves or prints a guided HTML view backed by SQLite with run navigation, candidate filters, and recommended next actions.

`parse-json`
- Converts raw JSON command output into concise terminal summaries.

`apply`
- Applies an accepted candidate back to the source file if the target hash still matches and the candidate does not require new dependencies.

## 5. Choose the Right Workload Strategy

Decision flow:

1. Does the target require async orchestration, class state, fixtures, or realistic external inputs?
2. If yes, use explicit selectors (`--tests`, `--properties`, `--harness`).
3. If no, pytest discovery can work when tests are clearly aligned by naming and location.
4. If no tests are available, use default-arg fallback only for pure, simple targets.

Operational guidance:
- Explicit selectors are required for reliable claims on async and stateful targets.
- Default-arg fallback is a convenience path, not a quality path.
- If results look weak or unstable, revisit workload realism before changing optimizer settings.

## 6. Read the Generated Artifacts

After `baseline` or `run`, look for:

```text
<project>/
├── .joule.lock
└── .joule/
    ├── joule.db
    └── runs/
        └── <run_id>/
            ├── baseline.json
            ├── baseline_analysis.json
            ├── run_summary.json
            ├── optimization_analysis.json
            ├── hotspots.json
            ├── dashboard.html
            ├── events.jsonl
            └── best.patch
            └── candidates/
                └── <candidate_id>/...
```

What matters most:
- `.joule.lock` records reproducibility metadata and the config snapshot
- `baseline_analysis.json` captures baseline metrics and optional hotspot profiling
- `run_summary.json` shows the high-level optimization result
- `optimization_analysis.json` summarizes the optimization funnel, operator performance, and hotspot data
- `events.jsonl` stores structured stage-by-stage terminal events for diagnostics and CI scraping
- `best.patch` contains the candidate diff when a best accepted candidate exists
- `dashboard.html` provides a human-readable run snapshot

Need question-based lookup? See [docs/ARTIFACTS.md](docs/ARTIFACTS.md).

## 7. Try JOULE on Another Project

Basic pattern:

```bash
./joule baseline path/to/file.py --function my_function --tests tests/test_file.py::test_my_function
./joule run path/to/file.py --function my_function --tests tests/test_file.py::test_my_function --budget 6
./joule inspect /path/to/project --run-id <run_id>

# Humanized JSON helpers:
./joule run path/to/file.py --function my_function --output json --no-dashboard | ./joule parse-json
./joule discover /path/to/project --output human
```

Use explicit workloads whenever the target needs setup, object state, async orchestration, or meaningful real-world inputs.

## 8. Understand Dependency Policy (v0)

In v0, dependency-bearing candidates are inspectable but not auto-applicable.

- `run` can generate candidates that list new dependencies.
- `inspect` and candidate artifacts show exactly what those dependencies are.
- `apply` refuses those candidates until dependency automation and rollback controls are available.

If you hit this policy, continue with manual review using `best.patch` and candidate packs.

## 9. Known v0 Constraints

- No automatic dependency installation or dependency-file modification
- No background dashboard launch from `run`
- No nested/local function targeting
- Dependency-bearing candidates remain review-only and cannot be applied automatically
- Hotspot profiling and deep optimization analysis are opt-in via `--hotspots` and `--analysis`

## 10. Where to Go Next

Use this map:

- [README.md](README.md): high-level capabilities and command map
- [docs/ARTIFACTS.md](docs/ARTIFACTS.md): file-by-file troubleshooting and lookup
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): internals and data flow
- [docs/TRANSFORMATIONS.md](docs/TRANSFORMATIONS.md): full transformation catalog and snapshot contract
- [GUIDE.md](GUIDE.md): roadmap and deferred scope
