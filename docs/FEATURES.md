# HEDGE Feature Capabilities

HEDGE (**Hierarchical Evolutionary Domain-Guided Engine**) provides a robust environment for automated Python code optimization. The system is designed for both research and production-level code refinement.

## Core Optimization Framework

### Unified Intermediate Representation (IR)
- **Typed Architecture**: Built on Pydantic, the IR ensures that all code transformations are structurally valid and type-safe.
- **Independence**: All analysis and mutations are performed on the IR, decoupled from the underlying Python AST.
- **Serialization**: Complete support for IR snapshots in JSON format for debugging and reproducibility.

### Hierarchical Mutation System
Optimizations are partitioned into four layers to balance speed, safety, and complexity:
- **Semantic**: High-level algorithmic shifts and intent-informed refactoring (LLM-guided).
- **Algorithmic**: Efficiency-focused transformations of data structures and access patterns.
- **Syntactic**: Modernization of code using Pythonic idioms, comprehensions, and built-ins.
- **Micro**: Compiler-centric optimizations including constant folding and dead code elimination.

## Intelligent Selection & Evolution

### Multi-Objective Optimization
HEDGE maintains a **Pareto front** of solutions, evaluating candidates based on:
- **Energy Efficiency**: Instrumented measurement via `CodeCarbon`.
- **Execution Latency**: Precise performance timing.
- **Code Complexity**: Static analysis of the resulting IR.

### Self-Repairing AI Integration
When utilizing LLMs (Gemini/GPT-4o) for semantic optimizations:
- **Automated Verification**: Generated code is parsed and validated against the IR schema.
- **Closed-Loop Repair**: Syntax errors and test failures are fed back to the LLM for iterative correction (up to 3 retries).

## Execution & Analysis

### Green Gym (Sandboxed Execution)
- safe execution of code variants within a specialized runner.
- Built-in protection against infinite loops and resource exhaustion.
- Automated test suite verification to ensure semantic preservation.

### Advanced Visualization
- **Pareto Front Mapping**: Visual trade-offs between energy and speed.
- **Evolutionary Trajectory**: Tracking of fitness improvement over generations.
- **Layer Contribution Analysis**: Breakdown of which mutation layer provided the most benefit.
- **Interactive Reports**: Standalone HTML reports containing all metrics and code diffs.

## Enterprise Features

### Project Management
- **Scaffolding**: Initialize structured optimization projects with templates.
- **Governance**: Clear organization of experiment history and logs.
- **Portability**: YAML-based configuration with environment variable overrides.

### Extensibility
- **Plugin Architecture**: Developers can register custom mutators, custom runners, and new metrics.
- **API-First Design**: All HEDGE capabilities are accessible via a clean Python API.

---
*For implementation specifics, refer to the [Architecture Guide](ARCHITECTURE.md).*