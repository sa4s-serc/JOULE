# CLI Reference Manual

The HEDGE command-line interface provides a comprehensive suite of tools for code optimization, analysis, and visualization.

## Core Commands

### `optimize`

Performs evolutionary code optimization on a target file.

**Usage:**
```bash
python hedge.py optimize <target_file> <test_file> [options]
```

**Key Options:**
- `--level <level>`: Presets for optimization depth.
    - `micro`: Local refinements only.
    - `basic`: Micro + Syntactic patterns.
    - `standard`: Basic + Algorithmic data structures.
    - `advanced`: Standard + Semantic LLM integration.
    - `aggressive`: All layers with maximum generations.
- `--layers <layers>`: Comma-separated list of active layers (`semantic`, `algorithmic`, `syntactic`, `micro`).
- `--generations <n>`: Number of evolutionary cycles (default: 5).
- `--population-size <n>`: Number of variants per generation (default: 10).
- `--llm <provider>`: Specify LLM provider (`gemini` or `openai:gpt-4`).
- `--visualize`: Generate HTML reports and charts after completion.
- `--out-dir <dir>`: Specify output directory for experiment results.

### `analyze`

Performs static analysis on the target code to identify optimization opportunities and calculate metrics.

**Usage:**
```bash
python hedge.py analyze <target_file>
```

**Metrics Calculated:**
- Cyclomatic Complexity
- IR Node Density
- Nesting Depth
- Estimated Energy Profile

### `visualize`

Generates visualizations from a previous experiment's raw data.

**Usage:**
```bash
python hedge.py visualize <experiment_directory>
```

### `benchmark`

Runs HEDGE against a suite of standard problems to evaluate system performance.

**Usage:**
```bash
python hedge.py benchmark [--quick] [--compare-levels]
```

### `list-mutators`

Displays all registered mutators and their constituent strategies, organized by layer.

**Usage:**
```bash
python hedge.py list-mutators
```

## Environment Variables

- `GEMINI_API_KEY`: API key for Google Gemini.
- `OPENAI_API_KEY`: API key for OpenAI GPT-4.
- `HEDGE_LOG_LEVEL`: Controls logging verbosity (`DEBUG`, `INFO`, `WARNING`, etc.).

## Output Artifacts

Optimization results are stored in the `experiments/` directory:
- `*_optimized.py`: The single best-performing solution.
- `pareto_results.json`: Set of non-dominated solutions.
- `statistics.json`: Detailed mutation success and layer contribution metrics.
- `visualizations/`: Generated charts and interactive HTML reports.
