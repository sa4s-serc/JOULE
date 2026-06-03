# JOULE Improvement Plan

Ordered by expected optimization quality gain, highest first.
Each item includes: what changes, which files, how to verify.

---

## Guiding Principles

1. Every change must be independently mergeable and testable.
2. Deterministic operators ship with golden snapshot tests.
3. LLM operators ship with a precheck unit test and a prompt smoke test.
4. Surrogate changes must not break existing `screen_candidate` contract.
5. Registry/scoring changes are validated by running the example mock repo end-to-end.

---

## Phase 1 — Surrogate Feature Enrichment

**Expected gain:** surrogate screens better candidates earlier, fewer wasted measurements.
The current 17+5 feature vector is too coarse to distinguish smell categories.
Adding structural indicators doubles the predictive signal without changing any model.

### 1.1 Extend `SourceFeatureExtractor._base_features()`

File: `src/joule/surrogate/features.py`

Add 16 new boolean/count features after the existing 17:


```python
# New features to append to _base_features() in features.py

# Loop structural signals
has_nested_loop = int(any(
    isinstance(n, (ast.For, ast.While))
    for outer in nodes if isinstance(outer, (ast.For, ast.While))
    for n in ast.walk(outer) if n is not outer
))
loop_call_count = sum(
    1 for n in nodes
    if isinstance(n, (ast.For, ast.While))
    and any(isinstance(c, ast.Call) for c in ast.walk(n))
)

# Exception and control flow signals
try_except_count = sum(isinstance(n, ast.Try) for n in nodes)
has_bare_except = int(any(
    h.type is None
    for n in nodes if isinstance(n, ast.Try)
    for h in n.handlers
))

# String / memory signals
augassign_count = sum(isinstance(n, ast.AugAssign) for n in nodes)
has_string_concat_loop = int(any(
    isinstance(n, (ast.For, ast.While)) and any(
        isinstance(c, ast.AugAssign) and isinstance(c.op, ast.Add)
        for c in ast.walk(n)
    )
    for n in nodes
))

# Recursive / reuse signals
has_recursive_call = int(any(
    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == n.name
        for c in ast.walk(n)
    )
    for n in nodes
))

# Scope and attribute signals
max_attr_chain_depth = max(
    (sum(1 for _ in iter(lambda n=n: (n := n.value) if isinstance(n, ast.Attribute) else None, None))
     for n in nodes if isinstance(n, ast.Attribute)), default=0
)
import_count = sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes)

# Comprehension vs loop ratio
comp_to_loop_ratio = float(comp_count) / max(1.0, float(loop_count + comp_count))

# Data structure signals
list_in_loop = int(any(
    isinstance(n, (ast.For, ast.While)) and any(isinstance(c, ast.List) for c in ast.walk(n))
    for n in nodes
))
dict_subscript_in_loop = int(any(
    isinstance(n, (ast.For, ast.While)) and any(isinstance(c, ast.Subscript) for c in ast.walk(n))
    for n in nodes
))

# Yield / generator signals
yield_count = sum(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in nodes)

# Boolean and comparison signals
bool_op_count = sum(isinstance(n, ast.BoolOp) for n in nodes)
named_expr_count = sum(isinstance(n, ast.NamedExpr) for n in nodes)
```

Bump `FEATURE_SCHEMA_VERSION` from 1 to 2 in `src/joule/surrogate/types.py`.
This invalidates stale cached features automatically (the facade checks schema version).

**Verification:** run `pytest tests/` — no schema tests should fail since the cache is version-gated.
Add a unit test in `tests/test_surrogate_features.py` asserting the new feature vector length is 33.


---

## Phase 2 — Taxonomy-Aware Operator Routing

**Expected gain:** operator selection spends budget on operators whose smell targets match the
code under analysis, reducing wasted precheck failures and correctness rejections by an
estimated 20–35%.

### 2.1 Add `SmellTagger` utility

New file: `src/joule/transformers/smell_tagger.py`

A lightweight, pure-AST rule-based tagger that maps a source string to a set of taxonomy
category tags (C1–C12). No ML, no LLM. Used only for scoring, never for filtering.

```python
# src/joule/transformers/smell_tagger.py

SMELL_TAGS = frozenset([
    "C1",  # Redundant Computation
    "C2",  # Unnecessary Call Overhead
    "C3",  # Inefficient Iteration
    "C4",  # Inefficient Control Flow
    "C5",  # Suboptimal Data Structures
    "C6",  # Unnecessary Memory
    "C7",  # Suboptimal Algorithmic
    "C8",  # Missing Reuse
    "C9",  # Inefficient External Data Access
    "C10", # Underused Language Primitives
    "C11", # Inefficient Concurrency
    "C12", # Poor Hardware Locality
])

def tag_source(source: str) -> frozenset[str]:
    """Return the set of smell category tags likely present in source."""
    try:
        tree = ast.parse(source)
        nodes = list(ast.walk(tree))
    except SyntaxError:
        return frozenset()

    tags: set[str] = set()

    # C1: redundant computation indicators
    if _has_dead_assignment(nodes):
        tags.add("C1")

    # C3: iteration smells
    if _has_loop(nodes):
        tags.add("C3")
    if _has_nested_loop(nodes):
        tags.add("C3")

    # C4: control flow smells
    if _has_consecutive_ifs(tree):
        tags.add("C4")
    if _has_bare_except(nodes):
        tags.add("C4")

    # C5: data structure smells
    if _has_list_membership_check(nodes):
        tags.add("C5")

    # C6: memory smells
    if _has_list_in_loop(nodes):
        tags.add("C6")
    if _has_open_without_with(nodes):
        tags.add("C6")
    if _has_mutable_default_arg(nodes):
        tags.add("C6")

    # C7: algorithmic smells
    if _has_recursive_call(nodes):
        tags.add("C7")
    if _has_nested_loop(nodes):
        tags.add("C7")

    # C8: missing reuse
    if _has_repeated_calls(nodes):
        tags.add("C8")
    if _has_regex_runtime_call(nodes):
        tags.add("C8")

    # C10: language primitives
    if _has_manual_range_index_loop(nodes):
        tags.add("C10")
    if _has_string_concat_loop(nodes):
        tags.add("C10")

    return frozenset(tags)
```

Each `_has_*` helper is a simple AST predicate (10–20 lines each, reusing logic already
present in `llm_base.py` and deterministic operator precheks).

### 2.2 Add `targets_smells` to `BaseOperator`

File: `src/joule/transformers/base.py`

```python
class BaseOperator(ABC):
    targets_smells: ClassVar[frozenset[str]] = frozenset()  # add this line
```

Then annotate each existing operator with its primary smell categories.
Examples:

```python
# loop_global_to_local_hoisting.py
targets_smells = frozenset(["C8", "C10"])

# memoization_addition.py
targets_smells = frozenset(["C8"])

# container_membership_operator.py
targets_smells = frozenset(["C5"])

# string_concat_to_join.py
targets_smells = frozenset(["C10"])
```

### 2.3 Add smell-overlap bonus to `OperatorRegistry._contextual_score()`

File: `src/joule/transformers/registry.py`

Extend `_contextual_score()` to accept the target source (passed through from
`select_operator` / `ranked`) and apply a bonus when operator smell targets overlap
with the tagger output:

```python
_SCORE_SMELL_OVERLAP_BONUS = 0.30

def _contextual_score(self, op_name, total_attempts, *, phase, parent_generation,
                      smell_tags: frozenset[str] = frozenset()) -> float:
    # ... existing score calculation ...
    if smell_tags and operator.targets_smells:
        overlap = len(operator.targets_smells & smell_tags) / max(1, len(smell_tags))
        score += _SCORE_SMELL_OVERLAP_BONUS * overlap
    return score
```

Pass `smell_tags=SmellTagger.tag_source(target.source)` from the orchestrator's
`select_operators_for_candidate()` call site in `mfbo.py`.

**Verification:** add a unit test asserting that for a source with a known smell pattern,
the operator targeting that smell ranks higher than one that does not.


---

## Phase 3 — ROI-Priority Weighting for Operator Selection

**Expected gain:** budget allocation shifts toward high-ROI smell categories.
The Energy-Smells taxonomy paper empirically shows memory smells (C6) yield the highest
per-fix energy savings. Control flow smells (C4) are the most common but lowest per-fix ROI.
Encoding this as a static multiplier costs nothing at runtime.

### 3.1 Add `SMELL_ROI_WEIGHT` table and apply it in registry scoring

File: `src/joule/transformers/registry.py`

```python
# Empirically derived from Energy-Smells taxonomy paper measurements.
# Normalized so that the median (C3/C10) = 1.0.
SMELL_ROI_WEIGHT: dict[str, float] = {
    "C6":  1.40,   # Memory — highest energy savings per fix
    "C9":  1.30,   # I/O access — high when applicable
    "C11": 1.20,   # Concurrency
    "C8":  1.15,   # Missing reuse
    "C7":  1.10,   # Algorithmic
    "C12": 1.05,   # Hardware locality
    "C5":  1.00,   # Data structures (median)
    "C3":  1.00,   # Iteration (median)
    "C10": 0.95,   # Language primitives
    "C2":  0.85,   # Call overhead
    "C1":  0.80,   # Redundant computation (common, lower individual ROI)
    "C4":  0.75,   # Control flow (most common, lowest individual ROI)
}

def _smell_roi_multiplier(targets_smells: frozenset[str]) -> float:
    if not targets_smells:
        return 1.0
    return sum(SMELL_ROI_WEIGHT.get(s, 1.0) for s in targets_smells) / len(targets_smells)
```

Apply as a final multiplier to the contextual score:

```python
score = base_score * _smell_roi_multiplier(operator.targets_smells)
```

This is a pure additive change to the existing scoring formula with no structural changes.

**Verification:** unit test that given two operators with equal UCB scores, the one
targeting C6 ranks above the one targeting C4.

---

## Phase 4 — Tier-Phase Coupling (Exploit the Tier Model)

**Expected gain:** prevents Tier H LLM calls from burning budget in early exploration when
cheap Tier L wins are likely available. Mirrors how a human refactors: syntactic first,
semantic second, algorithmic last.

### 4.1 Add phase-tier preference to `OperatorRegistry.ranked()`

File: `src/joule/transformers/registry.py`

```python
_TIER_PHASE_BONUS: dict[tuple[str, str], float] = {
    # (tier, phase): bonus
    ("L", "exploration"):   0.40,
    ("M", "exploitation"):  0.35,
    ("H", "exploitation"):  0.20,
    ("H", "confirmation"):  0.30,
    ("L", "exploitation"):  0.10,
    ("M", "exploration"):   0.05,
}
```

Apply as a lookup bonus in `_contextual_score()`:

```python
phase_tier_bonus = _TIER_PHASE_BONUS.get(
    (operator.tier.value, phase.value if phase else "exploration"), 0.0
)
score += phase_tier_bonus
```

The values are chosen so that in exploration, Tier L operators get a +0.40 head start
over Tier H (+0.00), which is reversible if a Tier H operator has a very strong
historical success rate.

This is a non-breaking additive change. Existing behavior is preserved when all operators
have equal historical stats (the bonus still allows Tier H to win on high reward history).

**Verification:** integration test running mock repo optimization — confirm at least one
Tier L operator is applied before any Tier H in the first three candidates.


---

## Phase 5 — New Deterministic Operators (Batch A: High Confidence)

**Expected gain:** expands transformation surface area into smell categories C1, C4, C6
that are currently undercovered. All operators are AST-only, zero LLM cost, and follow
the established `AstTransformOperator` / `BaseOperator` pattern.

Each operator ships with:
- implementation in `src/joule/transformers/deterministic/<name>.py`
- export in `src/joule/transformers/deterministic/__init__.py`
- entry in `default_deterministic_operators()` list
- golden snapshot test entry
- `targets_smells` annotation (Phase 2)

### 5.1 `TryExceptToDefaultGet` — C4.S6

Detects the pattern:
```python
try:
    v = d[key]
except KeyError:
    v = default
```
and rewrites to `v = d.get(key, default)`.

Precheck: `ast.Try` node with a single `except KeyError` handler whose body is a single
assignment, and try body is also a single subscript assignment to the same target.

This is a guaranteed-safe rewrite. The LLM version (`TryExceptFastPathLLM`) handles
broader patterns; this handles the exact structural case deterministically.

### 5.2 `MultipleIfToElif` — C4.S4

Detects consecutive independent `if` statements testing the same variable or expression
where the conditions are mutually exclusive (range checks, equality against distinct
constants). Rewrites to `if/elif/else` chain.

Precheck: sequence of 3+ consecutive `ast.If` nodes in the same block whose test nodes
share a common `ast.Name` left-hand side in a `Compare`.

Safe when: all branches return or assign to the same target. The operator should generate
a candidate only when it can statically verify mutual exclusivity (distinct equality
checks or non-overlapping range comparisons).

### 5.3 `AugAssignNormalization` — C1.S2

Detects `x = x + expr` and `x = x - expr` patterns (where `x` is a simple `Name`) and
rewrites to `x += expr` / `x -= expr`.

Precheck: `ast.Assign` where target is `ast.Name`, value is `ast.BinOp` with `ast.Add`
or `ast.Sub`, and the BinOp's left operand is the same name as the target.

Extremely safe. The `AugAssign` form avoids a duplicate `LOAD_NAME` in CPython bytecode.

### 5.4 `BoolReturnFromCondition` — C1.S3 / C4.S8

Detects the pattern:
```python
if condition:
    return True
else:
    return False
```
(and the negated form) and rewrites to `return condition` (or `return not condition`).

This extends the existing `ReturnBoolSimplification` which only handles
`return x == True` / `return x is True` forms. This handles the full `if/return True`
structural pattern.

Precheck: `ast.If` node inside a function body where both branches are single `ast.Return`
nodes returning `ast.Constant(True)` and `ast.Constant(False)`.

### 5.5 `LoopInvariantLenCaching` — C3.S2 / C8.S3

Deterministic complement to the LLM `LoopInvariantHoistingLLM`. Detects `len(x)` calls
in loop conditions and loop bodies where `x` is not reassigned inside the loop.

```python
# Before
for i in range(len(data)):
    ...

# After
_len_data = len(data)
for i in range(_len_data):
    ...
```

Also handles `while i < len(lst):` form.

Precheck: `ast.For` or `ast.While` node whose `iter` or `test` contains a `Call` to
`len` with a `Name` argument. Verify the argument name is not in `assigned_names(loop)`.

The alias naming convention follows `LoopGlobalToLocalHoisting` to avoid collisions.

### 5.6 `MutableDefaultArgFix` — C6.S7

Deterministic version: detects `def f(x, acc=[])` and `def f(x, d={})` where a mutable
literal is used as a default argument value. Rewrites to `None` sentinel with internal
initialization.

```python
# Before
def f(items, result=[]):
    result.append(compute(items))
    return result

# After
def f(items, result=None):
    if result is None:
        result = []
    result.append(compute(items))
    return result
```

Precheck: any `ast.FunctionDef` with a default value that is `ast.List`, `ast.Dict`, or
`ast.Set`. The rewrite is always correct; mutable defaults are universally a bug.

### 5.7 `UselessPassElision` — C1.S1 / C1.S3

Removes `pass` statements from non-empty function/class/if bodies. A `pass` in an
otherwise non-empty block is dead code with real bytecode overhead.

Precheck: any `ast.Pass` node in a body with len > 1.

Does not touch functions or classes whose body is solely `pass` (those need the pass
to remain syntactically valid).


---

## Phase 6 — Cross-Run Surrogate Persistence

**Expected gain:** eliminates cold-start on every `joule run`. On a codebase optimized
more than once (the normal case in CI), the surrogate starts calibrated instead of
requiring `min_training_points` warm-up observations before it can screen.

This is the highest-impact surrogate change and requires the most code, but the schema
is already fully ready — all measurements are already in SQLite.

### 6.1 Add observation persistence to `JouleDB`

File: `src/joule/utils/db.py`

Add two methods:

```python
def save_surrogate_observations(
    self,
    *,
    file_path: str,
    function_name: str,
    schema_version: int,
    observations: list[dict],  # serialized SurrogateObservation records
) -> None:
    """Upsert observations keyed by (file_path, function_name, schema_version, source_hash)."""
    ...

def load_surrogate_observations(
    self,
    *,
    file_path: str,
    function_name: str,
    schema_version: int,
    limit: int = 100,
) -> list[dict]:
    """Return up to `limit` most recent observations for the given target."""
    ...
```

Schema: add a new table `surrogate_observations`:
```sql
CREATE TABLE IF NOT EXISTS surrogate_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    function_name TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    source_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    energy REAL NOT NULL,
    latency REAL NOT NULL,
    memory REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE(file_path, function_name, schema_version, source_hash)
);
```

### 6.2 Wire warm-start into `OptimizationOrchestrator.create()`

File: `src/joule/orchestrator/mfbo.py`

After `surrogate = ObjectiveSurrogate(...)`, load prior observations:

```python
prior_obs = db.load_surrogate_observations(
    file_path=str(target.file_path),
    function_name=target.function_name,
    schema_version=surrogate.feature_schema_version,
    limit=settings.surrogate.warm_start_limit,
)
for obs_record in prior_obs:
    surrogate.record(SurrogateObservation(
        source=obs_record["source"],
        targets=SurrogateMetricTargets.from_mapping(obs_record),
        feature_schema_version=obs_record["schema_version"],
    ))
```

### 6.3 Persist observations after each F3 measurement

In `mfbo.py`, after a candidate reaches F3 and its `AggregateMetrics` are confirmed,
call:

```python
db.save_surrogate_observations(
    file_path=str(target.file_path),
    function_name=target.function_name,
    schema_version=surrogate.feature_schema_version,
    observations=[{
        "source_hash": source_hash,
        "source": candidate.source,
        "energy": candidate_report.aggregate.mean_energy_j,
        "latency": candidate_report.aggregate.mean_wall_time_s,
        "memory": candidate_report.aggregate.mean_peak_memory_bytes,
    }],
)
```

Also persist the baseline measurement on first run so the surrogate has an anchor.

**Config:** respect the existing `surrogate.reuse_observations` setting as the kill switch.
If `reuse_observations = false`, skip the warm-start load entirely.

**Verification:** run `joule run` twice on the same target. On the second run, confirm
`events.jsonl` shows surrogate decisions firing from the first candidate (not waiting
for `min_training_points`).


---

## Phase 7 — New Deterministic Operators (Batch B: Memory & Reuse)

**Expected gain:** directly targets C6 (memory) and C8 (reuse) which have the highest
per-fix energy savings per the taxonomy paper. These operators fill the biggest coverage
gap in the current taxonomy-to-operator mapping.

### 7.1 `ListAppendInLoopToExtend` — C10.S3 / C6.S1

Detects a list initialized before a loop followed by repeated `.append()` inside the loop
where the loop iterates over a known collection and each iteration appends a transformed
value. Rewrites to a list comprehension or `.extend()`.

```python
# Before
result = []
for item in data:
    result.append(transform(item))

# After
result = [transform(item) for item in data]
```

This is a more aggressive form of `ForLoopToComprehension` but targeted specifically at
the accumulator pattern where a pre-initialized list exists outside the loop.

Precheck: `ast.Assign` of an empty list `[]` followed immediately in the same block by
`ast.For` containing a single `.append()` call in its body.

### 7.2 `RedundantCopyElision` — C6.S2

Detects `list(existing_list)` or `existing_list[:]` used as the sole argument to
`sorted()`, `reversed()`, or `list()` again, where the copy serves no purpose because
the consuming function does not modify the input.

```python
# Before
result = sorted(list(data))   # list() copy is unnecessary, sorted() doesn't mutate

# After
result = sorted(data)
```

Precheck: `ast.Call` to `sorted` / `reversed` / `list` / `tuple` / `set` whose single
argument is itself a `ast.Call` to `list` / `tuple` or a `ast.Subscript` slice of a
`Name` with no step.

### 7.3 `RegexPrecompilationDeterministic` — C8.S2

Deterministic complement to `RegexPrecompilationLLM`. Detects `re.search()`,
`re.match()`, `re.findall()`, `re.sub()` calls inside a loop body where the pattern
argument is a string literal. Hoists the `re.compile()` call to before the loop.

```python
# Before
for text in texts:
    if re.search(r"\d+", text):
        ...

# After
_pat = re.compile(r"\d+")
for text in texts:
    if _pat.search(text):
        ...
```

Precheck: `ast.For` / `ast.While` containing a `re.<method>` call whose first argument
is `ast.Constant` (string literal). Verify `re` is imported. Add `import re` if missing.

### 7.4 `ContextManagerWrap` — C6.S6

Detects bare `open(...)` calls assigned to a variable that is used within the same
function scope but never inside a `with` block. Wraps in `with open(...) as f:` and
adjusts the indentation of the using block.

Precheck: `ast.Assign` where the RHS is `ast.Call` to `open`, and the assigned name
is loaded at least once in a subsequent statement in the same block.

This is the most impactful C6 operator since resource leaks affect both energy and
reliability.


---

## Phase 8 — New LLM Operators (High-ROI Smell Categories)

**Expected gain:** covers smell categories completely absent from the current operator set.
Each operator follows the `LLMTransformationOperator` pattern: a class with `name`,
`tier`, `objective`, `precheck_node_types`, and `precheck_predicate`. No changes to the
generation pipeline are needed.

### 8.1 `ExceptionGuardElisionLLM` — C4.S7

`objective`: "Add trivial edge-case guards (empty input, zero-length, None checks)
at the top of the function to short-circuit expensive general processing."

`precheck`: function has at least one loop or sort/min/max call and no existing guard
at the entry point (no `if not x: return` or `if x is None: return` in the first 3 statements).

Tier M. High ROI: a single guard check can skip the entire function body for the
degenerate input case.

### 8.2 `ShortCircuitOrderingLLM` — C4.S1

`objective`: "Reorder AND/OR conditions so that cheap, high-probability-to-terminate
checks appear before expensive ones."

`precheck`: `ast.BoolOp` containing a mix of simple `ast.Compare` / `ast.Name` nodes
and `ast.Call` nodes in operand positions.

Tier M. The LLM has the reasoning capacity to determine which operand is cheaper.

### 8.3 `RedundantTypeConversionLLM` — C5.S4 / C1.S2

`objective`: "Remove redundant type conversion chains (e.g., int(int(x)), str(str(x)),
list(list(x))) and unnecessary conversions where the type is already correct."

`precheck`: any `ast.Call` where the function is a type name (`int`, `str`, `list`,
`float`, `tuple`) and the argument is itself a `ast.Call` to the same type name.

Tier L (deterministic logic is simple enough, but the LLM handles broader chains).

### 8.4 `OperationOrderOptimizationLLM` — C7.S4

`objective`: "Reorder filter-then-transform to transform-then-filter where semantically
safe, so that expensive operations receive the smallest possible input."

`precheck`: function contains at least one comprehension with an `if` clause, or a
sorted/map call followed by a filter/conditional expression.

Tier M. This is a semantic transformation requiring understanding of data flow.

### 8.5 `NumPyVectorizationLLM` — C10.S3 / C12.S1

`objective`: "Replace element-wise loops over numerical data with equivalent NumPy
vectorized operations. Import numpy as np if not already imported."

`precheck`: `ast.For` containing `ast.AugAssign` with arithmetic operations, and the
loop variable is used in arithmetic expressions. Only trigger if `numpy` is already
a project dependency (check target's `owner_path` / imports).

Tier H. Highest transformation impact for numerical code. The correctness gate
validates semantic equivalence.

### 8.6 `MissingLocalCacheLLM` — C8.S3

`objective`: "Cache repeated chained attribute lookups (obj.a.b.c) and repeated
built-in lookups in a local variable before the loop they appear in."

`precheck`: `ast.For` / `ast.While` body contains an `ast.Attribute` access chain
of depth ≥ 2 that appears more than once, where the root object is not reassigned
in the loop body.

Tier M. Complements the existing `LoopGlobalToLocalHoisting` which only handles
builtins; this handles attribute chains.

### 8.7 `AsyncParallelizationLLM` — C11.S5

`objective`: "Convert a sequential loop over independent I/O operations into
concurrent execution using asyncio.gather() or ThreadPoolExecutor.map()."

`precheck`: `ast.For` body contains exactly one `ast.Call` that either (a) is an
`await` expression, (b) calls a known I/O function (`requests.get`, `urllib`,
`open`, `socket`), or (c) calls a function whose name contains `fetch`, `download`,
`request`, `load`.

Tier H. The correctness gate is critical here — this operator should only propose
when parallelization is clearly safe (no shared mutable state in the loop body).

### 8.8 `DataClassSlotsLLM` — C5.S3 / C6.S1

`objective`: "Add __slots__ or slots=True to dataclasses and simple classes with
only __init__ attribute assignments, reducing per-instance memory overhead."

`precheck`: reuse existing `_class_without_slots` predicate from `llm_base.py`.
This already exists as `SlotsDelegateLLM` but the new version should also handle
Python 3.10+ `@dataclass(slots=True)` syntax and classes with inheritance.

Tier M. Complements `SlotsDelegateLLM` with broader coverage.

All 8 operators are registered in `src/joule/transformers/generative/__init__.py`
and added to `default_llm_operators()`.


---

## Phase 9 — Operator-Conditioned Surrogate Features

**Expected gain:** the surrogate learns that certain operators reliably help or hurt
for certain code shapes, instead of treating all candidates identically. This reduces
false escalations (measuring candidates that the surrogate would correctly predict
as poor if it knew which operator produced them).

### 9.1 Add operator identity to the feature vector

File: `src/joule/surrogate/features.py`

The `features()` method already accepts `feature_hints: dict[str, float]`. Extend the
convention: the orchestrator passes `feature_hints["operator_index"]` when building a
`SurrogateQuery` for screening.

```python
# In mfbo.py, when building the SurrogateQuery for a proposal:
all_operator_names = [op.name for op in registry.operators]
op_index = all_operator_names.index(proposal.operator_name) if proposal.operator_name in all_operator_names else -1
feature_hints = {
    **proposal.feature_hints,
    "operator_index": float(op_index),
    "operator_tier": float({"L": 0, "M": 1, "H": 2}.get(proposal.operator_tier.value, 0)),
}
```

In `SourceFeatureExtractor.features()`, the `operator_index` hint is already passed
through the `dynamic` array (it's in `feature_hints`). The `dynamic` vector currently
has 5 slots; add `operator_index` and `operator_tier` as slots 6 and 7.

This is a one-line change in `features.py` (extend the dynamic array) and a few lines
in the orchestrator to populate the hints. No model retraining needed — the GBDT
surrogate automatically discovers the operator-feature interaction.

**Bump `FEATURE_SCHEMA_VERSION` to 3** to invalidate stale cached features.

### 9.2 Operator success rate as a feature hint

Also pass the operator's current `success_rate` and `frontier_contribution_rate` from
the registry stats as feature hints:

```python
op_stats = registry.stats.get(proposal.operator_name, {})
feature_hints["op_success_rate"] = float(op_stats.get("success_rate", 0.5))
feature_hints["op_frontier_rate"] = float(op_stats.get("frontier_contributions", 0) / max(1, op_stats.get("attempts", 1)))
```

These encode the operator's current-run track record directly into the surrogate input,
allowing the model to screen out proposals from an operator that has been consistently
failing in this run.


---

## Phase 10 — Incremental Correctness Checking

**Expected gain:** for large test suites, correctness validation dominates the per-candidate
budget. Running a random 25% sample first halves the median correctness cost with < 5%
miss rate (missed failures discovered at full-suite stage which runs next).

### 10.1 Add `correctness_sample_fraction` config key

File: `src/joule/config.py`

```python
correctness_sample_fraction: float = 1.0   # 1.0 = full suite always (default, existing behavior)
```

Add to `JouleSettings`. Document in `pyproject.toml` example:
```toml
[tool.joule]
correctness_sample_fraction = 0.25   # fast pre-filter
```

### 10.2 Two-stage correctness check in `CorrectnessEngine`

File: `src/joule/evaluators/correctness.py`

```python
def check(self, target, candidate_source, bundle, *, sample_fraction=1.0):
    if sample_fraction < 1.0:
        # Stage 1: sample
        sampled_bundle = bundle.sample(fraction=sample_fraction, seed=hash(candidate_source))
        result = self._run_check(target, candidate_source, sampled_bundle)
        if not result.passed:
            return result   # fast reject, skip full suite
        # Stage 2: full suite
    return self._run_check(target, candidate_source, bundle)
```

`WorkloadBundle.sample(fraction, seed)` returns a new `WorkloadBundle` with a
deterministic random subset of its workloads.

The sample fraction is only applied for deterministic operators (Tier L) where the
failure modes are predictable. LLM operators always run the full suite because their
failure modes are more diverse.

### 10.3 Wire fraction from settings into orchestrator

File: `src/joule/orchestrator/mfbo.py`

Pass `sample_fraction` to `correctness.check()` based on operator tier:
```python
sample_fraction = (
    self.settings.correctness_sample_fraction
    if proposal.operator_tier == Tier.L else 1.0
)
```

**Verification:** unit test that `WorkloadBundle.sample(0.5)` returns exactly half the
workloads, deterministically for the same seed. Integration test: confirm two-stage
check catches a known-failing candidate at the sample stage.


---

## Phase 11 — Composition Chain Diversity Bonus

**Expected gain:** current composition chains can apply two operators targeting the same
smell category, which often produces no additional gain after the first transformation.
A diversity bonus directs compositions toward orthogonal smell categories.

### 11.1 Add diversity multiplier in `mfbo.py` composition logic

File: `src/joule/orchestrator/mfbo.py`

In the composition candidate building code, after the chain is assembled:

```python
def _composition_diversity(chain: list[BaseOperator]) -> float:
    """Returns [0, 1]. 1.0 = all operators target different smell categories."""
    if len(chain) <= 1:
        return 1.0
    smell_sets = [op.targets_smells for op in chain if op.targets_smells]
    if not smell_sets:
        return 0.5
    all_smells = set.union(*smell_sets)
    unique_categories = len(all_smells)
    total_claims = sum(len(s) for s in smell_sets)
    return min(1.0, unique_categories / max(1, total_claims))
```

Then scale the composition proposal rank:
```python
diversity = _composition_diversity(chain_operators)
composition_score_multiplier = 0.70 + (0.30 * diversity)
proposal.proposal_rank = int(proposal.proposal_rank * composition_score_multiplier)
```

A chain targeting C3 then C5 (diversity=1.0) gets full weight.
A chain targeting C3 twice (diversity=0.5) gets 0.85 weight.

This requires Phase 2 (`targets_smells` annotations) to be complete first.

---

## Phase 12 — Energy-Smells Dataset Warm-Start for Surrogate

**Expected gain:** the surrogate starts with an informed prior from 3,000 empirically
validated code pairs instead of cold. Eliminates the "first 5 candidates are noise"
problem on every run.

### 12.1 Build a static prior from the dataset

File: new `src/joule/surrogate/prior.py`

Parse `Energy-Smells-main/dataset/public_significant_energy_diff.jsonl` (or ship a
compiled subset as a package resource) at import time:

```python
def load_static_prior(extractor: SourceFeatureExtractor) -> list[SurrogateObservation]:
    """
    Load the public Energy-Smells dataset as surrogate observations.
    Only includes pairs where the "after" code has lower energy (true improvements).
    Normalizes energy values to be relative (ratio vs. baseline = 1.0).
    """
    ...
```

The dataset records contain `source_before`, `source_after`, `energy_before`,
`energy_after`. Each pair becomes two observations:
- baseline: `(source_before, targets(energy=1.0, latency=1.0, memory=1.0))`
- improved: `(source_after, targets(energy=ratio, latency=..., memory=...))`

### 12.2 Load prior during surrogate initialization

File: `src/joule/surrogate/facade.py`

Add a `load_static_prior` parameter to `ObjectiveSurrogate.__init__()`:

```python
if settings.surrogate.use_static_prior:   # new config key, default True
    prior_observations = load_static_prior(self._extractor)
    for obs in prior_observations[:settings.surrogate.warm_start_limit]:
        self.record(obs)
```

The static prior observations are recorded first (lowest priority in FIFO eviction)
so that live measurements from the current run always take precedence.

**Config key:** `surrogate.use_static_prior = true` (default). Can be disabled for
reproducibility testing.

**Note:** the dataset's `energy_before`/`energy_after` values are in joules from the
paper's test harness, not from JOULE's RAPL backend. Normalization to ratios (not
absolute values) makes this portable across measurement backends.


---

## Phase 13 — Surrogate-Guided Fidelity Escalation

**Expected gain:** stops spending F2/F3 budget on candidates the surrogate predicts will
barely improve or definitely regress. Also fast-tracks candidates with very high
predicted improvement by skipping F1 and going directly to F2.

### 13.1 Add adaptive fidelity hint to `SurrogateScreeningDecision`

File: `src/joule/surrogate/types.py`

Add a new field:
```python
@dataclass(slots=True)
class SurrogateScreeningDecision:
    ...
    suggested_max_fidelity: str = "F3"   # "F1", "F2", or "F3"
    suggested_min_fidelity: str = "F1"   # skip cheap stages if high confidence
```

### 13.2 Populate fidelity hints in `screen_candidate()`

File: `src/joule/surrogate/facade.py`

```python
# After computing acquisition_score and decision:

suggested_max = "F3"
suggested_min = "F1"

if prediction.uncertainty > 0.50:
    # Very uncertain — cap at F1 to avoid wasting F3 budget
    suggested_max = "F1"
elif expected_improvement < 0.02 and prediction.uncertainty < 0.15:
    # Confident small gain — cap at F2
    suggested_max = "F2"

if expected_improvement > 0.20 and prediction.uncertainty < 0.10:
    # High confidence large gain — skip F1, start at F2
    suggested_min = "F2"
```

### 13.3 Respect hints in the fidelity promotion logic

File: `src/joule/orchestrator/mfbo.py`

When deciding starting fidelity and maximum fidelity for a candidate, check
`screening["suggested_min_fidelity"]` and `screening["suggested_max_fidelity"]`
and apply them as bounds on the F1→F2→F3 ladder. The existing promotion thresholds
(score comparison, memory guard) remain fully in force as the final decision.

---

## Phase 14 — Auto-Suspend Underperforming Operators

**Expected gain:** stops wasting budget on operators that are consistently failing
in the current run without requiring manual `operator_kill_switches` configuration.

### 14.1 Add auto-suspend logic to `OperatorRegistry`

File: `src/joule/transformers/registry.py`

```python
AUTO_SUSPEND_MIN_ATTEMPTS = 10
AUTO_SUSPEND_CORRECTNESS_FAILURE_THRESHOLD = 0.85  # 85% correctness failure rate
AUTO_SUSPEND_DUPLICATE_THRESHOLD = 0.90            # 90% duplicate rate

def _should_auto_suspend(self, op_name: str) -> bool:
    stat = self.stats.get(op_name, {})
    attempts = stat.get("attempts", 0)
    if attempts < AUTO_SUSPEND_MIN_ATTEMPTS:
        return False
    correctness_failure_rate = stat.get("correctness_failures", 0) / attempts
    duplicate_rate = stat.get("duplicates", 0) / attempts
    return (
        correctness_failure_rate > AUTO_SUSPEND_CORRECTNESS_FAILURE_THRESHOLD
        or duplicate_rate > AUTO_SUSPEND_DUPLICATE_THRESHOLD
    )
```

In `ranked()`, filter out auto-suspended operators:
```python
return sorted(
    [op for op in self.operators
     if not self._should_auto_suspend(op.name)],
    key=lambda op: self._contextual_score(...),
    reverse=True,
)
```

Log suspended operators to the terminal reporter so the user can see which operators
were auto-suspended and why.

**Kill-switch override:** if `operator_kill_switches[op_name] = false` (explicit false),
the operator is never auto-suspended regardless of stats.

---

## Phase 15 — Taxonomy-Aware Explanation in Artifacts

**Expected gain:** makes JOULE educational, not just functional. Users understand *why*
a transformation improved energy, mapped to the research taxonomy. Zero runtime cost.

### 15.1 Map operator names to taxonomy categories

New file: `src/joule/transformers/taxonomy_map.py`

A static dict mapping every operator name to its primary taxonomy category and
subcategory ID:

```python
OPERATOR_TAXONOMY: dict[str, dict[str, str]] = {
    "MemoizationAddition": {
        "category": "C8",
        "category_name": "Missing Reuse",
        "subcategory": "C8.S1",
        "subcategory_name": "Missing Memoization Cache",
    },
    "container_membership": {
        "category": "C5",
        "category_name": "Suboptimal Data Structures",
        "subcategory": "C5.S1",
        "subcategory_name": "Inefficient Data Structure Choice",
    },
    # ... all 33+ operators mapped
}
```

### 15.2 Include taxonomy context in `synthesize_explanation()`

File: `src/joule/orchestrator/explainer.py`

When building the explanation for an accepted candidate, look up the winning
operator's taxonomy entry and append:

```
Energy reduction attributed to: C3.S2 (Recomputing Loop-Invariant Values).
Root cause: len(data) was recomputed on every iteration. Fix: hoisted to a
local variable before the loop, reducing per-iteration lookup overhead.
See: Energy Smells taxonomy, category C3 — Inefficient Iteration Patterns.
```

Include `taxonomy_category`, `taxonomy_subcategory` in `run_summary.json` under
the winning candidate record. This enriches the artifact schema without breaking
existing parsers (additive field).


---

## Summary Table

Phases ordered by expected optimization quality gain (highest first):

| Phase | What | Primary Files | Gain Category | Effort |
|---|---|---|---|---|
| 1 | Richer surrogate feature vector | `surrogate/features.py`, `surrogate/types.py` | Surrogate accuracy | Low |
| 2 | Taxonomy-aware operator routing | `transformers/smell_tagger.py`, `transformers/base.py`, `transformers/registry.py` | Selection efficiency | Medium |
| 3 | ROI-priority operator weighting | `transformers/registry.py` | Budget allocation | Low |
| 4 | Tier-phase coupling | `transformers/registry.py` | Tier usage discipline | Low |
| 5 | New deterministic operators (Batch A) | 7 new files in `transformers/deterministic/` | Surface area | Medium |
| 6 | Cross-run surrogate persistence | `utils/db.py`, `orchestrator/mfbo.py` | Cold-start elimination | Medium |
| 7 | New deterministic operators (Batch B) | 4 new files in `transformers/deterministic/` | Surface area (C6/C8) | Medium |
| 8 | New LLM operators (8 operators) | 8 new files in `transformers/generative/` | Surface area (C4/C6/C8/C11) | Medium |
| 9 | Operator-conditioned surrogate features | `surrogate/features.py`, `orchestrator/mfbo.py` | Surrogate accuracy | Low |
| 10 | Incremental correctness checking | `evaluators/correctness.py`, `config.py` | Pipeline speed | Medium |
| 11 | Composition chain diversity bonus | `orchestrator/mfbo.py` | Composition quality | Low |
| 12 | Energy-Smells dataset warm-start | `surrogate/prior.py`, `surrogate/facade.py` | Cold-start + calibration | Medium |
| 13 | Surrogate-guided fidelity escalation | `surrogate/facade.py`, `surrogate/types.py`, `orchestrator/mfbo.py` | Budget efficiency | Low |
| 14 | Auto-suspend underperforming operators | `transformers/registry.py` | Budget efficiency | Low |
| 15 | Taxonomy-aware explanations | `transformers/taxonomy_map.py`, `orchestrator/explainer.py` | UX / educational | Low |

**Effort key:** Low = 1–2 days; Medium = 3–5 days; High = 1+ week.

---

## Dependency Graph

Some phases build on each other. Safe to start in parallel otherwise:

```
Phase 1 (features) ──► Phase 9 (operator-conditioned features)
                   ──► Phase 12 (dataset warm-start)
                   ──► Phase 6 (persistence, needs version key)

Phase 2 (smell tagger) ──► Phase 3 (ROI weights, needs targets_smells)
                       ──► Phase 11 (composition diversity, needs targets_smells)

Phase 4 (tier-phase) — independent

Phase 5 (batch A operators) — independent
Phase 7 (batch B operators) — independent
Phase 8 (LLM operators) — independent, but more impactful after Phase 2 (smell routing)

Phase 6 (persistence) — independent; benefits from Phase 1 (richer features stored)

Phase 10 (incremental correctness) — independent
Phase 13 (fidelity hints) — independent; benefits from Phase 1 (better uncertainty)
Phase 14 (auto-suspend) — independent
Phase 15 (explanations) — independent; requires Phase 2 targets_smells annotations
```

---

## What To Build First

If starting with one engineer for one sprint:

1. **Phase 1** (extend features) + **Phase 3** (ROI weights) + **Phase 4** (tier-phase bonus) —
   all three touch only `registry.py` and `features.py`, ship together in one PR, no new files.
2. **Phase 5** (deterministic operators batch A) — 7 operators, follow existing patterns,
   each takes ~2 hours. Ship as a single PR with golden snapshot updates.
3. **Phase 2** (smell tagger) — new file + annotation pass over all operators.
   Can be done incrementally: ship the tagger first, annotate operators over time.
4. **Phase 6** (persistence) — medium effort, highest long-term compounding value.

The first sprint alone (phases 1, 3, 4, 5) adds 7 new transformations, improves operator
selection quality, and costs zero additional LLM calls.

