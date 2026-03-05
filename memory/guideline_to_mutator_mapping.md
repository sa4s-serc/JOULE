# Green Guideline → LLM Mutator Mapping

Generated from: `S2-group/...3.2 Green guidelines elicitation/7-final-guidelines.csv` + `Guidelines.pdf`

## LLM Mutators in the Hedge System

Only three mutators use LLMs (via `LLMMutatorBase`). The others are rule-based IR transformers.

| Mutator | Layer | Strategies |
|---------|-------|-----------|
| `AlgorithmicIntentMutator` | SEMANTIC | `ComplexityReduction`, `PatternRecognition`, `ArchitecturalImprovement` |
| `ProgramIntentMutator` | SEMANTIC | `LogicSimplification`, `FlowOptimization`, `PurposeAlignment` |
| `CodePatternOptimizer` | SYNTACTIC | `LoopOptimization`, `ConditionalSimplification`, `FunctionComposition`, `ErrorHandling` |

---

## Guidelines (G1–G28) and Their Assignments

### APPLICABLE GUIDELINES (include in LLM prompts)

---

#### G1 — Assign repeated expressions to a variable (CSE)
**Applicable to:**
- `AlgorithmicIntent_ComplexityReduction` — Eliminates redundant computation at algorithm level
- `AlgorithmicIntent_PatternRecognition` — CSE is a classic recognizable pattern
- `ProgramIntent_LogicSimplification` — Removing repeated evaluations simplifies logic
- `Pattern_LoopOptimization` — Hoist repeated expressions out of loops (loop invariant code motion)

**Reasoning:** This is a universal low-hanging-fruit optimization. It applies anywhere a subexpression recurs. Loop context is the most impactful location (applies per-iteration overhead).

---

#### G2 — Avoid redundant operations in sorting already sorted/semi-sorted collections
**Applicable to:**
- `AlgorithmicIntent_ComplexityReduction` — Detecting and skipping unnecessary O(n log n) sort
- `AlgorithmicIntent_PatternRecognition` — Recognizing sorted-input patterns (binary search, etc.)
- `ProgramIntent_FlowOptimization` — Conditionally skipping sort based on control flow

**Reasoning:** Sorting is expensive; if data is already ordered, re-sorting wastes CPU cycles and energy. This is an algorithm-level and control-flow concern.

---

#### G3 — Loop optimization (unrolling, unswitching, early termination, store loop-end condition)
**Applicable to:**
- `AlgorithmicIntent_ComplexityReduction` — Reducing loop-level complexity
- `AlgorithmicIntent_PatternRecognition` — Recognizing unrollable/optimizable loop patterns
- `ProgramIntent_FlowOptimization` — Control flow restructuring of loops (break conditions, hoisting end condition)
- `Pattern_LoopOptimization` — Most directly applicable; prompt already covers many of these

**Reasoning:** Loops dominate execution time in most programs. All loop-focused mutators should be aware of these techniques, especially early termination (huge energy savings when loops can exit early).

---

#### G4 — Short-circuit versions of logical operators
**Applicable to:**
- `ProgramIntent_LogicSimplification` — Core boolean algebra simplification
- `ProgramIntent_FlowOptimization` — Short-circuit reduces evaluations in conditionals
- `Pattern_ConditionalSimplification` — Directly addresses ordering of conditions for short-circuit efficiency

**Reasoning:** Python already short-circuits `and`/`or`, but the LLM should know to (a) order conditions cheapest-first, (b) place most-likely-false conditions first for `and`, (c) place most-likely-true first for `or`.

---

#### G5 — Approximate computations when high precision is not needed
**Applicable to:**
- `ProgramIntent_PurposeAlignment` — Choosing the right level of precision for the task
- `AlgorithmicIntent_ComplexityReduction` — Approximation can drastically reduce complexity (e.g., integer math vs float, bitwise vs division)

**Reasoning:** This is a semantic-level decision — the LLM needs to understand the program's purpose to know if precision is expendable. Not suitable for syntactic mutators.

---

#### G6 — Avoid storing or recomputing unnecessary data
**Applicable to:**
- `AlgorithmicIntent_ComplexityReduction` — Eliminate dead stores and redundant computation
- `ProgramIntent_LogicSimplification` — Remove debug-only variables, redundant intermediates
- `Pattern_LoopOptimization` — Avoid recomputing invariant values inside loops

**Reasoning:** Covers two sub-cases: (1) avoiding re-computation of already-known values, (2) avoiding keeping unnecessary variables alive. Both have energy and memory implications.

---

#### G7 — Use bulk operations to reduce per-item overhead
**Applicable to:**
- `AlgorithmicIntent_ArchitecturalImprovement` — Batching is an architectural pattern
- `AlgorithmicIntent_ComplexityReduction` — Reduces amortized cost per operation
- `Pattern_FunctionComposition` — Batching multiple calls into one

**Reasoning:** Calling an operation once on N items is typically far cheaper than N individual calls (reduced function call overhead, better CPU/memory pipeline usage).

---

#### G14 — Cache frequently used data shared by processes or nodes
**Applicable to:**
- `AlgorithmicIntent_PatternRecognition` — Recognizing data that's recomputed repeatedly
- `AlgorithmicIntent_ArchitecturalImprovement` — Caching as an architectural concern
- `ProgramIntent_FlowOptimization` — Avoiding repeated computation in hot paths
- `Pattern_FunctionComposition` — Caching strategies (memoization at function level)

**Reasoning:** At the code level this manifests as caching computed results in local variables, dicts, or using `functools.lru_cache`. Distinct from G18 (which focuses on pure-function memoization specifically).

---

#### G17 — Avoid calling heavy functions (e.g., NumPy) within loops
**Applicable to:**
- `ProgramIntent_FlowOptimization` — Restructuring control flow to hoist heavy calls
- `Pattern_LoopOptimization` — Directly: the prompt already notes "LOCAL VARIABLE CACHING: Cache attribute lookups and method calls in hot loops"
- `AlgorithmicIntent_ComplexityReduction` — Hoisting out of loops reduces multiplied cost

**Reasoning:** Each NumPy call (or any library call) has significant overhead (GIL, C extension entry, etc.). If called N times in a loop unnecessarily, this multiplies energy waste by N. The fix is to hoist the call out, vectorize it, or restructure.

---

#### G18 — Memoization for expensive pure functions
**Applicable to:**
- `AlgorithmicIntent_PatternRecognition` — Recognizing pure functions with repeated calls
- `ProgramIntent_FlowOptimization` — Adding `functools.lru_cache` or dict-based memoization
- `Pattern_FunctionComposition` — Caching strategies explicitly mentioned in prompt

**Reasoning:** Memoization is one of the highest-leverage optimizations for recursive or repeatedly-called pure functions. The LLM can add `@functools.lru_cache(maxsize=None)` or manual dict caching.

---

#### G19 — Reduce function calls; use static methods and inline code
**Applicable to:**
- `ProgramIntent_FlowOptimization` — Reducing call overhead in hot paths
- `ProgramIntent_LogicSimplification` — Inlining trivial single-use functions
- `Pattern_FunctionComposition` — Directly about function call overhead; prompt mentions "INLINE OPTIMIZATION"

**Reasoning:** Python function calls are expensive (~100ns overhead each). In tight loops, inlining small functions or converting to static methods/lambdas saves measurable energy.

---

#### G20 — Reduce number of created objects
**Applicable to:**
- `AlgorithmicIntent_ArchitecturalImprovement` — Object creation patterns at architecture level
- `ProgramIntent_PurposeAlignment` — Evaluating if object creation is necessary for the purpose
- `Pattern_LoopOptimization` — Explicitly mentioned: "Reduce object creation in hot loops"

**Reasoning:** Object allocation triggers GC pressure in Python. Creating objects inside loops is particularly costly. The LLM should prefer reusing objects, using slots, or avoiding unnecessary wrappers.

---

#### G21 — Use energy-efficient design patterns (Flyweight, Mediator, Proxy); avoid Decorator and Abstract Factory
**Applicable to:**
- `AlgorithmicIntent_ArchitecturalImprovement` — Directly about design pattern selection
- `ProgramIntent_PurposeAlignment` — Choosing the right pattern for the purpose

**Reasoning:** The architectural improvement mutator explicitly considers design patterns. Flyweight reduces object count (complements G20), Mediator reduces coupling and call overhead, Proxy enables lazy loading. Decorator and Abstract Factory add indirection layers that increase call overhead.

---

#### G24 — Use HPC libraries (NumPy, SciPy) for computationally intensive tasks
**Applicable to:**
- `AlgorithmicIntent_ComplexityReduction` — Replacing Python loops with vectorized NumPy operations
- `AlgorithmicIntent_PatternRecognition` — Recognizing array/matrix operations suitable for NumPy
- `ProgramIntent_PurposeAlignment` — For numerical tasks, NumPy is the right tool
- `AlgorithmicIntent_ArchitecturalImprovement` — NumPy usage as architectural decision

**Reasoning:** NumPy operations run in optimized C/Fortran code at SIMD speeds. Replacing an O(n) Python loop with a NumPy vectorized operation can achieve 10-100x speedup in both time and energy.

---

#### G28 — Minimize memory accesses; aggregate I/O calls
**Applicable to:**
- `AlgorithmicIntent_ArchitecturalImprovement` — Memory access pattern design
- `AlgorithmicIntent_ComplexityReduction` — Aggregating I/O reduces total call count
- `Pattern_LoopOptimization` — Chunking data to reduce I/O calls per iteration

**Reasoning:** Memory bandwidth is a primary energy consumer in modern hardware. Aggregating small reads/writes into bulk operations reduces overhead. This is especially relevant for I/O-heavy code.

---

### PARTIALLY APPLICABLE GUIDELINES (mention as suggestions, not primary focus)

---

#### G9 — Reduce data dependencies between iterations for parallelizability
**Applicable to:**
- `AlgorithmicIntent_ArchitecturalImprovement` — Restructuring to enable parallelism

**Reasoning:** Fully applying G9 requires multi-threading support beyond single-function scope. However, the LLM can note opportunities to reduce loop-carried dependencies as an architectural suggestion.

---

#### G15 — Use compiled language extensions (Cython/Numba/SWIG) for critical sections
**Applicable to:**
- `ProgramIntent_PurposeAlignment` — As a high-level recommendation for performance-critical code

**Reasoning:** This is a major transformation (language boundary crossing). The LLM can identify hot functions as candidates for Numba `@jit` decoration or note them as Cython candidates, but cannot fully rewrite them in another language. Use as a suggestion only.

---

### NOT APPLICABLE TO LLM MUTATORS

These guidelines operate at the system, framework, or build level — outside the scope of per-function code mutation:

| Guideline | Reason Not Applicable |
|-----------|----------------------|
| G8 — Delegate to ctypes to avoid GIL | Requires significant FFI infrastructure, not a code-level mutation |
| G10 — Use PyOpenGL/mpi4py frameworks | Framework selection, not code mutation |
| G11 — Thread shuffling for multithreading | OS/runtime-level scheduling |
| G12 — Work-stealing dynamic scheduling | Runtime/scheduler level |
| G13 — Put threads on sleep for I/O | Threading pattern, requires thread infrastructure |
| G16 — Compiler optimization flags | Build system level |
| G22 — Compress data before network transmission | Network/serialization layer |
| G23 — Offload to cloud hardware | Infrastructure decision |
| G25 — Offload to GPUs | Requires CUDA/GPU infrastructure |
| G26 — Allocate all CPU cores | Process/OS level |
| G27 — Replace Python structures with HDF5 | Major data layer change, not function-level |

---

## Summary Matrix

Each row = guideline, each column = LLM mutator strategy. `X` = primary, `(x)` = secondary/suggestion.

| Guideline | AIM_Complexity | AIM_Pattern | AIM_Arch | PIM_Logic | PIM_Flow | PIM_Purpose | CPO_Loop | CPO_Cond | CPO_Func |
|-----------|---------------|-------------|---------|---------|---------|------------|---------|---------|---------|
| G1 (CSE) | X | X | | X | | | X | | |
| G2 (sort) | X | X | | | X | | | | |
| G3 (loops) | X | X | | | X | | X | | |
| G4 (short-circuit) | | | | X | X | | | X | |
| G5 (approx) | (x) | | | | | X | | | |
| G6 (no recompute) | X | | | X | | | X | | |
| G7 (bulk ops) | X | | X | | | | | | X |
| G14 (cache data) | | X | X | | X | | | | X |
| G15 (Cython/Numba) | | | | | | (x) | | | |
| G17 (no heavy in loops) | X | | | | X | | X | | |
| G18 (memoize) | | X | | | X | | | | X |
| G19 (reduce calls) | | | | X | X | | | | X |
| G20 (fewer objects) | | | X | | | X | X | | |
| G21 (design patterns) | | | X | | | X | | | |
| G24 (NumPy/SciPy) | X | X | X | | | X | | | |
| G28 (minimize mem I/O) | X | | X | | | | X | | |
| G9 (data deps) | | | (x) | | | | | | |

---

## Rationale for Excluded Guidelines

- **G5** is excluded from syntactic/flow mutators because approximation requires understanding the *meaning* of the computation, which is a semantic/purpose-level decision.
- **G7** is excluded from conditional/flow mutators because batching is an architectural restructuring, not a local code pattern.
- **G21** is excluded from syntactic mutators because design pattern changes affect program structure, not local syntax.
- **G24** is excluded from syntactic mutators because introducing NumPy changes imports and data types — this is a semantic concern.
