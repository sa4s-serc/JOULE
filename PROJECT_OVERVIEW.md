# HEDGE: Comprehensive Project Overview & Documentation

**Hierarchical Evolutionary Domain-Guided Engine**

## Table of Contents
1. [Project Overview](#project-overview)
2. [Core Philosophy & Objectives](#core-philosophy--objectives)
3. [System Architecture](#system-architecture)
4. [Technical Components](#technical-components)
5. [Optimization Hierarchy](#optimization-hierarchy)
6. [Features & Capabilities](#features--capabilities)
7. [Installation & Setup](#installation--setup)
8. [Usage Guide](#usage-guide)
9. [API Reference](#api-reference)
10. [Configuration](#configuration)
11. [Development & Extension](#development--extension)
12. [Performance Metrics & Evaluation](#performance-metrics--evaluation)

---

## Project Overview

HEDGE is an advanced Python code optimization framework designed to improve software efficiency through a combination of evolutionary algorithms, artificial intelligence, and hierarchical transformation layers. The system operates on a strictly-typed Intermediate Representation (IR) to ensure semantic correctness while exploring a broad spectrum of optimizations.

### Key Characteristics

- **Multi-Layer Architecture**: Operates across four distinct optimization layers (Semantic, Algorithmic, Syntactic, Micro)
- **LLM-Integrated**: Leverages state-of-the-art language models (GPT-4, Gemini) for intelligent refactoring
- **Evolutionary Approach**: Uses population-based optimization to explore solution spaces
- **Type-Safe IR**: All mutations performed on Pydantic-validated intermediate representation
- **Multi-Objective**: Simultaneously optimizes for speed (latency) and efficiency (energy consumption)
- **Automated Testing**: Built-in verification through test suite integration
- **Reproducible**: JSON-serializable IR snapshots enable debugging and reproducibility

### Target Use Cases

1. **Research**: Code optimization benchmarks and algorithm exploration
2. **Production**: Automated performance improvements for existing Python codebases
3. **Education**: Understanding evolutionary optimization and code transformation techniques
4. **Energy Efficiency**: Green computing initiatives measuring and improving energy consumption
5. **Benchmarking**: Evaluating system against standardized problem sets (EvoEval benchmark)

---

## Core Philosophy & Objectives

### Philosophy

HEDGE is built on the principle that **code optimization should be both systematic and intelligent**. Rather than applying ad-hoc transformations, the system:

1. **Maintains Structural Integrity**: All transformations validated against the IR schema
2. **Preserves Semantics**: Test suite execution ensures functional correctness
3. **Balances Tradeoffs**: Maintains Pareto-optimal solutions for speed vs. energy
4. **Leverages AI**: Integrates LLMs for domain knowledge that algorithms cannot capture alone
5. **Measures Impact**: Comprehensive metrics on execution time and energy consumption

### Design Objectives

| Objective | Implementation |
|-----------|-----------------|
| **Safety** | IR validation, test execution, self-repair for AI-generated code |
| **Scope** | Four hierarchical layers handling different optimization classes |
| **Intelligence** | LLM integration for semantic-level transformations |
| **Visibility** | Extensive logging, visualization, and reporting capabilities |
| **Extensibility** | Plugin architecture for custom mutators and metrics |
| **Automation** | End-to-end pipeline from source to optimized code |

---

## System Architecture

### Design Pattern: Domain-Driven Design (DDD)

HEDGE is organized into three primary layers following DDD principles:

```
┌──────────────────────────────────────────────────────────┐
│                    CLI / API / Web Interface              │
├──────────────────────────────────────────────────────────┤
│                  Application Layer (Orchestration)        │
│  - Evolutionary Engine  - Mutation Registry             │
│  - Mutation Hierarchy   - Fitness Evaluation             │
├──────────────────────────────────────────────────────────┤
│                      Domain Layer (Core)                  │
│  - IR Schema & Models  - Metrics & Analytics             │
│  - Interface Definitions - Type Definitions              │
├──────────────────────────────────────────────────────────┤
│                 Infrastructure Layer (I/O)               │
│  - Parser & Codegen    - Execution Runner               │
│  - LLM Clients         - Energy Monitoring               │
└──────────────────────────────────────────────────────────┘
```

### 1. Domain Layer (`src/domain/`)

**Purpose**: Define the core data structures and abstract interfaces

**Components**:
- **IR Schema** (`ir.py`): Pydantic models representing Python constructs
  - `Module`: Top-level Python module
  - `FunctionDef`: Function definitions
  - `Assign`: Variable assignments
  - `For`, `While`, `If`: Control flow structures
  - Expressions, operators, literals, and more

- **Metrics** (`metrics.py`): Static analysis calculations
  - Cyclomatic complexity
  - Nesting depth
  - IR node density
  - Code size estimates

- **Interfaces** (`base.py`): Abstract base classes
  - `Mutator`: Base class for all mutation strategies
  - `ExecutionRunner`: Interface for code execution
  - `LLMClient`: Interface for language model integration
  - `MetricsCalculator`: Interface for fitness evaluation

### 2. Application Layer (`src/application/`)

**Purpose**: Orchestrate optimization workflows and implement transformation logic

**Key Components**:

#### Evolutionary Engine
- Manages population of candidate solutions
- Selection mechanisms (tournament, fitness-proportionate)
- Reproduction cycles with crossover and mutation
- Pareto archive maintenance for multi-objective optimization

#### Mutation Hierarchy

```
┌─────────────────────────────────────────┐
│      Semantic Layer (High-Level)        │
│  - Algorithmic shifts (e.g., O(n)→O(1)) │
│  - Program intent analysis              │
│  - LLM-driven transformations           │
├─────────────────────────────────────────┤
│    Algorithmic Layer (Data Structures)  │
│  - Membership optimization              │
│  - Search & access patterns             │
│  - Complexity reduction                 │
├─────────────────────────────────────────┤
│   Syntactic Layer (Pythonic Patterns)   │
│  - List/dict comprehensions             │
│  - Built-in functions                   │
│  - Iterator optimization                │
├─────────────────────────────────────────┤
│    Micro Layer (Compiler Techniques)    │
│  - Constant folding                     │
│  - Dead code elimination                │
│  - Loop unrolling                       │
└─────────────────────────────────────────┘
```

#### Mutator Registry
- Central registry of all available mutators
- Adaptive selection based on mutation success rates
- Layer-specific organization for targeted optimization

### 3. Infrastructure Layer (`src/infrastructure/`)

**Purpose**: Interface with external systems and the physical environment

**Components**:
- **Parser** (`parser.py`): High-fidelity Python AST → IR conversion
- **Codegen** (`codegen.py`): IR → Python source code generation
- **Execution Runner** (`runner.py`): Sandboxed code execution with:
  - Timeout protection
  - Resource limits
  - Energy monitoring via CodeCarbon
  - Test result verification
- **LLM Clients** (`llm_clients.py`): Typed interfaces for:
  - OpenAI GPT-4 / GPT-4o
  - Google Gemini API
  - Self-repair loop for syntax correction

---

## Technical Components

### Intermediate Representation (IR)

The IR is the central abstraction in HEDGE, enabling:
- **Type Safety**: Pydantic validation of all Python constructs
- **Serialization**: JSON snapshots for reproducibility and debugging
- **Independence**: Decouples analysis from Python's native AST
- **Composability**: Complex transformations via IR node manipulation

**Example IR Structure**:
```python
Module(
    body=[
        FunctionDef(
            name="calculate",
            args=Arguments(args=[arg(name="n")]),
            body=[
                Assign(
                    targets=[Name(id="result")],
                    value=Constant(value=0)
                ),
                For(
                    target=Name(id="i"),
                    iter=Call(func=Name(id="range"), args=[Name(id="n")]),
                    body=[...],
                    orelse=[]
                )
            ]
        )
    ]
)
```

### Evolutionary Optimization Loop

The core algorithm follows this structured workflow:

```
1. Parse Source Code
   └→ Convert to IR
   └→ Establish Baseline (latency, energy, complexity)

2. Initialize Population
   └→ Create N random mutations of the IR

3. Evolutionary Cycles (per generation):
   a. Selection → Select parent solutions using fitness-biased tournament
   b. Mutation → Apply 1-3 mutations from different layers
   c. Validation → Check structural soundness via IR schema
   d. Codegen → Convert mutated IR back to Python
   e. Execution → Run test suite and measure metrics
   f. Evaluation → Calculate fitness (pareto-dominance)
   g. Archive → Update population and Pareto front

4. Termination
   └→ Output best solution and pareto-optimal set
```

### Multi-Objective Fitness Evaluation

HEDGE evaluates solutions based on three metrics:

| Metric | Unit | Collection Method | Importance |
|--------|------|-------------------|-----------|
| **Execution Latency** | milliseconds | Wall-clock time of test suite | Primary |
| **Energy Consumption** | Joules/kWh | CodeCarbon hardware sensors | Primary |
| **Code Complexity** | static measure | Cyclomatic complexity analysis | Secondary (tie-breaker) |

A solution is **Pareto-optimal** if no other solution is strictly better in both latency AND energy.

---

## Optimization Hierarchy

### Layer 1: Semantic Optimization

**Scope**: Highest-level program intent and algorithmic complexity

**Mutators**:

1. **AlgorithmicIntentMutator**
   - Detects suboptimal Big-O patterns (e.g., recursive exponential algorithms)
   - Proposes algorithmic shifts (e.g., dynamic programming, memoization)
   - Uses LLM to generate semantically equivalent but more efficient code
   - Example: `fibonacci(n)` recursive → dynamic programming table

2. **ProgramIntentMutator**
   - Analyzes high-level control flow and data movement
   - Simplifies complex branching and loop structures
   - Refactors based on program semantics
   - Example: Eliminating unnecessary intermediate variables

**Safety Mechanisms**:
- Self-repair loop: LLM-generated code is parsed and validated
- Test suite execution confirms behavioral equivalence
- Up to 3 retry attempts if initial generation fails

---

### Layer 2: Algorithmic Optimization

**Scope**: Data structure and access pattern efficiency

**Mutators**:

1. **DataStructureOptimizer**
   
   a. **Membership Optimization**
   - Detects: `if x in list_var` patterns
   - Replaces: `list` → `set` for O(1) membership testing
   - Conditions: Data immutability, no order dependency
   
   b. **Insertion/Deletion Optimization**
   - Detects: Frequent `list_var.pop(0)` or `list_var.insert(0, x)`
   - Replaces: `list` → `collections.deque` for O(1) head operations
   - Conditions: No random access patterns
   
   c. **Search Optimization**
   - Detects: Linear search patterns in sorted data
   - Replaces: Manual loop → `bisect` module
   - Conditions: Data proven sorted through analysis

2. **ComplexityReducer**
   
   a. **Nested Loop Reduction**
   - Detects: Nested loops creating Cartesian products
   - Replaces: Manual nesting → `itertools.product`
   - Benefit: More efficient iteration
   
   b. **Mathematical Optimization**
   - Detects: Complex arithmetic or logical loops
   - Simplifies: Using mathematical identities
   - Example: Sum formulas, closed-form solutions
   
   c. **Duplicate Work Elimination**
   - Detects: Redundant computations in loops
   - Optimizes: Hoisting invariant computations
   - Reduces: Unnecessary repeated operations

---

### Layer 3: Syntactic Optimization

**Scope**: Pythonic idioms and modern language features

**Mutators**:

1. **PythonicIdiomOptimizer**
   
   a. **Comprehension Optimization**
   - Detects: Manual accumulation loops
   - Converts: `for x in data: result.append(...)` → list comprehensions
   - Benefit: More readable, potentially faster execution
   
   b. **Built-in Utilization**
   - Detects: Manual implementations of built-ins
   - Replaces: Manual `sum()`/`min()`/`max()` → built-in functions
   - Benefit: Leverages optimized C implementations
   
   c. **Iterator Optimization**
   - Detects: `range(len(seq))` patterns
   - Replaces: With `enumerate()` or direct iteration
   - Benefit: More idiomatic, potentially faster

2. **CodePatternOptimizer**
   - Uses LLMs to suggest modern Pythonic patterns
   - Targets: Loop simplification, conditional refactoring, function composition
   - Safe: Test suite verifies correctness

---

### Layer 4: Micro Optimization

**Scope**: Compiler-style, localized refinements

**Mutators**:

1. **ConstantOptimizer**
   
   a. **Constant Folding**
   - Evaluates: Constant expressions at optimization-time
   - Example: `2 + 3` → `5`, `"hello" + "world"` → `"helloworld"`
   - Benefit: Reduces runtime operations
   
   b. **Constant Propagation**
   - Detects: Variables assigned constant values
   - Substitutes: Variable references with constants (where safe)
   - Example: `x = 10; y = x + 5` → `x = 10; y = 15`
   
   c. **Arithmetic/Boolean Simplification**
   - Simplifies: Identity operations
   - Examples:
     - `x + 0` → `x`, `x * 1` → `x`
     - `x and True` → `x`, `x or False` → `x`
     - `x and False` → `False`, `x or True` → `True`

2. **DeadCodeEliminator**
   
   a. **Unreachable Code**
   - Removes: Code after `return`, `break`, `raise`, `continue`
   - Safely: Analyzes control flow
   
   b. **Unused Variables**
   - Detects: Assignments never read
   - Eliminates: Unnecessary variable assignments
   - Safe: Only when no side effects in assignment
   
   c. **Pure Expression Removal**
   - Identifies: Statements with no side effects
   - Removes: Orphaned expressions that don't affect output
   - Example: `x + y` (alone) → removed

3. **LoopMicroOptimizer**
   
   a. **Small Loop Unrolling**
   - Detects: Loops with < 4 iterations
   - Unrolls: Explicit iterations to reduce branch overhead
   - Benefit: Better CPU cache utilization
   
   b. **Invariant Motion**
   - Identifies: Computations that don't change in loop
   - Hoists: Moves before the loop
   - Reduces: Unnecessary repeated computations
   - Example: `for x in data: result.append(constant_expr)` → move before loop

---

## Features & Capabilities

### 1. Unified Intermediate Representation

**Characteristics**:
- **Typed Architecture**: All IR nodes are Pydantic models with full type validation
- **Independence**: Operates independently from Python's native AST
- **Completeness**: Supports all Python 3.8+ syntactic constructs
- **Serialization**: Full JSON serialization for debugging and reproducibility
- **Extensibility**: Easy to add new IR node types

**Benefits**:
- Type safety prevents invalid transformations
- Snapshots enable deterministic replays
- Decoupling allows independent optimization logic
- Validation ensures structural integrity

---

### 2. Hierarchical Mutation System

**Design**: Four layers from high-level to low-level

**Benefits**:
- **Speed**: High-level changes have compound effects
- **Safety**: Low-level changes increase confidence
- **Flexibility**: Mix layers based on time/risk constraints
- **Clarity**: Each mutator has clear responsibility

**Layer Selection**:
- `--level micro`: Layer 4 only (safest, fastest)
- `--level basic`: Layers 3-4 (balanced)
- `--level standard`: Layers 2-4 (comprehensive)
- `--level advanced`: Layers 1-4 with LLM (most powerful, slowest)
- `--level aggressive`: All layers, maximum generations

---

### 3. Intelligent LLM Integration

**LLM Providers Supported**:
- OpenAI GPT-4 / GPT-4o
- Google Gemini 2.0 Flash

**Self-Repairing Mechanism**:
```
1. Generate → LLM produces mutated code
2. Parse   → Convert to IR
3. Validate → Check schema compliance
4. Test    → Execute test suite
   ├─ Success → Accept mutation
   └─ Failure → Retry with error feedback (max 3 attempts)
```

**Chain-of-Thought Prompting**:
- Provides IR structure to LLM
- Explains optimization goals clearly
- Includes test suite for verification
- Iteratively corrects syntax/logic errors

---

### 4. Multi-Objective Evolution

**Objectives**:
1. **Minimize Execution Latency**: Wall-clock time of test suite
2. **Minimize Energy Consumption**: Joules/kWh via CodeCarbon
3. **Secondary**: Code complexity (for tie-breaking)

**Pareto Archive**:
- Maintains set of non-dominated solutions
- Solutions on the Pareto front are all potentially valuable
- Trade-offs visualized in reports (latency vs. energy)

**Selection Strategy**:
- Tournament selection biased toward Pareto-optimal solutions
- Crowding distance ensures diversity
- Elitism preserves best solutions

---

### 5. Automated Validation & Testing

**Validation Pipeline**:
```
IR → Codegen → Syntax Check → Parse to IR
       ↓
    Execution → Test Suite → Pass/Fail
       ↓
    Metrics → Fitness Evaluation
```

**Test Suite Integration**:
- Executes provided test file
- All tests must pass for solution acceptance
- Test coverage determines confidence level
- Failures trigger repair attempts (for LLM mutations)

---

### 6. Green Gym (Sandboxed Execution)

**Features**:
- Isolated Python subprocess execution
- Timeout protection (prevents infinite loops)
- Resource limits (memory, CPU)
- Automatic cleanup
- Energy monitoring integration

**Metrics Collection**:
- Wall-clock execution time
- CPU time
- Peak memory usage
- Energy consumption (hardware sensors on Linux)
- Test pass/fail status

---

### 7. Advanced Visualization & Reporting

**Generated Artifacts**:

1. **HTML Reports** (`report.html`)
   - Interactive dashboard
   - Pareto front visualization
   - Fitness trajectory across generations
   - Code diff highlighting
   - Mutation history timeline

2. **Pareto Front Chart**
   - Scatter plot: Latency vs. Energy
   - Each point is a Pareto-optimal solution
   - Hover tooltips with detailed metrics
   - Download as SVG/PNG

3. **Performance Charts**
   - Fitness improvement per generation
   - Layer contribution analysis
   - Success rate by mutator
   - Population diversity metrics

4. **Code Diff Visualization**
   - Side-by-side or inline diffs
   - Mutation highlighting
   - Original vs. optimized side-by-side

5. **Statistical Summary**
   - Total generations executed
   - Total mutations attempted
   - Success rate per layer
   - Best improvement percentage
   - Pareto set size

---

### 8. Project & Experiment Management

**Project Structure**:
```
project_name/
├── source.py                 # Original code
├── tests.py                  # Test suite
├── config.yaml              # Project configuration
└── experiments/
    ├── experiment_001/
    │   ├── optimized.py     # Best solution
    │   ├── pareto_results.json
    │   ├── statistics.json
    │   └── visualizations/
    │       ├── report.html
    │       ├── pareto_front.png
    │       └── statistics.json
    └── experiment_002/
        └── ...
```

**Configuration Management**:
- YAML-based configuration
- Hierarchical: CLI args → local config → global config → defaults
- Environment variable overrides
- Project-specific settings

---

### 9. Extensibility & Plugin Architecture

**Custom Mutator Development**:
```python
from src.application.mutators.base import LayeredMutator, MutationLayer
from src.domain.ir import schema

class CustomOptimizer(LayeredMutator):
    def __init__(self):
        super().__init__(MutationLayer.MICRO)
        self.mutator_name = "Custom Optimizer"
    
    def _apply_mutations(self, ir: schema.Module) -> List[schema.Module]:
        # Custom transformation logic
        variants = []
        # Create multiple variants
        return variants
```

**Registry System**:
- Automatic mutator discovery
- Per-layer organization
- Adaptive selection based on success rates
- Extensible without modifying core code

---

## Installation & Setup

### Prerequisites

```
- Python 3.8 or higher
- Linux recommended (for hardware energy monitoring via CodeCarbon)
- Optional: OpenAI API key or Google Gemini API key
```

### Step-by-Step Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd HEDGE

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Optional: Install visualization packages
pip install rich matplotlib

# 5. Configure API keys (for semantic optimization)
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
LOG_LEVEL=INFO
EOF

# 6. Verify installation
python hedge.py benchmark --quick
```

### Dependencies

**Core Requirements**:
- `pydantic>=2.0`: Type validation and serialization
- `click>=8.0`: CLI framework
- `pytest>=7.0`: Testing framework
- `python-dotenv>=1.0`: Environment configuration

**Performance & Monitoring**:
- `codecarbon>=2.0`: Energy consumption measurement
- `numpy>=1.20`, `pandas>=1.3`: Data analysis

**Visualization**:
- `matplotlib>=3.5`: Static plots
- `plotly>=5.0`: Interactive visualizations
- `jinja2>=3.0`: HTML report generation
- `rich>=13.0`: Terminal output formatting

**API & Web**:
- `fastapi>=0.100.0`: REST API framework
- `uvicorn>=0.23.0`: ASGI application server
- `websockets>=11.0`: WebSocket support

**Configuration**:
- `pyyaml>=6.0`: YAML configuration parsing

---

## Usage Guide

### 1. Basic Optimization

```bash
# Optimize a Python file with default settings
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py

# Specify optimization level
python hedge.py optimize target.py test.py --level advanced

# With custom generation count
python hedge.py optimize target.py test.py --generations 20 --population-size 15
```

### 2. Specifying Optimization Layers

```bash
# Use only micro optimizations (safest, fastest)
python hedge.py optimize target.py test.py --layers micro

# Use specific layers
python hedge.py optimize target.py test.py --layers "micro,syntactic,algorithmic"

# Use all layers (same as --level advanced)
python hedge.py optimize target.py test.py --layers "semantic,algorithmic,syntactic,micro"
```

### 3. LLM Provider Selection

```bash
# Use Gemini (faster, lower cost)
python hedge.py optimize target.py test.py --llm gemini --level advanced

# Use OpenAI GPT-4
python hedge.py optimize target.py test.py --llm openai:gpt-4 --level advanced
```

### 4. Static Analysis

```bash
# Analyze a file without optimization
python hedge.py analyze target.py

# Output includes:
# - Cyclomatic complexity
# - IR node density
# - Nesting depth
# - Estimated optimization opportunities
```

### 5. Visualization & Reporting

```bash
# Generate visualization during optimization
python hedge.py optimize target.py test.py --visualize

# Generate visualization from existing experiment
python hedge.py visualize experiments/experiment_001

# Outputs:
# - report.html: Interactive dashboard
# - pareto_front.png: Trade-off visualization
# - statistics.json: Raw metrics
```

### 6. Benchmarking

```bash
# Run quick benchmark (minimal time)
python hedge.py benchmark --quick

# Comprehensive comparison across optimization levels
python hedge.py benchmark --compare-levels

# Run against EvoEval suite
python hedge.py benchmark --suite evoeval
```

### 7. Web Interface

```bash
# Start interactive web interface (Node.js required)
python hedge.py app

# Access at http://localhost:5173
# Features:
# - Real-time optimization visualization
# - Experiment management
# - Configuration interface
# - Results comparison
```

### 8. API Server

```bash
# Start REST API and WebSocket server
python hedge.py serve

# Or with custom port
python hedge.py serve --port 8000 --host 0.0.0.0

# Enable debug logging
LOG_LEVEL=DEBUG python hedge.py serve
```

---

## API Reference

### REST Endpoints (FastAPI)

#### Start Optimization Task
```
POST /api/v1/optimize

Request Body:
{
  "target_code": "string",
  "test_code": "string",
  "level": "micro|basic|standard|advanced|aggressive",
  "generations": 10,
  "population_size": 8,
  "llm_provider": "gemini|openai:gpt-4"
}

Response:
{
  "task_id": "uuid",
  "status": "running",
  "created_at": "ISO-8601 timestamp"
}
```

#### Get Task Status
```
GET /api/v1/tasks/{task_id}

Response:
{
  "task_id": "uuid",
  "status": "running|completed|failed",
  "progress": {"current_gen": 5, "total_gen": 10},
  "best_solution": {...},
  "pareto_front": [...]
}
```

#### Stop Task
```
DELETE /api/v1/tasks/{task_id}

Response:
{
  "status": "stopped",
  "final_solutions": [...]
}
```

#### Get Specific Solution
```
GET /api/v1/tasks/{task_id}/solutions/{variant_id}

Response:
{
  "id": "variant_001",
  "code": "string",
  "metrics": {
    "latency": 45.2,
    "energy": 0.034,
    "complexity": 8
  },
  "mutations": ["mutator1", "mutator2"]
}
```

#### List All Tasks
```
GET /api/v1/tasks

Response:
{
  "tasks": [
    {
      "task_id": "uuid",
      "status": "completed",
      "created_at": "ISO-8601"
    }
  ]
}
```

#### Health Check
```
GET /health

Response:
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### WebSocket Interface

#### Connection
```
WS /api/v1/ws/{task_id}
```

#### Real-Time Events

**Optimization Started**:
```json
{
  "event": "optimization_started",
  "task_id": "uuid",
  "total_generations": 10
}
```

**Generation Complete**:
```json
{
  "event": "generation_complete",
  "generation": 1,
  "population_size": 8,
  "best_fitness": {"latency": 42.1, "energy": 0.031}
}
```

**Mutation Attempt**:
```json
{
  "event": "mutation_attempt",
  "mutator": "ConstantOptimizer",
  "mutator_display": "Constant Optimizer",
  "strategy": "Fold_Constants",
  "parent": "variant_001"
}
```

**Mutation Result**:
```json
{
  "event": "mutation_result",
  "mutator": "ConstantOptimizer",
  "success": true,
  "variant": "variant_002",
  "metrics": {
    "latency": 39.8,
    "energy": 0.029,
    "improvement": 5.5
  }
}
```

**Optimization Complete**:
```json
{
  "event": "optimization_complete",
  "best_solution": {...},
  "pareto_front": [...],
  "statistics": {...}
}
```

**Error**:
```json
{
  "event": "error",
  "message": "Detailed error description",
  "timestamp": "ISO-8601"
}
```

---

## Configuration

### Configuration File Structure

**Location Hierarchy** (highest to lowest priority):
1. CLI arguments
2. Explicit config file (--config)
3. Local config (./hedge.yaml)
4. User config (~/.hedge/config.yaml)
5. Project defaults (config/default.yaml)

**Example hedge.yaml**:
```yaml
optimization:
  default_level: "standard"
  default_generations: 10
  default_population_size: 8
  max_generations: 50
  timeout_seconds: 300

llm:
  default_provider: "gemini"
  gemini:
    model: "gemini-2.0-flash"
    temperature: 0.7
    max_retries: 3
  openai:
    model: "gpt-4"
    temperature: 0.5
    max_retries: 3

execution:
  test_timeout: 30
  energy_monitoring: true
  sandbox_memory_limit: 1024  # MB
  
visualization:
  generate_html: true
  generate_charts: true
  interactive: true

api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:3000"
  enable_debug: false

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Environment Variables

**API Configuration**:
```bash
LOG_LEVEL=DEBUG              # Logging verbosity
HOST=0.0.0.0                # Server host
PORT=8000                   # Server port
ENVIRONMENT=development     # development or production
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

**LLM Configuration**:
```bash
GEMINI_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

**Optimization**:
```bash
HEDGE_LOG_LEVEL=DEBUG       # Log level for optimization
DEFAULT_GENERATIONS=10
DEFAULT_POPULATION_SIZE=8
```

---

## Development & Extension

### Project Structure Details

```
HEDGE/
├── hedge.py                 # Entry point script
├── requirements.txt         # Dependency specifications
├── Makefile                # Build automation
├── config/
│   └── default.yaml        # Default configuration
│
├── cli/                     # Command-line interface
│   ├── main.py             # CLI entry point
│   ├── commands/           # Individual command implementations
│   │   ├── optimize.py
│   │   ├── analyze.py
│   │   ├── benchmark.py
│   │   ├── app.py
│   │   ├── serve.py
│   │   ├── visualize.py
│   │   └── ...
│   └── utils/              # CLI utilities
│       ├── banner.py
│       └── ...
│
├── api/                     # REST API & WebSocket server
│   ├── main.py             # FastAPI application
│   ├── endpoints.py        # Route handlers
│   ├── manager.py          # Task management logic
│   ├── models.py           # Request/response models
│   └── utils.py            # Helper functions
│
├── src/
│   ├── domain/             # Domain layer - core models & interfaces
│   │   ├── ir.py           # Intermediate Representation schema
│   │   ├── metrics.py      # Metrics calculation
│   │   └── base.py         # Abstract base classes
│   │
│   ├── application/        # Application layer - business logic
│   │   ├── engine.py       # Evolutionary engine
│   │   ├── mutators/       # Mutation strategies
│   │   │   ├── semantic.py
│   │   │   ├── algorithmic.py
│   │   │   ├── syntactic.py
│   │   │   ├── micro.py
│   │   │   └── base.py
│   │   ├── registry.py     # Mutator registry
│   │   └── orchestrator.py # Multi-stage orchestration
│   │
│   ├── infrastructure/     # Infrastructure layer - external integrations
│   │   ├── parser.py       # Python AST → IR conversion
│   │   ├── codegen.py      # IR → Python source generation
│   │   ├── runner.py       # Sandboxed execution environment
│   │   ├── llm_clients.py  # LLM integrations
│   │   └── energy_monitor.py
│   │
│   └── utils/              # Shared utilities
│
├── examples/               # Example code for benchmarking
│   ├── target_fib.py
│   ├── target_complex.py
│   └── test_*.py
│
├── tests/                  # Comprehensive test suite
│   ├── test_api_endpoints.py
│   ├── test_cli_commands.py
│   ├── test_codegen.py
│   ├── test_execution_runners.py
│   ├── test_ir_schema.py
│   ├── test_parser.py
│   └── ...
│
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md
│   ├── CLI.md
│   ├── MUTATORS.md
│   ├── SETUP.md
│   ├── FEATURES.md
│   └── CONTRIBUTING.md
│
├── evoeval_benchmark/      # EvoEval benchmarking suite
│   ├── extract_evoeval.py
│   └── EvoEval_difficult_*/
│
├── web/                    # Interactive web interface (Vue.js/React)
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── eslint.config.js
│
└── scripts/                # Utility scripts
    ├── setup.py            # Installation & setup
    ├── clean.py            # Cleanup utility
    └── run_examples.py     # Example execution
```

### Creating Custom Mutators

**Template**:
```python
from src.application.mutators.base import LayeredMutator, MutationLayer
from src.domain.ir import schema
from typing import List

class MyCustomMutator(LayeredMutator):
    """Description of what this mutator does"""
    
    def __init__(self):
        super().__init__(MutationLayer.MICRO)  # Choose appropriate layer
        self.mutator_name = "My Custom Mutator"
    
    def _apply_mutations(self, ir: schema.Module) -> List[schema.Module]:
        """
        Apply mutations to the IR, returning multiple variants.
        Each variant should be a valid, independent IR.
        """
        variants = []
        
        # Clone the IR
        import copy
        ir_copy = copy.deepcopy(ir)
        
        # Apply your transformation logic
        # Example: Transform ir_copy.body
        
        # Add the variant
        if my_transformation_is_valid(ir_copy):
            variants.append(ir_copy)
        
        # Create multiple variants if needed
        ir_copy2 = copy.deepcopy(ir)
        # Different transformation...
        variants.append(ir_copy2)
        
        return variants

# Register the mutator
from src.application.mutators.registry import register_mutator
register_mutator(MyCustomMutator())
```

**Integration Points**:
1. Inherit from `LayeredMutator`
2. Specify the layer in `__init__`
3. Implement `_apply_mutations(ir)` method
4. Return list of IR variants
5. Register in mutator registry or auto-discovery handles it

---

## Performance Metrics & Evaluation

### Metrics Collected

#### Primary Metrics

| Metric | Unit | How Measured | Importance |
|--------|------|--------------|-----------|
| **Execution Latency** | ms | Wall-clock test suite time | Critical |
| **Energy Consumption** | kJ/Wh | CodeCarbon + CPU counters | Critical |

#### Secondary Metrics

| Metric | Unit | How Measured | Purpose |
|--------|------|--------------|---------|
| **Cyclomatic Complexity** | integer | Static IR analysis | Code maintainability |
| **IR Node Density** | nodes/function | Count IR nodes | Code size metric |
| **Nesting Depth** | levels | Max nesting in AST | Readability measure |
| **Code Size** | LoC | Line of code count | Size comparison |

### Benchmark Suite

#### EvoEval Benchmark

HEDGE includes integration with the **EvoEval** benchmark suite for standardized evaluation:

**Test Categories**:
- `EvoEval_difficult_4`: 4 difficult algorithmic problems
- `EvoEval_difficult_16`: 16 difficult problems
- `EvoEval_difficult_52`: 52 problems (medium difficulty)
- `EvoEval_difficult_61-90`: Various difficulty levels

**Evaluation Protocol**:
```bash
# Run against EvoEval
python hedge.py benchmark --suite evoeval [--subset difficult_16]

# Comparison across optimization levels
python hedge.py benchmark --compare-levels --suite evoeval
```

### Pareto Optimality Analysis

**Definition**: A solution is Pareto-optimal if no other solution is strictly better in ALL objectives.

**Visualization**: Generated reports show:
- Pareto front as a scatter plot (Latency × Energy)
- Non-dominated solutions highlighted
- Dominated solutions shown with transparency
- Trade-off curve for decision-making

**Applications**:
1. **Space-Time Tradeoff**: Choose latency- or energy-optimal solution
2. **Balanced Solutions**: Select solutions in middle of Pareto front
3. **Hardware Tuning**: Different hardware favors different points

### Success Metrics

**Mutation Success Rate**:
- Percentage of mutations yielding valid (syntactically correct) IR
- Typical range: 60-85% depending on layer

**Test Pass Rate**:
- Percentage of mutations passing test suite
- Typical range: 70-95% (semantic mutations lower)

**Improvement Rate**:
- Percentage of generations showing fitness improvement
- Typical range: 40-70%

**Coverage by Layer**:
- Which layers contributed to final improvements
- Typical: Micro (30%), Syntactic (25%), Algorithmic (25%), Semantic (20%)

---

## Troubleshooting & FAQ

### Common Issues

#### Issue: "No codec module available"
**Cause**: Energy monitoring not available
**Solution**: Install `codecarbon` or disable energy monitoring:
```bash
pip install codecarbon
```

#### Issue: "LLM API Key not found"
**Cause**: Environment variable not set
**Solution**: 
```bash
export GEMINI_API_KEY=your-key
export OPENAI_API_KEY=your-key
```

#### Issue: Test suite fails on optimized code
**Cause**: Mutation violated test correctness
**Solution**: The mutation is automatically rejected; HEDGE will try others

#### Issue: WebSocket shows "Unknown" mutator names
**Cause**: Mutator metadata not properly attached to mutations
**Solution**: Enable DEBUG logging and check merge operations:
```bash
LOG_LEVEL=DEBUG python api/main.py
```

### Performance Tuning

**For Speed**:
```bash
python hedge.py optimize target.py test.py --level micro --generations 5
```

**For Quality**:
```bash
python hedge.py optimize target.py test.py --level advanced --generations 30 --population-size 20
```

**For Energy Analysis**:
- Run on Linux with hardware energy sensors
- Use larger test suite for accurate measurements
- Monitor CodeCarbon logs

---

## Key Statistics & Capabilities

| Aspect | Capability |
|--------|-----------|
| **Python Support** | 3.8+ (all modern syntax) |
| **Optimization Layers** | 4 (Semantic, Algorithmic, Syntactic, Micro) |
| **LLM Models** | GPT-4, Gemini 2.0 Flash |
| **Mutators** | 10+ built-in, extensible |
| **Fitness Objectives** | 2 primary (latency, energy) + complexity |
| **Evolution Strategy** | Tournament selection, multi-objective |
| **Validation** | IR schema + test suite execution |
| **Visualization** | Interactive HTML, charts, diffs |
| **API** | REST endpoints + WebSocket |
| **Benchmarks** | EvoEval suite integration |
| **Self-Repair** | Yes, for LLM mutations (3 retries) |

---

## Conclusion

HEDGE represents a comprehensive framework for automated Python code optimization that balances multiple objectives through evolutionary algorithms, intelligent AI integration, and rigorous validation. By operating on a type-safe intermediate representation and organizing optimizations hierarchically, HEDGE enables both researchers and practitioners to explore and implement significant performance improvements while maintaining code correctness and clarity.

The system is designed for extensibility, allowing custom mutators and metrics to be integrated seamlessly, and provides extensive visibility through logging, reporting, and visualization capabilities.

---

