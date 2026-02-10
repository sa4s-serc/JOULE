# HEDGE

**Hierarchical Evolutionary Domain-Guided Engine**

HEDGE is an advanced code optimization framework designed to improve Python code efficiency through evolutionary strategies and hierarchical mutation layers. By operating on a strictly typed Intermediate Representation (IR), HEDGE explores a broad spectrum of optimizations, from compiler-style micro-optimizations to LLM-guided algorithmic refactoring.

---

## Key Features

- **Hierarchical Mutation Architecture**: Operates across four distinct layers: Semantic, Algorithmic, Syntactic, and Micro.
- **LLM-Guided Refactoring**: Leverages state-of-the-art models (GPT-4, Gemini) for high-level semantic transformations and algorithmic improvements.
- **Type-Safe IR System**: All transformations are performed on a Pydantic-validated Intermediate Representation, ensuring structural integrity.
- **Multi-Objective Optimization**: Simultaneously optimizes for execution time and energy consumption, maintaining a Pareto-optimal set of solutions.
- **Automated Validation**: Integrated test suite execution and a self-repair mechanism for AI-generated code snippets.
- **Extensive Visualization**: Generates comprehensive HTML reports, performance charts, and detailed complexity metrics.

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd HEDGE

# Run the automated setup script
python scripts/setup.py
source .venv/bin/activate
```

### Basic Usage

```bash
# Perform standard optimization
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py

# Perform advanced optimization with LLM integration
python hedge.py optimize target.py tests.py --level advanced
```

### Reducing Measurement Noise

To reduce measurement noise when evaluating energy and time, you can run multiple measured iterations per candidate and optionally perform warmup runs:

```bash
# Run 5 measured iterations per candidate to compute a baseline
python hedge.py optimize target.py tests.py --test-iterations 5

# Add warmup runs before each measured run (helps with cache/JIT effects)
python hedge.py optimize target.py tests.py \
  --test-iterations 5 --test-warmup-iterations 10

# Make runs reproducible across iterations (seeds Python and NumPy)
python hedge.py optimize target.py tests.py \
  --test-iterations 5 --test-warmup-iterations 10 --test-seed 42
```

- `--test-iterations N` (1–50): Number of measured iterations per candidate; metrics are aggregated via sum (total energy and time across all iterations).
- `--test-warmup-iterations N` (0–100): Unmeasured warmup runs before each measured run.
- `--test-seed N`: Base seed; per-iteration seed is `base_seed + iteration_index`. Used to seed `random` and (when available) `numpy.random` inside the test harness.

These options are also available via the API under `engine.test_iterations`, `engine.test_warmup_iterations`, and `engine.test_seed`.

### Interactive Web Interface

HEDGE features a modern, interactive web interface for visualizing optimization results, managing experiments, and configuring the engine.

```bash
# Start the web interface (requires Node.js)
python hedge.py app
```

Once started, the interface is accessible at `http://localhost:5173`.

## Optimization Hierarchy

HEDGE utilizes a layered approach to code transformation:

| Layer | Responsibility | Mechanism |
| :--- | :--- | :--- |
| **Semantic** | High-level logic & complexity | LLM Analysis (OpenAI/Gemini) |
| **Algorithmic** | Data structures & access patterns | Logic-based IR Transformers |
| **Syntactic** | Pythonic idioms & code patterns | Pattern-matching Transformers |
| **Micro** | Low-level compiler optimizations | Localised IR Refinement |

## Project Structure

- `cli/`: Command-line interface and command definitions.
- `src/domain/`: Core IR schema, metrics, and abstract interfaces.
- `src/application/`: Optimization engine, mutation layers, and orchestrators.
- `src/infrastructure/`: Parser, code generator, LLM clients, and execution runner.
- `docs/`: Technical documentation and guides.
- `examples/`: Reference problems and performance targets.

## Documentation

For more detailed information, please refer to the following guides:

- [Installation & Configuration](docs/SETUP.md)
- [System Architecture](docs/ARCHITECTURE.md)
- [Mutation & Optimization Layers](docs/MUTATORS.md)
- [CLI Reference Manual](docs/CLI.md)
- [Benchmarks & Performance](evoeval_benchmark/README.md)
- [API Server Documentation](api/README.md)

## Troubleshooting

### Debug Logging

If you encounter issues or want to see detailed information about the optimization process:

**For the API Server:**
```bash
# Run with DEBUG logging
LOG_LEVEL=DEBUG python api/main.py

# Or use the helper script
python scripts/run_api_debug.py
```

Debug logging provides detailed information about:
- Mutation attempts and results with mutator names
- WebSocket message flow
- Event broadcasting
- Merge operations in parallel orchestrator

**For the CLI:**
```bash
# Enable verbose logging
python hedge.py optimize target.py tests.py --verbose
```

### Common Issues

**"Unknown" Mutator Names in Web Interface**

If you see "Unknown" as the mutator name:
1. Enable DEBUG logging: `LOG_LEVEL=DEBUG python api/main.py`
2. Check logs for `[MERGE_DEBUG]` and `[MUTATOR_DEBUG]` messages
3. The system will attempt to infer mutator names from strategy names
4. See [API Server Documentation](api/README.md) for more details

**WebSocket Connection Issues**

1. Verify the API server is running on the expected port (default: 8000)
2. Check CORS settings in `api/main.py`
3. Enable DEBUG logging to see connection events
4. Check browser console for WebSocket errors

---
*Developed by the HEDGE Team*
