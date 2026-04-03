# Quickstart

This quickstart gets JOULE running locally and walks through one complete example flow.

## 1. Install Dev Dependencies

```bash
make install-dev
```

This creates `.venv` and installs the project in editable mode with test tooling.

## 2. Run the Built-In Smoke Example

```bash
make smoke-example
```

This verifies the end-to-end toolchain against [example/mock_repo](/home/prakhar/dev/prakhar479/hedge/example/mock_repo). It runs:

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
  --no-dashboard
```

Run optimization on a simple default-arg function:

```bash
./joule run \
  example/mock_repo/sample_pkg/algos.py \
  --function unreferenced_total \
  --budget 4 \
  --no-dashboard
```

Inspect the run:

```bash
./joule inspect example/mock_repo <run_id>
```

Render the dashboard HTML to stdout:

```bash
./joule dashboard example/mock_repo --once
```

## 4. Understand the Main Commands

`doctor`
- Validates the local runtime and separates required checks from optional capabilities.

`baseline`
- Measures the selected target against the resolved workloads and writes a baseline report plus dashboard snapshot.

`run`
- Runs the optimization flow: baseline measurement, candidate generation, correctness checks, surrogate screening, and multi-fidelity evaluation.

`inspect`
- Dumps persisted run state including metadata, candidates, measurements, artifacts, and apply audits.

`dashboard`
- Serves or prints an HTML view backed by the SQLite run database.

`apply`
- Applies an accepted candidate back to the source file if the target hash still matches and the candidate does not require new dependencies.

## 5. Choose the Right Workload Strategy

Preferred order:

1. Explicit selectors via `--tests`, `--properties`, or `--harness`
2. Heuristic pytest discovery
3. Safe default-argument fallback when the target can be called without extra state

Guidance:
- Use explicit selectors for async targets when possible.
- Use explicit selectors for class methods that depend on object setup.
- Treat default-arg fallback as a convenience for simple pure functions, not as a replacement for meaningful tests.

## 6. Read the Generated Artifacts

After `baseline` or `run`, look for:

```text
<project>/
├── .joule.lock
└── .joule/
    ├── joule.db
    └── runs/
        └── <run_id>/
            ├── baseline.json or run_summary.json
            ├── dashboard.html
            └── best.patch
```

What matters most:
- `.joule.lock` records reproducibility metadata and the config snapshot
- `run_summary.json` shows the high-level optimization result
- `best.patch` contains the candidate diff when a best accepted candidate exists
- `dashboard.html` provides a human-readable run snapshot

## 7. Try JOULE on Another Project

Basic pattern:

```bash
./joule baseline path/to/file.py --function my_function --tests tests/test_file.py::test_my_function
./joule run path/to/file.py --function my_function --tests tests/test_file.py::test_my_function --budget 6
./joule inspect /path/to/project <run_id>
```

Use explicit workloads whenever the target needs setup, object state, async orchestration, or meaningful real-world inputs.

## 8. Known v0 Constraints

- No automatic dependency installation or dependency-file modification
- No background dashboard launch from `run`
- No nested/local function targeting
- Dependency-bearing candidates remain review-only and cannot be applied automatically

## 9. Where to Go Next

- [README.md](/home/prakhar/dev/prakhar479/hedge/README.md) for the high-level project overview
- [docs/ARCHITECTURE.md](/home/prakhar/dev/prakhar479/hedge/docs/ARCHITECTURE.md) for internals and design
- [GUIDE.md](/home/prakhar/dev/prakhar479/hedge/GUIDE.md) for roadmap and deferred work
