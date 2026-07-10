# Examples Guide

This catalog explains the expanded JOULE example set and when to use each target.

## Complexity Tiers

| Tier | Target | Path | Workload Selector | Expected Behavior |
|---|---|---|---|---|
| Basic | `membership_total` | `example/mock_repo/sample_pkg/algos.py` | `--tests tests/test_algos.py::test_membership_total` | Fast baseline and simple deterministic optimization surface |
| Basic | `unreferenced_total` | `example/mock_repo/sample_pkg/algos.py` | default fallback or explicit tests | Good candidate for quick run/apply demos |
| Intermediate | `optimization_surface_demo` | `example/mock_repo/sample_pkg/algos.py` | `--tests tests/test_algos.py::test_optimization_surface_demo` | Multiple deterministic operator opportunities |
| Intermediate | `string_concat_report` | `example/mock_repo/sample_pkg/algos.py` | `--tests tests/test_algos.py::test_string_concat_report` | String and loop-focused rewrites |
| Intermediate | `counter_histogram` | `example/mock_repo/sample_pkg/algos.py` | `--tests tests/test_algos.py::test_counter_histogram` or property selector | Collection-heavy rewrite opportunities |
| Intermediate | `local_import_json_encode` | `example/mock_repo/sample_pkg/algos.py` | `--tests tests/test_algos.py::test_local_import_json_encode` | Demonstrates local import hoisting behavior |
| Advanced | `warehouse_balancing_pipeline` | `example/mock_repo/sample_pkg/complex_cases.py` | `--tests tests/test_complex_cases.py::test_warehouse_balancing_pipeline` | Very large function with nested control flow |
| Advanced | `telemetry_triage_pipeline` | `example/mock_repo/sample_pkg/complex_cases.py` | `--tests tests/test_complex_cases.py::test_telemetry_triage_pipeline` | Very large function with rolling windows and scoring |
| Edge Case | `impure_inventory_trace` | `example/mock_repo/sample_pkg/edge_cases.py` | explicit tests only | Target resolution rejects as impure for optimization |
| Edge Case | `recursive_inventory_checksum` | `example/mock_repo/sample_pkg/edge_cases.py` | explicit tests only | Valid for measurement demos and recursion-heavy baseline experiments |

## Suggested Demo Paths

### 1. Quick End-To-End

```bash
./joule baseline \
  example/mock_repo/sample_pkg/algos.py \
  --function membership_total \
  --tests tests/test_algos.py::test_membership_total \
  --hotspots --no-dashboard

./joule run \
  example/mock_repo/sample_pkg/algos.py \
  --function unreferenced_total \
  --budget 4 \
  --analysis --no-dashboard
```

### 2. Batch Processing

```bash
./joule batch \
  example/mock_repo/sample_pkg/ \
  --budget 4 \
  --parallel 2 \
  --verbose
```

### 3. Intermediate Transformation Mix

```bash
./joule run \
  example/mock_repo/sample_pkg/algos.py \
  --function optimization_surface_demo \
  --tests tests/test_algos.py::test_optimization_surface_demo \
  --budget 6 --analysis --no-dashboard
```

### 3. Advanced Large-Function Baseline

```bash
./joule baseline \
  example/mock_repo/sample_pkg/complex_cases.py \
  --function warehouse_balancing_pipeline \
  --tests tests/test_complex_cases.py::test_warehouse_balancing_pipeline \
  --no-dashboard
```

### 4. Edge-Case Guardrails

```bash
./joule baseline \
  example/mock_repo/sample_pkg/edge_cases.py \
  --function impure_inventory_trace \
  --tests tests/test_edge_cases.py::test_impure_inventory_trace
```

The command above is expected to fail because impure targets are intentionally guarded.

## Operator-Oriented Targets

| Operator Family | Good Targets |
|---|---|
| Loop/comprehension rewrites | `unreferenced_total`, `optimization_surface_demo`, `telemetry_triage_pipeline` |
| Membership and container rewrites | `membership_total`, `sort_then_membership`, `counter_histogram` |
| Import and hoisting rewrites | `local_import_json_encode`, `warehouse_balancing_pipeline` |
| Aggregation and reduction rewrites | `counter_histogram`, `tuple_unpack_accumulator`, `warehouse_balancing_pipeline` |
| String-focused rewrites | `string_concat_report`, `optimization_surface_demo` |

## Verification Commands

```bash
python -m pytest example/mock_repo/tests -q
python -m pytest tests/test_discovery.py tests/test_cli_baseline.py tests/test_run.py -q
make smoke-example
```
