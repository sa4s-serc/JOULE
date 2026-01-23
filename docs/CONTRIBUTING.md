# Contributing to HEDGE

Thank you for your interest in contributing to HEDGE. This document outlines the technical standards and processes for contributing to the framework.

## Development Environment

### 1. Setup
```bash
# Clone and enter repository
git clone <repository-url>
cd HEDGE

# Initialize environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov rich matplotlib
```

### 2. Testing
All contributions must pass the existing test suite and include new tests for added functionality.
```bash
# Run the complete suite
python -m pytest tests/ -v

# Run tests with coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Engineering Standards

### Architecture Compliance
HEDGE follows a strict 3-tier Domain-Driven Design (DDD) pattern:
- **Domain Layer**: Must contain only IR logic and core interfaces. No external dependencies.
- **Application Layer**: Orchestrates evolution, mutation layers, and registry management.
- **Infrastructure Layer**: Implements external concerns such as parsing, codegen, and LLM clients.

### The IR-Only Mandate
Direct string manipulation of Python code is strictly prohibited. All transformations must be implemented as `NodeTransformer` objects operating on the HEDGE IR models (`src/domain/ir/schema.py`). 

## Adding a New Mutator

1.  **Define Strategy**: Identify which of the [four layers](MUTATORS.md) (Semantic, Algorithmic, Syntactic, or Micro) the mutator belongs to.
2.  **Inherit**: Extend the `LayeredMutator` base class.
3.  **Implement**: Override `_apply_mutations(self, ir)` to perform transformations.
4.  **Register**: Add the mutator to the `auto_discover_mutators()` function in `src/application/mutators/registry.py`.
5.  **Document**: Add the new strategies to the comprehensive list in `docs/MUTATORS.md`.

## Submission Process

1.  **Branching**: Use a descriptive branch name: `feat/layer-name`, `fix/issue-description`, or `docs/improvement`.
2.  **Linting**: Ensure code adheres to PEP 8 standards with clear type hints.
3.  **Pull Request**: Submit a detailed PR describing the optimization rationale and performance impact.

---
*For further technical queries, please consult the [Architecture Guide](ARCHITECTURE.md).*
