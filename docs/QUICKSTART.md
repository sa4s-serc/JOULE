# Quick Start Guide

This guide provides a rapid introduction to optimizing code with HEDGE.

## Installation

### Automated Setup
The recommended way to install HEDGE is using the provided setup script:

```bash
git clone <repository-url>
cd HEDGE
python scripts/setup.py
source .venv/bin/activate
```

## Running Your First Optimization

HEDGE requires a **target file** (the code to optimize) and a **test file** (to verify correctness).

### Basic Optimization
Run HEDGE with standard settings on the Fibonacci example:

```bash
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py
```

### AI-Powered Optimization
For more significant transformations (e.g., recursive to iterative), enable the advanced level (requires a [configured API key](SETUP.md)):

```bash
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py --level advanced
```

## Optimization Workflow

1.  **Analyze**: Evaluate code complexity before starting.
    ```bash
    python hedge.py analyze my_code.py
    ```
2.  **Optimize**: Run the evolutionary engine.
    ```bash
    python hedge.py optimize my_code.py my_tests.py --level standard --visualize
    ```
3.  **Review**: Examine the Pareto front and the best solution.
    -   The best code is saved as `my_code_optimized.py`.
    -   Detailed metrics are available in the `experiments/` directory.

## Common Command Presets

| Objective | Command |
| :--- | :--- |
| **Fastest Run** | `python hedge.py optimize <target> <test> --level micro` |
| **Balanced** | `python hedge.py optimize <target> <test> --level standard` |
| **Deep Research** | `python hedge.py optimize <target> <test> --level aggressive --visualize` |
| **System Check** | `python hedge.py benchmark --quick` |

---
*For detailed configuration, see [SETUP.md](SETUP.md). For command details, see [CLI.md](CLI.md).*