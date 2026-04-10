# Transformations Reference

This document describes the full set of transformations currently implemented in JOULE.

## Runtime Inspection

Use the CLI to inspect the live catalog from your project settings:

```bash
./joule transformations <project_or_file_path> --output human
./joule transformations <project_or_file_path> --output json
```

The output reports operator name, family, tier, escape-only status, and AST precheck pattern nodes.

## Tier Model

- `L` (syntactic): local syntax-level rewrites with narrow structural matching.
- `M` (semantic): broader semantic rewrites (currently LLM-driven).
- `H` (algorithmic): data-structure or algorithm-level shifts with stronger upside and stricter guards.

## Deterministic Operators

The deterministic catalog is fully implemented and precheck-gated.

| Name | Tier | Precheck Nodes | Primary Rewrite |
|---|---|---|---|
| `ForLoopToComprehension` | `L` | `For` | Converts `append`-driven loops into list comprehensions. |
| `IteratorSubstitution` | `L` | `For` | Removes redundant `iter(...)` in `for` loops. |
| `ReductionListCompToGenerator` | `L` | `Call` | Rewrites reduction calls over list comprehensions to generator expressions. |
| `DictKeysMembershipElision` | `L` | `Compare` | Rewrites `k in d.keys()` to `k in d`. |
| `StringConcatToJoin` | `L` | `BinOp` | Rewrites chained string additions to `''.join(...)`. |
| `SortedToInPlaceSort` | `L` | `Assign` | Rewrites `xs = sorted(xs)` to `xs.sort()` when local guards are met. |
| `LocalImportHoisting` | `L` | `Import`, `ImportFrom` | Hoists safe stdlib local imports to module scope. |
| `JoinListCompToGenerator` | `L` | `Call` | Rewrites `sep.join([comp])` to `sep.join((gen))`. |
| `GeneratorToYieldFrom` | `L` | `For` | Rewrites pass-through yield loops to `yield from`. |
| `MultipleOrToSetMembership` | `L` | `BoolOp` | Rewrites `x == a or x == b ...` to `x in {...}`. |
| `EnumerateSubstitution` | `L` | `For` | Rewrites `range(len(seq))` indexing loops to `enumerate(seq)`. |
| `ListPopZeroToDeque` | `H` | `While` | Rewrites queue-like `list.pop(0)` usage to `collections.deque` + `popleft()`. |
| `FStringConversion` | `L` | `Call` | Rewrites simple `str.format(...)` templates to f-strings. |
| `MultipleAssignmentFusion` | `L` | `Assign` | Fuses adjacent independent assignments into tuple assignment. |
| `LoopGlobalToLocalHoisting` | `H` | `For`, `While` | Caches repeated builtin lookups (`len`, `sum`, ...) into locals before loops. |
| `ReturnBoolSimplification` | `L` | `If` | Simplifies boolean branch returns to direct `return cond` form. |
| `TupleUnpackInLoop` | `L` | `For` | Rewrites indexed tuple extraction in loops to tuple unpacking loop targets. |
| `ChainedComparisonFusion` | `L` | `BoolOp` | Rewrites `a < b and b < c` into chained comparisons. |
| `DictGetWithDefault` | `L` | `If` | Rewrites dictionary membership branch assignment to `.get(key, default)`. |
| `IdentityCompareNormalization` | `L` | `Compare` | Normalizes `== None` / `!= None` to `is None` / `is not None`. |
| `ConstantConditionElision` | `L` | `If` | Eliminates branches with constant boolean conditions. |
| `NotInNormalization` | `L` | `UnaryOp` | Rewrites `not (x in y)` to `x not in y`. |
| `ConcatListLiteralFusion` | `L` | `BinOp` | Rewrites `[...]+[...]` list literal concatenation to one literal. |
| `DataStructureSubstitution[list->set]` | `H` | `Compare` | Rewrites literal membership lists/tuples to set literals for faster lookup. |
| `LoopMembershipSetCache` | `H` | `For`, `While` | Materializes stable membership containers as sets outside loops. |
| `SeenSetForAppendDedup` | `H` | `If` | Rewrites append-based dedup loops to use side `seen` caches. |
| `MemoizationAddition` | `H` | `FunctionDef` | Adds `functools.lru_cache(maxsize=None)` to eligible recursive functions. |
| `DefaultDictSubstitution` | `H` | `If` | Rewrites guarded dict list initialization to `defaultdict` pattern. |
| `CounterSubstitution` | `H` | `If` | Rewrites manual frequency-map branches to `collections.Counter` increments. |
| `HeapNLargestSmallest` | `H` | `Subscript` | Rewrites `sorted(... )[:k]` variants to `heapq.nsmallest`/`nlargest`. |
| `container_membership` | `L` | `Compare` | Compatibility alias for literal membership container substitution. |
| `sum_generator` | `L` | `Call` | Compatibility alias for reduction list-comp to generator rewrite. |
| `empty_literal` | `L` | `Call` | Rewrites zero-arg `list()`/`dict()` to `[]`/`{}`. |

## LLM Operators

These operators are available when an LLM model is configured.

| Name | Tier | Objective |
|---|---|---|
| `GeneratorChainFusion` | `M` | Fuse adjacent generator/list stages into a lazy pipeline. |
| `EarlyExitOptimization` | `M` | Introduce semantically-safe early exits. |
| `CachingWrapper` | `M` | Add bounded caching for repeated deterministic computation. |
| `ManualReductionToBuiltinsLLM` | `M` | Replace manual reduction loops with builtins. |
| `LoopInvariantHoistingLLM` | `M` | Hoist loop-invariant computations out of loops. |
| `ItertoolsDelegateLLM` | `M` | Delegate iterative composition to `itertools`. |
| `MathToBitwiseLLM` | `M` | Convert safe arithmetic to equivalent bitwise forms. |
| `LazyEvaluationRewriteLLM` | `M` | Rewrite eager processing into lazy pipelines. |
| `RegexPrecompilationLLM` | `M` | Precompile repeated regex usage. |
| `DictDoubleHashEliminationLLM` | `M` | Eliminate repeated dictionary hash lookups. |
| `TryExceptFastPathLLM` | `M` | Keep common-case execution outside exception-heavy paths. |
| `SlotsDelegateLLM` | `M` | Introduce `__slots__` in suitable classes. |
| `ConcurrentMapDelegateLLM` | `M` | Parallelize independent map workloads where safe. |
| `BisectSubstitutionLLM` | `M` | Replace linear sorted-list searches with `bisect`. |
| `StringBuildBufferLLM` | `M` | Rewrite repeated string building to buffer-based patterns. |
| `RecursionToDynamicProgramming` | `H` | Convert recursive algorithms to dynamic programming. |
| `NaiveSearchToIndexed` | `H` | Replace repeated naive searches with indexed lookups. |
| `VectorizationDelegate[loop->numpy]` | `H` | Vectorize numeric loop workloads. |
| `AlgorithmicComplexityReduction` | `H` | Reduce asymptotic complexity through algorithmic refactor. |
| `LoopMembershipIndexingLLM` | `H` | Replace repeated membership checks with indexed structures. |
| `SeenSetDeduplicationLLM` | `H` | Introduce seen-set deduplication patterns. |
| `llm_generative` | `M` | General-purpose candidate generation with rationale. |

### Escape Operator

- `GenericSemanticRewriteLLM` (`H`, escape-only): broad semantic rewrite used as escape behavior when search stagnates.

## Snapshot Contract for Deterministic Output Shape

Deterministic source-to-source output shape is locked via golden snapshots:

- Snapshot payload: [tests/golden/deterministic_operator_snapshots.json](../tests/golden/deterministic_operator_snapshots.json)
- Snapshot test: [tests/test_transformer_golden_snapshots.py](../tests/test_transformer_golden_snapshots.py)

Run snapshot verification:

```bash
./.venv/bin/python -m pytest tests/test_transformer_golden_snapshots.py -q
```

## Example Function with Broader Optimization Surface

The mock example includes a richer function specifically for demonstration:

- Implementation: [example/mock_repo/sample_pkg/algos.py](../example/mock_repo/sample_pkg/algos.py)
- Test: [example/mock_repo/tests/test_algos.py](../example/mock_repo/tests/test_algos.py)

Function: `optimization_surface_demo`

It intentionally contains multiple rewrite opportunities so the transformations catalog is easier to observe in a single target.
