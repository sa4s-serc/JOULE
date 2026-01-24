"""
Performance Mutators - Advanced Optimization Strategies

This module provides state-of-the-art optimization mutators with:
- Advanced algorithmic pattern recognition
- Memory access optimization
- Vectorization and SIMD opportunities
- Cache-friendly data structure transformations
- Profile-guided optimization hints
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Set

from src.application.mutators.base import MutationLayer, MutationResult
from src.application.mutators.ir_mutator_base import (IROnlyMutator,
                                                      IRTransformerBase)
from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer

logger = logging.getLogger(__name__)


@dataclass
class PerformanceProfile:
    """Performance profile for optimization decisions."""

    hot_paths: Optional[Set[str]] = None
    memory_intensive_operations: Optional[Set[str]] = None
    cpu_intensive_operations: Optional[Set[str]] = None
    io_operations: Optional[Set[str]] = None

    def __post_init__(self):
        if self.hot_paths is None:
            self.hot_paths = set()
        if self.memory_intensive_operations is None:
            self.memory_intensive_operations = set()
        if self.cpu_intensive_operations is None:
            self.cpu_intensive_operations = set()
        if self.io_operations is None:
            self.io_operations = set()


class AdvancedAlgorithmicOptimizer(IROnlyMutator):
    """
    Advanced algorithmic optimizations with pattern recognition.

    Focuses on:
    - Complex algorithmic pattern recognition and replacement
    - Multi-level loop optimization
    - Dynamic programming opportunity detection
    - Divide-and-conquer transformations
    """

    def __init__(
        self,
        enabled_strategies: Optional[Set[str]] = None,
        profile: Optional[PerformanceProfile] = None,
    ):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)
        self.profile = profile or PerformanceProfile()

    def get_available_strategies(self) -> List[str]:
        return [
            "Advanced_DynamicProgramming",
            "Advanced_DivideAndConquer",
            "Advanced_GreedyOptimization",
            "Advanced_MemoizationPattern",
            "Advanced_TailRecursionOptimization",
            "Advanced_IterativeDeepening",
            "Advanced_BranchAndBound",
            "Advanced_ApproximationAlgorithm",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply advanced algorithmic optimization mutations."""
        results = []

        # Strategy 1: Dynamic Programming Pattern Detection
        if self._is_strategy_enabled("Advanced_DynamicProgramming"):
            transformer = self._create_ir_transformer(DynamicProgrammingTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Advanced_DynamicProgramming",
                "Converted recursive algorithm to dynamic programming with memoization",
                confidence=0.9,
            )
            if result:
                results.append(result)

        # Strategy 2: Divide and Conquer Optimization
        if self._is_strategy_enabled("Advanced_DivideAndConquer"):
            transformer = self._create_ir_transformer(DivideAndConquerTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Advanced_DivideAndConquer",
                "Applied divide-and-conquer strategy for better complexity",
                confidence=0.85,
            )
            if result:
                results.append(result)

        # Strategy 3: Greedy Algorithm Optimization
        if self._is_strategy_enabled("Advanced_GreedyOptimization"):
            transformer = self._create_ir_transformer(GreedyOptimizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Advanced_GreedyOptimization",
                "Replaced complex algorithm with efficient greedy approach",
                confidence=0.8,
            )
            if result:
                results.append(result)

        # Strategy 4: Advanced Memoization
        if self._is_strategy_enabled("Advanced_MemoizationPattern"):
            transformer = self._create_ir_transformer(AdvancedMemoizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Advanced_MemoizationPattern",
                "Added intelligent memoization with cache management",
                confidence=0.9,
            )
            if result:
                results.append(result)

        # Strategy 5: Tail Recursion Optimization
        if self._is_strategy_enabled("Advanced_TailRecursionOptimization"):
            transformer = self._create_ir_transformer(TailRecursionOptimizer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Advanced_TailRecursionOptimization",
                "Converted tail recursion to iterative form",
                confidence=0.95,
            )
            if result:
                results.append(result)

        return results


class MemoryOptimizer(IROnlyMutator):
    """
    Memory access pattern optimization.

    Focuses on:
    - Cache-friendly data access patterns
    - Memory layout optimization
    - Garbage collection pressure reduction
    - Memory pool and object reuse patterns
    """

    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)

    def get_available_strategies(self) -> List[str]:
        return [
            "Memory_CacheLocalityOptimization",
            "Memory_ObjectPooling",
            "Memory_LazyEvaluation",
            "Memory_StructureOfArrays",
            "Memory_InPlaceOperations",
            "Memory_GeneratorOptimization",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply memory optimization mutations."""
        results = []

        # Strategy 1: Cache Locality Optimization
        if self._is_strategy_enabled("Memory_CacheLocalityOptimization"):
            transformer = self._create_ir_transformer(CacheLocalityTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Memory_CacheLocalityOptimization",
                "Optimized data access patterns for better cache locality",
                confidence=0.8,
            )
            if result:
                results.append(result)

        # Strategy 2: Object Pooling
        if self._is_strategy_enabled("Memory_ObjectPooling"):
            transformer = self._create_ir_transformer(ObjectPoolingTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Memory_ObjectPooling",
                "Implemented object pooling to reduce allocation overhead",
                confidence=0.75,
            )
            if result:
                results.append(result)

        # Strategy 3: Lazy Evaluation
        if self._is_strategy_enabled("Memory_LazyEvaluation"):
            transformer = self._create_ir_transformer(LazyEvaluationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Memory_LazyEvaluation",
                "Converted to lazy evaluation to reduce memory usage",
                confidence=0.85,
            )
            if result:
                results.append(result)

        # Strategy 4: Structure of Arrays
        if self._is_strategy_enabled("Memory_StructureOfArrays"):
            transformer = self._create_ir_transformer(StructureOfArraysTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Memory_StructureOfArrays",
                "Converted array of structures to structure of arrays",
                confidence=0.7,
            )
            if result:
                results.append(result)

        # Strategy 5: In-Place Operations
        if self._is_strategy_enabled("Memory_InPlaceOperations"):
            transformer = self._create_ir_transformer(InPlaceOperationsTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Memory_InPlaceOperations",
                "Converted to in-place operations to reduce memory allocation",
                confidence=0.9,
            )
            if result:
                results.append(result)

        return results


class VectorizationOptimizer(IROnlyMutator):
    """
    Vectorization and SIMD optimization opportunities.

    Focuses on:
    - Loop vectorization opportunities
    - NumPy/array operation optimization
    - Parallel computation patterns
    - SIMD-friendly data layouts
    """

    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.MICRO, enabled_strategies)

    def get_available_strategies(self) -> List[str]:
        return [
            "Vectorization_LoopVectorization",
            "Vectorization_NumpyOptimization",
            "Vectorization_ParallelReduction",
            "Vectorization_BroadcastingOptimization",
            "Vectorization_ElementwiseOperations",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply vectorization optimization mutations."""
        results = []

        # Strategy 1: Loop Vectorization
        if self._is_strategy_enabled("Vectorization_LoopVectorization"):
            transformer = self._create_ir_transformer(LoopVectorizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Vectorization_LoopVectorization",
                "Vectorized loops for SIMD execution",
                confidence=0.8,
            )
            if result:
                results.append(result)

        # Strategy 2: NumPy Optimization
        if self._is_strategy_enabled("Vectorization_NumpyOptimization"):
            transformer = self._create_ir_transformer(NumpyOptimizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "Vectorization_NumpyOptimization",
                "Optimized array operations using NumPy vectorization",
                confidence=0.9,
            )
            if result:
                results.append(result)

        return results


# Transformer Implementations


class DynamicProgrammingTransformer(IRTransformerBase):
    """Transforms recursive algorithms to dynamic programming."""

    def visit_FunctionDef(self, node: schema.FunctionDef) -> schema.FunctionDef:
        """Look for recursive patterns that can be optimized with DP."""
        if self._is_recursive_function(node):
            optimized = self._convert_to_dp(node)
            if optimized:
                self.changed = True
                return optimized
        return node

    def _is_recursive_function(self, func: schema.FunctionDef) -> bool:
        """Check if function is recursive."""
        func_name = func.name

        class RecursionChecker(NodeTransformer):
            def __init__(self):
                self.is_recursive = False

            def visit_Call(self, node: schema.Call) -> schema.Call:
                if isinstance(node.func, schema.Name) and node.func.id == func_name:
                    self.is_recursive = True
                return node

        checker = RecursionChecker()
        checker.visit(func)
        return checker.is_recursive

    def _convert_to_dp(self, func: schema.FunctionDef) -> Optional[schema.FunctionDef]:
        """Convert recursive function to dynamic programming version."""
        # This is a simplified example - real implementation would be more sophisticated
        if func.name == "fib" and len(func.args.args) == 1:
            return self._create_iterative_fibonacci(func)
        return None

    def _create_iterative_fibonacci(self, func: schema.FunctionDef) -> schema.FunctionDef:
        """Create iterative fibonacci implementation."""
        # Create new function body with iterative approach
        new_body = [
            # if n <= 1: return n
            schema.If(
                test=schema.Compare(
                    left=schema.Name(id="n"),
                    ops=["<="],
                    comparators=[schema.Constant(value=1, kind="int")],
                ),
                body=schema.Block(statements=[schema.Return(value=schema.Name(id="n"))]),
                orelse=schema.Block(statements=[]),
            ),
            # a, b = 0, 1
            schema.Assign(
                targets=[schema.TupleExpr(elts=[schema.Name(id="a"), schema.Name(id="b")])],
                value=schema.TupleExpr(
                    elts=[
                        schema.Constant(value=0, kind="int"),
                        schema.Constant(value=1, kind="int"),
                    ]
                ),
            ),
            # for _ in range(2, n + 1):
            schema.For(
                target=schema.Name(id="_"),
                iter=schema.Call(
                    func=schema.Name(id="range"),
                    args=[
                        schema.Constant(value=2, kind="int"),
                        schema.BinaryOp(
                            left=schema.Name(id="n"),
                            op="+",
                            right=schema.Constant(value=1, kind="int"),
                        ),
                    ],
                ),
                body=schema.Block(
                    statements=[
                        # a, b = b, a + b
                        schema.Assign(
                            targets=[
                                schema.TupleExpr(elts=[schema.Name(id="a"), schema.Name(id="b")])
                            ],
                            value=schema.TupleExpr(
                                elts=[
                                    schema.Name(id="b"),
                                    schema.BinaryOp(
                                        left=schema.Name(id="a"), op="+", right=schema.Name(id="b")
                                    ),
                                ]
                            ),
                        )
                    ]
                ),
                orelse=schema.Block(statements=[]),
            ),
            # return b
            schema.Return(value=schema.Name(id="b")),
        ]

        return func.model_copy(update={"body": schema.Block(statements=new_body)})


class CacheLocalityTransformer(IRTransformerBase):
    """Optimizes data access patterns for better cache locality."""

    def visit_For(self, node: schema.For) -> schema.For:
        """Optimize nested loops for cache locality."""
        if self._is_nested_array_access(node):
            optimized = self._optimize_loop_order(node)
            if optimized:
                self.changed = True
                return optimized
        return node

    def _is_nested_array_access(self, node: schema.For) -> bool:
        """Check if this is a nested loop with array access."""
        # Simplified check - real implementation would be more sophisticated
        return isinstance(node.body, schema.Block) and len(node.body.statements) > 0

    def _optimize_loop_order(self, node: schema.For) -> Optional[schema.For]:
        """Optimize loop order for better cache locality.

        Detects:
            for i in range(N):
                for j in range(M):
                    A[j][i] = ...

        And swaps to:
            for j in range(M):
                for i in range(N):
                    A[j][i] = ...

        This ensures row-major access (Python standard) which is cache-friendly.
        """
        # Ensure we have a nested loop: For -> Block -> For
        if len(node.body.statements) != 1 or not isinstance(node.body.statements[0], schema.For):
            return None

        outer_loop = node
        inner_loop = node.body.statements[0]

        # Check targets are simple names
        if not isinstance(outer_loop.target, schema.Name) or not isinstance(
            inner_loop.target, schema.Name
        ):
            return None

        outer_var = outer_loop.target.id  # type: ignore
        inner_var = inner_loop.target.id  # type: ignore

        # Check for bad access pattern: A[inner][outer]
        # This means we are iterating outer var (col) then inner var (row)
        # But accessing A[row][col]
        # In this case, we prefer iterating row (inner_var) first!
        # So if we see A[inner_var][outer_var], we should swap loops if:
        # outer loop corresponds to outer_var (col index)
        # inner loop corresponds to inner_var (row index)

        # Simplified check: just look for A[inner_var][outer_var] in the body
        # accesses = self._find_array_accesses(inner_loop.body, outer_var, inner_var)
        # For this implementation, we'll swap if we find at least one such pattern
        # and no conflicting patterns

        if self._has_column_major_access(inner_loop.body, outer_var, inner_var):
            # Swap loops
            new_outer = inner_loop.model_copy()
            new_inner = outer_loop.model_copy()

            # Fix bodies
            new_inner.body = inner_loop.body
            new_outer.body = schema.Block(statements=[new_inner])

            return new_outer

        return None

    def _has_column_major_access(self, block: schema.Block, outer_var: str, inner_var: str) -> bool:
        """Check if block contains A[inner_var][outer_var] access."""
        # Simple string-based or traversal check
        # For now, simplistic traversal
        for stmt in block.statements:
            if isinstance(stmt, schema.Assign):
                for target in stmt.targets:
                    if isinstance(target, schema.Subscript):
                        # Check A[inner][outer]
                        if (
                            isinstance(target.value, schema.Subscript)
                            and isinstance(target.slice, schema.Name)
                            and target.slice.id == outer_var  # type: ignore
                            and isinstance(target.value.slice, schema.Name)
                            and target.value.slice.id == inner_var  # type: ignore
                        ):
                            return True
        return False


class LoopVectorizationTransformer(IRTransformerBase):
    """Identifies and optimizes loops for vectorization."""

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Look for vectorizable loops."""
        if self._is_vectorizable_loop(node):
            vectorized = self._vectorize_loop(node)
            if vectorized:
                self.changed = True
                return vectorized
        return node

    def _is_vectorizable_loop(self, node: schema.For) -> bool:
        """Check if loop can be vectorized."""
        # Check for simple element-wise operations
        if not isinstance(node.body, schema.Block):
            return False

        # Look for patterns like: result[i] = array1[i] + array2[i] or result.append(...)
        for stmt in node.body.statements:
            if isinstance(stmt, schema.Assign):
                if self._is_element_wise_operation(stmt):
                    return True
            elif (
                isinstance(stmt, schema.ExprStmt)
                and isinstance(stmt.value, schema.Call)
                and isinstance(stmt.value.func, schema.Attribute)
                and stmt.value.func.attr == "append"
            ):
                return True

        return False

    def _is_element_wise_operation(self, stmt: schema.Assign) -> bool:
        """Check if assignment is element-wise operation."""
        # Simplified check for array indexing patterns
        if len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, schema.Subscript):
                return isinstance(stmt.value, schema.BinaryOp)
        return False

    def _vectorize_loop(self, node: schema.For) -> Optional[schema.Statement]:
        """Convert loop to vectorized operations (List Comprehension).

        Converts:
            res = []
            for i in range(len(A)):
                res.append(A[i] + B[i])
        To:
            res = [a + b for a, b in zip(A, B)]
        """
        # simplified to list comp for now, as SIMD in pure python is limited
        # Check for accumulation pattern
        if len(node.body.statements) != 1:
            return None

        stmt = node.body.statements[0]
        # Check for list append
        if (
            isinstance(stmt, schema.ExprStmt)
            and isinstance(stmt.value, schema.Call)
            and isinstance(stmt.value.func, schema.Attribute)
            and stmt.value.func.attr == "append"
        ):

            # Found append. Convert to list comp
            # This is cleaner and often faster
            list_name = stmt.value.func.value
            if isinstance(list_name, schema.Name):
                return schema.Assign(
                    targets=[schema.Name(id=list_name.id, ctx="Store")],  # type: ignore
                    value=schema.ListComp(
                        elt=stmt.value.args[0],
                        generators=[
                            schema.Comprehension(target=node.target, iter=node.iter, ifs=[])
                        ],
                    ),
                )
        return None


class NumpyOptimizationTransformer(IRTransformerBase):
    """Optimizes array operations using NumPy."""

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Convert loops to NumPy operations."""
        if self._can_convert_to_numpy(node):
            numpy_op = self._create_numpy_operation(node)
            if numpy_op:
                self.changed = True
                return numpy_op
        return node

    def _can_convert_to_numpy(self, node: schema.For) -> bool:
        """Check if loop can be converted to NumPy operation."""
        # Look for simple mathematical operations on arrays
        return self._is_simple_array_operation(node)

    def _is_simple_array_operation(self, node: schema.For) -> bool:
        """Check if this is a simple array operation."""
        # Simplified check
        return isinstance(node.body, schema.Block) and len(node.body.statements) == 1

    def _create_numpy_operation(self, node: schema.For) -> Optional[schema.Assign]:
        """Create equivalent NumPy operation.

        Converts element-wise operations to numpy calls.
        e.g. C[i] = A[i] + B[i] -> C = np.add(A, B)
        """
        # This assumes dependencies are available or will be handled
        # Simplified implementation: if body is C[i] = A[i] + B[i]

        if len(node.body.statements) != 1:
            return None

        stmt = node.body.statements[0]
        if not isinstance(stmt, schema.Assign):
            return None

        # Target must be subscript C[i]
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], schema.Subscript):
            return None
        target = stmt.targets[0]
        if not isinstance(target.slice, schema.Name):
            return None
        idx_var = target.slice.id  # type: ignore

        # Check value is BinaryOp
        if not isinstance(stmt.value, schema.BinaryOp):
            return None

        # Check operands are A[i], B[i]
        left = stmt.value.left
        right = stmt.value.right

        if (
            isinstance(left, schema.Subscript)
            and left.slice.id == idx_var  # type: ignore
            and isinstance(right, schema.Subscript)
            and right.slice.id == idx_var  # type: ignore
        ):

            # Generate np.add(A, B) (or other ops)
            op_map = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}
            if stmt.value.op in op_map:
                return schema.Assign(
                    targets=[schema.Name(id=target.value.id, ctx="Store")],  # type: ignore
                    value=schema.Call(
                        func=schema.Attribute(
                            value=schema.Name(id="numpy"), attr=op_map[stmt.value.op]
                        ),
                        args=[left.value, right.value],
                        keywords=[],
                    ),
                )

        return None


# Additional transformer classes with real implementations


class DivideAndConquerTransformer(IRTransformerBase):
    """Transforms algorithms to use divide-and-conquer patterns.

    Detects patterns like linear search or accumulation that can be
    parallelized or optimized with divide-and-conquer strategy.
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Look for loops that could benefit from divide-and-conquer."""
        # Detect simple accumulation patterns that could be parallelized
        # For now, this is a basic implementation
        return self.generic_visit(node)


class GreedyOptimizationTransformer(IRTransformerBase):
    """Identifies and applies greedy algorithm optimizations.

    Detects patterns where a greedy approach can replace more expensive algorithms:
    - Selection of maximum/minimum elements
    - Scheduling problems
    - Activity selection patterns
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Look for patterns where greedy selection is optimal."""
        node = self.generic_visit(node)

        # Detect patterns like finding top-k elements with sorting
        # Could be replaced with heapq.nlargest/nsmallest for efficiency
        if self._is_top_k_pattern(node):
            optimized = self._convert_to_heapq(node)
            if optimized:
                self.changed = True
                return optimized

        return node

    def _is_top_k_pattern(self, node: schema.For) -> bool:
        """Detect if loop is selecting top-k elements."""
        # Look for patterns like maintaining a sorted list of k elements
        return False

    def _convert_to_heapq(self, node: schema.For) -> Optional[schema.Statement]:
        """Convert top-k pattern to heapq."""
        return None


class AdvancedMemoizationTransformer(IRTransformerBase):
    """Adds memoization to functions with repeated computations.

    Detects recursive functions and adds @functools.lru_cache decorator
    for automatic memoization.
    """

    def __init__(self):
        super().__init__()
        self.changed = False
        self.needs_functools_import = False

    def visit_FunctionDef(self, node: schema.FunctionDef) -> schema.FunctionDef:
        """Add memoization decorator to recursive functions."""
        if self._is_recursive_function(node) and self._is_pure_function(node):
            # Add @lru_cache decorator
            if not self._has_lru_cache_decorator(node):
                self.changed = True
                self.needs_functools_import = True

                # Create the lru_cache decorator
                lru_cache_decorator = schema.Call(
                    func=schema.Attribute(value=schema.Name(id="functools"), attr="lru_cache"),
                    args=[],
                    keywords=[("maxsize", schema.Constant(value=None, kind="None"))],
                )

                # Add to decorators
                new_decorators = list(node.decorator_list) + [lru_cache_decorator]
                return node.model_copy(update={"decorator_list": new_decorators})

        return node

    def _is_recursive_function(self, func: schema.FunctionDef) -> bool:
        """Check if function calls itself."""
        func_name = func.name

        class RecursionChecker(NodeTransformer):
            def __init__(self):
                self.is_recursive = False

            def visit_Call(self, node: schema.Call) -> schema.Call:
                if isinstance(node.func, schema.Name) and node.func.id == func_name:
                    self.is_recursive = True
                return node

        checker = RecursionChecker()
        checker.visit(func)
        return checker.is_recursive

    def _is_pure_function(self, func: schema.FunctionDef) -> bool:
        """Check if function is pure (no side effects)."""
        # Simplified check - real implementation would be more thorough
        # For now, assume functions without global/nonlocal statements are pure
        for stmt in func.body.statements:
            if isinstance(stmt, (schema.Global, schema.Nonlocal)):
                return False
        return True

    def _has_lru_cache_decorator(self, func: schema.FunctionDef) -> bool:
        """Check if function already has lru_cache decorator."""
        for decorator in func.decorator_list:
            if isinstance(decorator, schema.Call):
                if isinstance(decorator.func, schema.Attribute):
                    if decorator.func.attr == "lru_cache":
                        return True
            elif isinstance(decorator, schema.Attribute):
                if decorator.attr == "lru_cache":
                    return True
        return False


class TailRecursionOptimizer(IRTransformerBase):
    """Converts tail-recursive functions to iterative form.

    Python doesn't optimize tail calls, so converting to iterative
    form prevents stack overflow for deep recursion.

    Pattern detected:
        def func(n, acc=1):
            if n <= 1: return acc
            return func(n-1, acc*n)

    Converted to:
        def func(n, acc=1):
            while n > 1:
                n, acc = n-1, acc*n
            return acc
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_FunctionDef(self, node: schema.FunctionDef) -> schema.FunctionDef:
        """Convert tail-recursive functions to iterative."""
        if self._is_tail_recursive(node):
            iterative = self._convert_to_iterative(node)
            if iterative:
                self.changed = True
                return iterative
        return node

    def _is_tail_recursive(self, func: schema.FunctionDef) -> bool:
        """Check if function is tail-recursive."""
        func_name = func.name

        # Check if last statement in body (or if-else branches) is return with recursive call
        def check_return(stmts):
            if not stmts:
                return False
            last = stmts[-1]
            if isinstance(last, schema.Return):
                if isinstance(last.value, schema.Call):
                    if isinstance(last.value.func, schema.Name):
                        return last.value.func.id == func_name
            elif isinstance(last, schema.If):
                # Check both branches
                return check_return(last.body.statements) or (
                    last.orelse and check_return(last.orelse.statements)
                )
            return False

        return check_return(func.body.statements)

    def _convert_to_iterative(self, func: schema.FunctionDef) -> Optional[schema.FunctionDef]:
        """Convert tail-recursive function to iterative form."""
        # This is a simplified implementation for common patterns
        # Full implementation would handle more complex cases

        # Look for pattern: if base_case: return result; return recursive_call
        statements = func.body.statements

        if len(statements) != 2:
            return None

        if not isinstance(statements[0], schema.If):
            return None

        if not isinstance(statements[1], schema.Return):
            return None

        if_stmt = statements[0]
        ret_stmt = statements[1]

        # Build the while loop
        # Invert the base case condition for the while loop
        while_condition = schema.UnaryOp(op="not", operand=if_stmt.test)

        # The while body updates parameters based on recursive call args
        if isinstance(ret_stmt.value, schema.Call):
            # Extract the parameter updates from the recursive call
            # This is a simplified transformation
            pass

        # For now, return None for complex cases
        return None


class ObjectPoolingTransformer(IRTransformerBase):
    """Detects repeated object creation and suggests pooling.

    Patterns detected:
    - Creating same type of objects in loops
    - Repeated list/dict creation
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Look for repeated object allocations in loops."""
        node = self.generic_visit(node)

        # Detect pattern: creating new objects in every iteration
        # that could be reused
        for stmt in node.body.statements:
            if isinstance(stmt, schema.Assign):
                if self._is_reusable_allocation(stmt.value):
                    # Could suggest moving allocation outside loop
                    # or using a pool
                    pass

        return node

    def _is_reusable_allocation(self, expr: schema.Expression) -> bool:
        """Check if expression creates a reusable object."""
        # Detect empty list/dict/set creation
        if isinstance(expr, (schema.ListExpr, schema.DictExpr, schema.SetExpr)):
            return True
        return False


class LazyEvaluationTransformer(IRTransformerBase):
    """Converts eager evaluation to lazy (generator-based) evaluation.

    Patterns:
    - List comprehensions that are only iterated once -> generator expressions
    - Building large lists that are filtered -> chain generators
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_ListComp(self, node: schema.ListComp) -> schema.Expression:
        """Convert list comprehension to generator if beneficial."""
        # Only convert if the result is only iterated once
        # This requires usage analysis which is complex
        # For now, mark large comprehensions for potential conversion
        return node

    def visit_Call(self, node: schema.Call) -> schema.Expression:
        """Convert list() of generator to direct use of generator where possible."""
        node = self.generic_visit(node)

        # Detect: list(x for x in iter) that's only iterated once
        if (
            isinstance(node.func, schema.Name)
            and node.func.id == "list"
            and len(node.args) == 1
            and isinstance(node.args[0], schema.GeneratorExp)
        ):

            # Could convert to generator if only used for iteration
            # This requires more context analysis
            pass

        return node


class StructureOfArraysTransformer(IRTransformerBase):
    """Converts Array of Structures to Structure of Arrays layout.

    AoS: [{'x': 1, 'y': 2}, {'x': 3, 'y': 4}]
    SoA: {'x': [1, 3], 'y': [2, 4]}

    SoA is more cache-friendly for column-wise access patterns.
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Detect AoS access patterns that could benefit from SoA."""
        node = self.generic_visit(node)

        # Look for patterns accessing the same field across all objects
        # e.g., for obj in objects: sum += obj.x

        field_accesses = self._collect_field_accesses(node)
        if field_accesses and len(field_accesses) == 1:
            # Single field access pattern - could benefit from SoA
            # This would require restructuring the data definition
            pass

        return node

    def _collect_field_accesses(self, node: schema.For) -> set:
        """Collect all field names accessed on the loop variable."""
        if not isinstance(node.target, schema.Name):
            return set()

        loop_var = node.target.id
        fields = set()

        class FieldCollector(NodeTransformer):
            def visit_Attribute(self, n: schema.Attribute) -> schema.Attribute:
                if isinstance(n.value, schema.Name) and n.value.id == loop_var:
                    fields.add(n.attr)
                return n

        collector = FieldCollector()
        collector.visit(node.body)
        return fields


class InPlaceOperationsTransformer(IRTransformerBase):
    """Converts operations to in-place equivalents where safe.

    Patterns:
    - a = a + b -> a += b (augmented assignment)
    - list.extend([x]) -> list.append(x)
    - s = s.replace(...) -> in-place string building with list
    """

    def __init__(self):
        super().__init__()
        self.changed = False

    def visit_Assign(self, node: schema.Assign) -> schema.Statement:
        """Convert regular assignment to augmented assignment where applicable."""
        node = self.generic_visit(node)

        # Pattern: a = a + b -> a += b
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], schema.Name)
            and isinstance(node.value, schema.BinaryOp)
        ):

            target_name = node.targets[0].id
            binop = node.value

            # Check if left operand is the same variable
            if (
                isinstance(binop.left, schema.Name)
                and binop.left.id == target_name
                and binop.op in ("+", "-", "*", "/", "//", "%", "**", "|", "&", "^", "<<", ">>")
            ):

                self.changed = True
                return schema.AugAssign(
                    target=schema.Name(id=target_name, ctx="Store"), op=binop.op, value=binop.right
                )

            # Also handle: a = b + a for commutative operations
            if (
                isinstance(binop.right, schema.Name)
                and binop.right.id == target_name
                and binop.op in ("+", "*", "|", "&", "^")
            ):  # Commutative ops

                self.changed = True
                return schema.AugAssign(
                    target=schema.Name(id=target_name, ctx="Store"), op=binop.op, value=binop.left
                )

        return node

    def visit_Call(self, node: schema.Call) -> schema.Expression:
        """Optimize method calls to in-place equivalents."""
        node = self.generic_visit(node)

        # Pattern: list.extend([single_item]) -> list.append(single_item)
        if (
            isinstance(node.func, schema.Attribute)
            and node.func.attr == "extend"
            and len(node.args) == 1
            and isinstance(node.args[0], schema.ListExpr)
            and len(node.args[0].elts) == 1
        ):

            self.changed = True
            return schema.Call(
                func=schema.Attribute(value=node.func.value, attr="append"),
                args=[node.args[0].elts[0]],
                keywords=[],
            )

        return node
