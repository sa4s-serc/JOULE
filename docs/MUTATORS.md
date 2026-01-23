# HEDGE Optimization Layers

HEDGE utilizes a hierarchical mutation system to optimize Python code across multiple levels of abstraction. Each layer is responsible for a specific class of optimizations, ranging from high-level algorithmic shifts to low-level compiler-style micro-refinements.

## 1. Semantic Layer
The Semantic Layer operates at the highest level of abstraction, focusing on the program's intent and high-level algorithmic logic. It leverages Large Language Models (LLMs) to perform complex refactorings that require a deep understanding of the code.

### Mutators
- **AlgorithmicIntentMutator**: Identifies opportunities to change the underlying algorithm or Big-O complexity (e.g., recursive to iterative, exponential to linear).
- **ProgramIntentMutator**: Simplifies high-level control flow and program structure based on the inferred meaning of the code.

### Mechanism
These mutators convert the IR to source code, prompt an LLM with specific optimization goals, and then parse the results back into the HEDGE IR. A self-repair mechanism handles any syntax errors in the AI-generated output.

---

## 2. Algorithmic Layer
The Algorithmic Layer focuses on data structure efficiency and internal complexity reduction. These are logic-based transformations that do not require an LLM but operate on broader code patterns.

### Mutators
- **DataStructureOptimizer**: 
    - **Membership Optimization**: Converts list membership tests to set membership for O(1) access.
    - **Insertion/Deletion Optimization**: Replaces list operations with `collections.deque` where appropriate to optimize O(n) head operations.
    - **Search Optimization**: Heuristically replaces linear searches with `bisect` for sorted data.
- **ComplexityReducer**:
    - **Nested Loop Reduction**: Converts nested loops to `itertools.product` to improve iteration performance.
    - **Mathematical Optimization**: Simplifies complex arithmetic or logical loops using mathematical identities.
    - **Duplicate Work Elimination**: Identifies and removes redundant computations within a scope.

---

## 3. Syntactic Layer
The Syntactic Layer focuses on Pythonic idioms and modern coding patterns. It ensures the code follows "The Zen of Python" and utilizes efficient built-in features.

### Mutators
- **PythonicIdiomOptimizer**:
    - **Comprehension Optimization**: Converts manual accumulation loops into list, set, or dict comprehensions.
    - **Built-in Utilization**: Replaces manual loop-based `sum`, `min`, or `max` calculations with their built-in equivalents.
    - **Iterator Optimization**: Transforms `range(len())` patterns into idiomatic `enumerate()` or direct iteration.
- **CodePatternOptimizer**: Uses LLMs to suggest modern Pythonic patterns for loop management, conditional simplification, and function composition.

---

## 4. Micro Layer
The Micro Layer performs localized, compiler-style optimizations. These transformations are extremely safe, fast, and focus on removing "bloat" from the code.

### Mutators
- **ConstantOptimizer**:
    - **Constant Folding**: Evaluates constant expressions (e.g., `2 + 3`) during optimization.
    - **Constant Propagation**: Substitutes variable references with their known constant values.
    - **Arithmetic/Boolean Simplification**: Removes identity operations (e.g., `x + 0`, `x and True`).
- **DeadCodeEliminator**:
    - **Unreachable Code**: Removes code after `return`, `break`, or `raise`.
    - **Unused Variables**: Eliminates assignments to variables that are never read.
    - **Pure Expression Removal**: Removes statements that have no side effects and no impact on output.
- **LoopMicroOptimizer**:
    - **Small Loop Unrolling**: Expands very small loops (e.g., < 4 iterations) to reduce branch overhead.
    - **Invariant Motion**: Moves computations that don't change inside a loop to just before the loop begins.

---

## Custom Mutator Development

To extend HEDGE with custom mutators, developers can inherit from the `LayeredMutator` base class and register them in the `MutatorRegistry`.

```python
from src.application.mutators.base import LayeredMutator, MutationLayer
from src.domain.ir import schema

class MyOptimizer(LayeredMutator):
    def __init__(self):
        super().__init__(MutationLayer.MICRO)
        
    def _apply_mutations(self, ir: schema.Module):
        # Implementation of IR-based transformations
        pass
```
