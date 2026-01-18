# HEDGE Features Overview

Comprehensive guide to all HEDGE features and capabilities.

## 🏗️ Core Architecture

### IR-Only Optimization
- **Intermediate Representation**: All transformations operate on a strict IR, never on strings
- **Type Safety**: Pydantic-based IR ensures structural validity
- **Validation Gates**: Every transformation is validated before code generation
- **Serializable**: IR can be saved, loaded, and analyzed independently

### Hierarchical Mutation System
HEDGE uses a 4-layer hierarchical approach to code optimization:

```
🧠 SEMANTIC LAYER     - Algorithm intent and high-level logic
📊 ALGORITHMIC LAYER  - Data structures and complexity optimization  
🐍 SYNTACTIC LAYER    - Python idioms and code patterns
⚡ MICRO LAYER        - Low-level optimizations
```

## 🔬 Optimization Layers

### Semantic Layer (🧠)
**AI-Powered Algorithm Optimization**
- **AlgorithmicIntentMutator**: Recognizes algorithmic patterns and suggests better approaches
- **ProgramIntentMutator**: Simplifies program logic and control flow
- **Capabilities**:
  - O(2^n) → O(n) Fibonacci optimization
  - Recursive → Iterative transformations
  - Algorithm selection (bubble sort → quicksort)
  - Logic simplification

**Example Transformation**:
```python
# Before: O(2^n) recursive Fibonacci
def fib(n):
    if n <= 1: return n
    return fib(n-1) + fib(n-2)

# After: O(n) iterative Fibonacci  
def fib(n):
    if n <= 1: return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
```

### Algorithmic Layer (📊)
**Data Structure and Complexity Optimization**
- **DataStructureOptimizer**: Optimizes data structure selection
- **ComplexityReducer**: Reduces algorithmic complexity
- **Capabilities**:
  - List → Set conversion for membership testing
  - Nested loop reduction
  - Mathematical optimizations
  - Access pattern optimization

**Example Transformation**:
```python
# Before: O(n²) membership testing
def filter_items(items, allowed):
    result = []
    for item in items:
        if item in allowed:  # O(n) lookup in list
            result.append(item)
    return result

# After: O(n) with set lookup
def filter_items(items, allowed):
    allowed_set = set(allowed)  # O(1) lookup
    return [item for item in items if item in allowed_set]
```

### Syntactic Layer (🐍)
**Python Idiom and Pattern Optimization**
- **PythonicIdiomOptimizer**: Applies Python best practices
- **CodePatternOptimizer**: LLM-based pattern improvements
- **Capabilities**:
  - List comprehensions
  - Built-in function usage (map, filter, sum)
  - Iterator optimization
  - Pythonic patterns

**Example Transformation**:
```python
# Before: Manual loop
result = []
for x in items:
    if x > 0:
        result.append(x * 2)

# After: List comprehension
result = [x * 2 for x in items if x > 0]
```

### Micro Layer (⚡)
**Low-Level Code Optimizations**
- **ConstantOptimizer**: Constant folding and propagation
- **DeadCodeEliminator**: Removes unreachable code
- **LoopMicroOptimizer**: Loop unrolling and strength reduction
- **Capabilities**:
  - Compile-time constant evaluation
  - Unreachable code removal
  - Strength reduction (x**2 → x*x)
  - Loop unrolling for small iterations

**Example Transformation**:
```python
# Before: Runtime calculation
SECONDS_PER_DAY = 24 * 60 * 60
if False:
    print("This never runs")

# After: Compile-time optimization
SECONDS_PER_DAY = 86400
# Dead code removed
```

## 🎯 Optimization Levels

### Micro Level
- **Layers**: Micro only
- **Speed**: Very fast (< 1 minute)
- **Safety**: Highest - only safe transformations
- **Use Case**: Quick wins, production code

### Basic Level  
- **Layers**: Micro + Syntactic
- **Speed**: Fast (1-3 minutes)
- **Safety**: High - well-tested transformations
- **Use Case**: Python idiom improvements

### Standard Level (Recommended)
- **Layers**: Micro + Syntactic + Algorithmic
- **Speed**: Moderate (3-10 minutes)
- **Safety**: Good - complexity-aware transformations
- **Use Case**: General optimization, most projects

### Advanced Level
- **Layers**: All layers including Semantic
- **Speed**: Slower (10-30 minutes)
- **Safety**: Requires validation - AI-generated code
- **Use Case**: Research, maximum optimization
- **Requirements**: LLM API key

### Aggressive Level
- **Layers**: All layers with maximum settings
- **Speed**: Slowest (30+ minutes)
- **Safety**: Requires careful validation
- **Use Case**: Experimental optimization

## 🤖 LLM Integration

### Supported Providers
- **Google Gemini** (recommended)
  - Model: gemini-pro
  - Fast and cost-effective
  - Good code understanding
  
- **OpenAI GPT-4**
  - Model: gpt-4
  - Highest quality transformations
  - More expensive

### Self-Repair Mechanism
- **Automatic Validation**: Generated code is automatically tested
- **Retry Logic**: Up to 3 attempts to fix invalid code
- **Fallback**: Falls back to lower-level optimizations on failure

### Caching
- **Response Caching**: LLM responses are cached to avoid repeated calls
- **Cost Optimization**: Reduces API costs for repeated optimizations

## 🏃‍♂️ Execution Engine

### Green Gym Runner
- **Energy Monitoring**: Measures actual energy consumption using CodeCarbon
- **Time Tracking**: Precise execution time measurement
- **Sandboxing**: Safe execution environment
- **Timeout Protection**: Prevents infinite loops

### Multi-Objective Optimization
- **Pareto Front**: Maintains non-dominated solutions
- **Energy vs Time**: Balances energy efficiency and execution speed
- **Diversity Preservation**: NSGA-II style crowding distance
- **Archive Management**: Maintains best solutions across generations

## 📊 Metrics and Analysis

### IR Metrics
- **Structural Metrics**: Node count, depth, complexity
- **Cyclomatic Complexity**: Code complexity measurement
- **Function Analysis**: Per-function metrics
- **Dependency Analysis**: Variable usage and scope

### Performance Metrics
- **Energy Consumption**: Joules consumed during execution
- **Execution Time**: Wall-clock time in seconds
- **Memory Usage**: Peak memory consumption
- **Cache Statistics**: Hit rates and efficiency

### Success Metrics
- **Mutation Success Rate**: Percentage of valid mutations
- **Improvement Percentage**: Energy/time improvement over baseline
- **Pareto Solutions**: Number of non-dominated solutions found

## 🎨 Visualization System

### Chart Types
- **Pareto Front**: Energy vs time scatter plot
- **Evolution Progress**: Improvement over generations
- **Mutation Effectiveness**: Success rates by mutator type
- **Metrics History**: Detailed metric tracking

### Export Formats
- **HTML Reports**: Interactive web-based reports
- **PNG Images**: Static chart images
- **SVG Vector**: Scalable vector graphics
- **PDF Reports**: Print-ready documents

### Interactive Features
- **Hover Details**: Detailed information on hover
- **Zoom and Pan**: Interactive chart navigation
- **Solution Comparison**: Side-by-side code comparison

## 🔧 Configuration System

### Configuration Sources (Priority Order)
1. **Environment Variables**: `HEDGE_*` variables
2. **User Config**: `~/.hedge/config.yaml`
3. **Project Config**: `.hedge.yaml` in project directory
4. **Default Config**: Built-in defaults

### Configuration Sections
- **Optimization**: Default levels, generations, population size
- **LLM**: Provider settings, model selection, caching
- **Execution**: Runner configuration, timeouts, limits
- **Output**: Experiment directories, visualization settings
- **Performance**: Caching, parallelization, batch sizes

## 🚀 CLI Features

### Modern Interface
- **Rich Console**: Beautiful terminal output with colors and formatting
- **Progress Tracking**: Real-time progress bars and status updates
- **Interactive Prompts**: Guided configuration and setup
- **Command Completion**: Tab completion for commands and options

### Command Categories
- **optimize**: Core optimization functionality
- **analyze**: Code analysis and metrics
- **visualize**: Generate charts and reports
- **benchmark**: Performance testing on example problems
- **config**: Configuration management
- **project**: Project organization and management

### Batch Operations
- **Multiple Files**: Optimize multiple files in one run
- **Experiment Suites**: Run comprehensive optimization experiments
- **Comparison Mode**: Compare different optimization levels

## 🔍 Analysis Tools

### Code Complexity Analysis
- **Cyclomatic Complexity**: McCabe complexity metric
- **Nesting Depth**: Maximum indentation depth
- **Function Metrics**: Per-function analysis
- **Recommendations**: Automated optimization suggestions

### Dependency Analysis
- **Variable Usage**: Track variable definitions and usage
- **Scope Analysis**: Function and class scope tracking
- **Import Analysis**: External dependency tracking

### Performance Profiling
- **Execution Profiling**: Identify performance bottlenecks
- **Memory Profiling**: Track memory usage patterns
- **Energy Profiling**: Identify energy-intensive operations

## 📁 Project Management

### Project Templates
- **Basic**: Simple optimization project
- **Advanced**: Full-featured project with benchmarking
- **Research**: Academic research template with notebooks

### Project Structure
```
my_project/
├── src/           # Source code to optimize
├── tests/         # Test files
├── experiments/   # Optimization results
├── config/        # Project configuration
├── docs/          # Documentation
└── scripts/       # Utility scripts
```

### Experiment Management
- **Automatic Organization**: Timestamped experiment directories
- **Result Archiving**: Compress and store old experiments
- **Cleanup Tools**: Remove temporary files and old results

## 🧪 Testing and Validation

### Comprehensive Test Suite
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Performance Tests**: Optimization effectiveness testing
- **Safety Tests**: Semantic preservation validation

### Continuous Validation
- **IR Validation**: Structural correctness checking
- **Semantic Validation**: Behavior preservation testing
- **Performance Validation**: Improvement verification

## 🔌 Extensibility

### Plugin System
- **Custom Mutators**: Add new optimization strategies
- **Custom Runners**: Integrate different execution environments
- **Custom Metrics**: Define domain-specific metrics

### API Access
- **Python API**: Programmatic access to all functionality
- **Configuration API**: Dynamic configuration management
- **Extension Points**: Well-defined interfaces for customization

## 🛡️ Safety and Reliability

### Semantic Preservation
- **Test-Driven Validation**: All optimizations must pass existing tests
- **Behavior Verification**: Automated behavior checking
- **Rollback Capability**: Easy reversion to original code

### Error Handling
- **Graceful Degradation**: Falls back to simpler optimizations on failure
- **Detailed Logging**: Comprehensive error reporting and debugging
- **Recovery Mechanisms**: Automatic recovery from common failures

### Production Ready
- **Stable Core**: Well-tested core optimization algorithms
- **Conservative Defaults**: Safe default settings for production use
- **Validation Gates**: Multiple validation layers prevent invalid output