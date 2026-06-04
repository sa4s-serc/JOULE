# JOULE Large Repository Experiment

This experiment runs JOULE optimization on three large Python repositories (black, networkx, sympy) using a hotspot-focused strategy to identify and optimize high-impact functions.

## Quick Start

### Prerequisites

- Python 3.10+
- JOULE source code (hedge repository)
- Git (for cloning repositories)
- Virtual environment support

### Setup

1. Clone this experiment directory:
```bash
git clone <experiment-repo> joule-experiment
cd joule-experiment
```

2. Set environment variables if needed:
```bash
export JOULE_SRC=/path/to/hedge  # Path to JOULE source
export EXPERIMENT_ROOT=$(pwd)    # Experiment directory
```

3. Run the complete experiment:
```bash
./scripts/run_experiment.sh
```

### Running Individual Phases

You can run individual phases for debugging or resumption:

```bash
# Phase 1: Setup and environment preparation
./scripts/01_setup.sh

# Phase 2: Discovery
./scripts/02_discover.sh

# Phase 3: Hotspot selection
python3 scripts/03_select_hotspots.py --repo black --sample-size 80
# Optional: override paths if running from outside the experiment directory
# python3 scripts/03_select_hotspots.py --repo black --results-dir /path/to/results --repos-dir /path/to/repos

# Phase 4: Hotspot baseline
./scripts/04_hotspot_baseline.sh black ../results/hotspots/black_sample_targets.csv

# Phase 5: Top hotspot identification
python3 scripts/05_identify_top_hotspots.py --repo black --limit 30

# Phase 6: Final baseline
./scripts/06_final_baseline.sh black ../results/final_baselines/black_top_hotspots.csv

# Phase 7: Optimization
./scripts/07_optimize.sh black ../results/final_baselines/black_top_hotspots.csv 10

# Phase 8: Analysis
python3 scripts/08_analyze_results.py --repos "black networkx sympy"

# Phase 9: Report generation
./scripts/09_generate_report.sh
```

### Resuming from a Specific Phase

```bash
# Start from phase 4 (skip phases 1-3)
./scripts/run_experiment.sh --start-phase 4

# Run only phase 7
./scripts/run_experiment.sh --phase 7
```

## Configuration

Configuration is managed through `scripts/experiment_config.sh`. You can override settings using environment variables:

```bash
# Example: Override JOULE profile and budget
export JOULE_PROFILE=thorough
export OPTIMIZATION_BUDGET=15
export SAMPLE_SIZE=100
export TOP_HOTSPOTS_LIMIT=25

./scripts/run_experiment.sh
```

### RAPL vs Mock Energy Backend

By default the experiment uses the `mock` backend, which generates synthetic energy values — useful for validating the pipeline works, but **not valid for energy claims**.

To get real energy measurements, enable RAPL:
```bash
# Check RAPL is available on your machine first
cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj

# Then run with real backend
export JOULE_BACKEND=rapl
./scripts/run_experiment.sh
```

RAPL requires a Linux machine with Intel/AMD CPU and the `powercap` module enabled. If `energy_uj` is not readable, you need either `sudo chmod a+r /sys/class/powercap/intel-rapl/*/energy_uj` or to run as root.

### Key Configuration Options

- `JOULE_SRC`: Path to JOULE source directory
- `JOULE_PROFILE`: JOULE profile (thorough, fast, etc.)
- `JOULE_BACKEND`: Energy backend (rapl, mock)
- `OPTIMIZATION_BUDGET`: Optimization budget (default: 10)
- `SAMPLE_SIZE`: Number of functions to sample for hotspot analysis (default: 80)
- `TOP_HOTSPOTS_LIMIT`: Number of top hotspots to optimize (default: 30)
- `MAX_PARALLEL_BASELINES`: Max concurrent baseline runs (default: 4)
- `MAX_PARALLEL_OPTIMIZATIONS`: Max concurrent optimizations (default: 2)

## Experiment Phases

### Phase 1: Setup and Environment Preparation
- Creates virtual environments for each repository
- Installs JOULE in development mode
- Configures JOULE settings for each repo
- Verifies runtime with `doctor` command

### Phase 2: Discovery
- Runs JOULE discover on each repository
- Identifies all optimizable functions
- Outputs discovery JSON files

### Phase 3: Hotspot Selection
- Selects diverse sample of functions (80 per repo)
- Outputs sample targets CSV for baseline processing
- Ensures coverage across different modules

### Phase 4: Hotspot Baseline
- Runs baseline with `--hotspots` on sampled functions
- Measures runtime hotspots for each function
- Outputs hotspot analysis results

### Phase 5: Top Hotspot Identification
- Aggregates hotspot data across all sampled functions
- Identifies top 20-30 hotspots by runtime impact
- Outputs top hotspots CSV for final processing

### Phase 6: Final Baseline
- Runs focused baseline on identified top hotspots
- Uses thorough profile settings
- Establishes accurate baselines for optimization

### Phase 7: Optimization
- Runs optimization on top hotspots (budget=10)
- Uses thorough profile with analysis enabled
- Outputs optimization results and artifacts

### Phase 8: Analysis
- Aggregates results across all repositories
- Calculates success metrics and improvement statistics
- Generates comprehensive analysis JSON

### Phase 9: Report Generation
- Compiles experiment report with all results
- Includes configuration, metrics, and recommendations
- Outputs markdown report

## Directory Structure

```
joule-experiment/
├── repos/
│   ├── black/
│   ├── networkx/
│   └── sympy/
├── results/
│   ├── discovery/
│   │   ├── black_discovery.json
│   │   ├── networkx_discovery.json
│   │   └── sympy_discovery.json
│   ├── hotspots/
│   │   ├── black_sample_targets.csv
│   │   ├── black_sample_baselines/
│   │   ├── networkx_sample_targets.csv
│   │   ├── networkx_sample_baselines/
│   │   └── sympy_sample_targets.csv
│   ├── final_baselines/
│   │   ├── black_top_hotspots.csv
│   │   ├── black_hotspot_baselines/
│   │   ├── networkx_top_hotspots.csv
│   │   └── sympy_top_hotspots.csv
│   ├── optimizations/
│   │   ├── black_optimizations/
│   │   ├── networkx_optimizations/
│   │   └── sympy_optimizations/
│   └── analysis/
│       └── aggregated_results.json
├── scripts/
│   ├── experiment_config.sh
│   ├── 01_setup.sh
│   ├── 02_discover.sh
│   ├── 03_select_hotspots.py
│   ├── 04_hotspot_baseline.sh
│   ├── 05_identify_top_hotspots.py
│   ├── 06_final_baseline.sh
│   ├── 07_optimize.sh
│   ├── 08_analyze_results.py
│   ├── 09_generate_report.sh
│   └── run_experiment.sh
├── report/
│   └── experiment_report.md
├── logs/
│   └── experiment.log
└── README.md
```

## Running on a Different Machine

To run this experiment on a different machine:

1. Copy the entire experiment directory:
```bash
scp -r joule-experiment user@remote-machine:/path/to/
```

2. On the remote machine, set up JOULE source:
```bash
cd /path/to/joule-experiment
export JOULE_SRC=/path/to/hedge  # Adjust to your JOULE source location
```

3. Run the experiment:
```bash
./scripts/run_experiment.sh
```

The scripts use relative paths and environment variables, making them portable across machines.

## Troubleshooting

### JOULE doctor fails
- Ensure JOULE is installed in development mode: `cd ${JOULE_SRC} && make install-dev`
- Check Python version compatibility (requires 3.10+)
- Verify RAPL backend availability or fall back to mock

### Discovery finds no functions
- Check that repository is properly installed
- Verify JOULE configuration in pyproject.toml
- Review JOULE logs for specific errors

### Baseline runs timeout
- Increase `WORKLOAD_TIMEOUT_S` in experiment_config.sh
- Reduce `MAX_PARALLEL_BASELINES` to limit concurrent runs
- Check system resources (CPU, memory)

### Optimization fails frequently
- Increase `OPTIMIZATION_BUDGET` for difficult functions
- Review failure reasons in optimization logs
- Check test coverage and workload quality

## Logs

All scripts log to `logs/experiment.log` with timestamps and log levels. Check this file for debugging information.

## Results

After completion, review:
- Experiment report: `report/experiment_report.md`
- Aggregated analysis: `results/analysis/aggregated_results.json`
- Individual optimization results: `results/optimizations/*/`

## License

This experiment setup is part of the JOULE project. See the JOULE repository for license information.
