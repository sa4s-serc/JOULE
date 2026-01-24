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

### `app`

Starts the HEDGE Interactive Web Interface.

**Usage:**
```bash
python hedge.py app [--port 5173]
```

### `serve`

Starts the HEDGE API server for remote access or web interface integration.

**Usage:**
```bash
python hedge.py serve [--port 8000] [--host 0.0.0.0]
```

## Configuration Files

HEDGE uses a hierarchical YAML-based configuration system. Settings are loaded and merged from the following locations (highest priority first):

1.  **CLI Arguments**: Explicit flags like `--generations` or `--level`.
2.  **Explicit Config**: File passed via `--config`.
3.  **Local Configuration**: `hedge.yaml` in the current working directory.
4.  **Global Configuration**: `~/.hedge/config.yaml`.
5.  **Project Defaults**: `config/default.yaml`.

### Common Configuration Structure
```yaml
optimization:
  default_level: "standard"
  default_generations: 10
  default_population_size: 8

llm:
  default_provider: "gemini"
  gemini:
    model: "gemini-2.0-flash"
  openai:
    model: "gpt-4"
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
