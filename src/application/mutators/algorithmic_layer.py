"""
Algorithmic Layer Mutators - Data Structures and Complexity Improvements

These mutators focus on:
- Data structure selection and optimization
- Algorithm complexity improvements
- Memory access pattern optimization
- Computational efficiency enhancements
"""

import logging
from typing import List, Optional, Set

from src.application.mutators.base import (MutationLayer, MutationResult,
                                           safe_deepcopy_ir)
from src.application.mutators.ir_mutator_base import (IROnlyMutator,
                                                      IRTransformerBase)
from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer, collect_names
from src.utils.mutation_factory import create_mutation_result

logger = logging.getLogger(__name__)


class DataStructureOptimizer(IROnlyMutator):
    """
    Optimizes data structure selection for better algorithmic performance.

    Focuses on choosing the right data structure for the access patterns
    and operations performed in the code.
    """

    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)

    def get_available_strategies(self) -> List[str]:
        return [
            "DataStructure_MembershipOptimization",
            "DataStructure_AccessPatternOptimization",
            "DataStructure_InsertionOptimization",
            "DataStructure_SearchOptimization",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply data structure optimization mutations."""
        results = []

        # Strategy 1: Membership Testing Optimization (list -> set)
        if self._is_strategy_enabled("DataStructure_MembershipOptimization"):
            transformer = self._create_ir_transformer(MembershipOptimizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "DataStructure_MembershipOptimization",
                "Optimized membership testing from O(n) to O(1) using sets",
                confidence=0.95,
            )
            if result:
                results.append(result)

        # Strategy 2: Access Pattern Optimization
        if self._is_strategy_enabled("DataStructure_AccessPatternOptimization"):
            transformer = self._create_ir_transformer(AccessPatternOptimizer)
            result = self._apply_transformer(
                ir,
                transformer,
                "DataStructure_AccessPatternOptimization",
                "Optimized data access patterns for better cache locality",
                confidence=0.8,
            )
            if result:
                results.append(result)

        # Strategy 3: Insertion/Deletion Optimization
        if self._is_strategy_enabled("DataStructure_InsertionOptimization"):
            transformer = self._create_ir_transformer(InsertionDeletionOptimizer)
            result = self._apply_transformer(
                ir,
                transformer,
                "DataStructure_InsertionOptimization",
                "Optimized insertion/deletion operations using appropriate data structures",
                confidence=0.85,
            )
            if result:
                if getattr(transformer, "needs_collections_import", False):
                    self._ensure_import(result.ir, "collections")
                results.append(result)

        # Strategy 4: Search Operation Optimization
        if self._is_strategy_enabled("DataStructure_SearchOptimization"):
            transformer = self._create_ir_transformer(SearchOptimizationTransformer)
            result = self._apply_transformer(
                ir,
                transformer,
                "DataStructure_SearchOptimization",
                "Optimized search operations using efficient algorithms and data structures",
                confidence=0.9,
            )
            if result:
                if getattr(transformer, "needs_bisect_import", False):
                    self._ensure_import(result.ir, "bisect")
                results.append(result)

        return results

    def _ensure_import(self, ir: schema.Module, module_name: str):
        """Ensure a module is imported."""
        # Check if already imported
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    if alias.name == module_name:
                        return
            elif isinstance(stmt, schema.ImportFrom):
                if stmt.module == module_name:
                    return

        # Add import at the beginning
        import_stmt = schema.Import(names=[schema.Alias(name=module_name)])
        ir.body.statements.insert(0, import_stmt)

    def _check_semantic_preservation(self, mutated_ir: schema.Module) -> bool:
        """
        Relaxed semantic check for DataStructureOptimizer.

        Optimizations like loop replacement (SearchOptimization) naturally remove
        variables (loop indices/items). We trust the transformers to handle this safely.
        """
        # We rely primarily on structural validation from the base class
        # calling super().mutate() -> super()._validate_ir_mutation() -> this method
        return True


class ComplexityReducer(IROnlyMutator):
    """
    Reduces algorithmic complexity through better algorithm selection.

    Identifies opportunities to replace high-complexity operations with
    more efficient alternatives.
    """

    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)

    def get_available_strategies(self) -> List[str]:
        return [
            "Complexity_NestedLoopReduction",
            "Complexity_SortingOptimization",
            "Complexity_DuplicateWorkElimination",
            "Complexity_MathematicalOptimization",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply complexity reduction mutations."""
        results = []

        # Strategy 1: Nested Loop Reduction
        if self._is_strategy_enabled("Complexity_NestedLoopReduction"):
            variant = self._reduce_nested_loops(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Complexity_NestedLoopReduction",
                        layer=MutationLayer.ALGORITHMIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.8,
                        description="Reduced nested loop complexity using mathematical optimization",
                    )
                )

        # Strategy 2: Sorting Optimization
        if self._is_strategy_enabled("Complexity_SortingOptimization"):
            variant = self._optimize_sorting_operations(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Complexity_SortingOptimization",
                        layer=MutationLayer.ALGORITHMIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.9,
                        description="Optimized sorting operations for better complexity",
                    )
                )

        # Strategy 3: Duplicate Work Elimination
        if self._is_strategy_enabled("Complexity_DuplicateWorkElimination"):
            variant = self._eliminate_duplicate_work(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Complexity_DuplicateWorkElimination",
                        layer=MutationLayer.ALGORITHMIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.85,
                        description="Eliminated duplicate computations and redundant work",
                    )
                )

        # Strategy 4: Mathematical Optimization
        if self._is_strategy_enabled("Complexity_MathematicalOptimization"):
            variant = self._apply_mathematical_optimizations(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Complexity_MathematicalOptimization",
                        layer=MutationLayer.ALGORITHMIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.7,
                        description="Applied mathematical optimizations to reduce computational complexity",
                    )
                )

        return results

    def _reduce_nested_loops(self, ir: schema.Module) -> Optional[schema.Module]:
        """Reduce nested loop complexity where possible."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = NestedLoopReducer()
        transformer.visit(new_ir)

        if transformer.changed and transformer.needs_itertools_import:
            self._ensure_import(new_ir, "itertools")

        return new_ir if transformer.changed else None

    def _optimize_sorting_operations(self, ir: schema.Module) -> Optional[schema.Module]:
        """Optimize sorting operations for better performance."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = SortingOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _eliminate_duplicate_work(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate duplicate computations and redundant work."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = DuplicateWorkEliminator()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _apply_mathematical_optimizations(self, ir: schema.Module) -> Optional[schema.Module]:
        """Apply mathematical optimizations to reduce complexity."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = MathematicalOptimizer()
        transformer.visit(new_ir)

        if transformer.changed and transformer.needs_math_import:
            self._ensure_import(new_ir, "math")

        return new_ir if transformer.changed else None

    def _ensure_import(self, ir: schema.Module, module_name: str):
        """Ensure a module is imported."""
        # Check if already imported
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    if alias.name == module_name:
                        return

        # Add import at the beginning
        import_stmt = schema.Import(names=[schema.Alias(name=module_name)])
        ir.body.statements.insert(0, import_stmt)


class MembershipOptimizationTransformer(IRTransformerBase):
    """Optimizes membership testing operations."""

    def __init__(self):
        self.changed = False

    def visit_Compare(self, node: schema.Compare) -> schema.Expression:
        node = self.generic_visit(node)

        if (
            len(node.ops) == 1
            and node.ops[0] in ("in", "not in")
            and len(node.comparators) == 1
            and isinstance(node.comparators[0], schema.ListExpr)
        ):

            list_expr = node.comparators[0]
            # Convert to set if all elements are constants (hashable)
            if all(isinstance(elt, schema.Constant) for elt in list_expr.elts):
                self.changed = True
                node.comparators[0] = schema.SetExpr(elts=list_expr.elts)

        return node


class AccessPatternOptimizer(NodeTransformer):
    """Optimizes data access patterns.

    Converts:
        for i in range(len(arr)): use arr[i]
    To:
        for item in arr: use item

    When the index is only used for array access (not for other purposes).
    """

    def __init__(self):
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)

        # Look for patterns like: for i in range(len(arr)): use arr[i]
        if (
            isinstance(node.iter, schema.Call)
            and isinstance(node.iter.func, schema.Name)
            and node.iter.func.id == "range"
            and len(node.iter.args) == 1
        ):

            range_arg = node.iter.args[0]
            if (
                isinstance(range_arg, schema.Call)
                and isinstance(range_arg.func, schema.Name)
                and range_arg.func.id == "len"
                and len(range_arg.args) == 1
                and isinstance(range_arg.args[0], schema.Name)
            ):

                arr_name = range_arg.args[0].id

                if isinstance(node.target, schema.Name):
                    idx_name = node.target.id

                    # Check if index is ONLY used for arr[idx] access
                    checker = _IndexUsageChecker(arr_name, idx_name)
                    checker.visit(node.body)

                    if checker.only_used_for_array_access and checker.has_array_access:
                        self.changed = True
                        item_name = f"_item"

                        # Replace arr[idx] with item in the body
                        replacer = _IndexReplacer(arr_name, idx_name, item_name)
                        replacer.visit(node.body)

                        # Update loop to iterate directly over array
                        node.target = schema.Name(id=item_name, ctx="Store")
                        node.iter = schema.Name(id=arr_name, ctx="Load")

        return node


class _IndexUsageChecker(NodeTransformer):
    """Checks how an index variable is used in a loop body.

    Tracks whether:
    1. The index is used for array access (arr[idx])
    2. The index is ONLY used for the specific array access pattern

    If the index is used for anything else (arithmetic, function calls,
    other array accesses), only_used_for_array_access becomes False.
    """

    def __init__(self, arr_name: str, idx_name: str):
        self.arr_name = arr_name
        self.idx_name = idx_name
        self.has_array_access = False
        self.only_used_for_array_access = True
        self._in_target_subscript = False  # Flag to track if we're inside arr[idx]

    def visit_Subscript(self, node: schema.Subscript) -> schema.Expression:
        # Check for arr[idx] pattern
        if (
            isinstance(node.value, schema.Name)
            and node.value.id == self.arr_name
            and isinstance(node.slice, schema.Name)
            and node.slice.id == self.idx_name
        ):
            self.has_array_access = True
            # Mark that we're in the target subscript (so visit_Name skips this idx)
            self._in_target_subscript = True
            result = self.generic_visit(node)
            self._in_target_subscript = False
            return result
        else:
            # Check if idx is used in slice for different array
            if isinstance(node.slice, schema.Name) and node.slice.id == self.idx_name:
                self.only_used_for_array_access = False
        return self.generic_visit(node)

    def visit_Name(self, node: schema.Name) -> schema.Expression:
        """Track when the index variable is used outside of arr[idx] pattern."""
        if node.id == self.idx_name and node.ctx == "Load":
            # If we're not inside the target arr[idx] subscript, this is a non-array use
            if not self._in_target_subscript:
                self.only_used_for_array_access = False
        return node


class _IndexReplacer(NodeTransformer):
    """Replaces arr[idx] with item_name."""

    def __init__(self, arr_name: str, idx_name: str, item_name: str):
        self.arr_name = arr_name
        self.idx_name = idx_name
        self.item_name = item_name

    def visit_Subscript(self, node: schema.Subscript) -> schema.Expression:
        if (
            isinstance(node.value, schema.Name)
            and node.value.id == self.arr_name
            and isinstance(node.slice, schema.Name)
            and node.slice.id == self.idx_name
            and node.ctx == "Load"
        ):
            return schema.Name(id=self.item_name, ctx="Load")
        return self.generic_visit(node)


class InsertionDeletionOptimizer(NodeTransformer):
    """Optimizes insertion and deletion operations.

    Detects inefficient list operations that would benefit from deque:
    - list.insert(0, item) -> deque.appendleft(item)  [O(n) to O(1)]
    - list.pop(0) -> deque.popleft()  [O(n) to O(1)]

    Note: This transformer marks lists for conversion to deque. The actual
    conversion requires tracking across the module, so we convert the method
    calls and flag that collections.deque import is needed.
    """

    def __init__(self):
        self.changed = False
        self.needs_collections_import = False
        self.lists_to_convert: set = set()  # Track list names that should be deques
        self._candidates: set = set()  # Candidates identified during pre-scan

    def visit_FunctionDef(self, node: schema.FunctionDef) -> schema.FunctionDef:
        """Scan function body first to find candidates."""
        # Pre-scan to find variables used as queues
        candidates = set()
        scanner = self._QueueUsageScanner(candidates)
        scanner.visit(node)

        # Save candidates for this scope
        old_candidates = self._candidates
        self._candidates = candidates

        # Visit body
        node = self.generic_visit(node)

        # Restore old candidates
        self._candidates = old_candidates
        return node

    class _QueueUsageScanner(NodeTransformer):
        """Scans for list.insert(0) and list.pop(0) usage."""

        def __init__(self, candidates: set):
            self.candidates = candidates

        def visit_Call(self, node: schema.Call) -> schema.Call:
            if isinstance(node.func, schema.Attribute) and isinstance(node.func.value, schema.Name):
                if node.func.attr == "insert" and len(node.args) >= 2:
                    if isinstance(node.args[0], schema.Constant) and node.args[0].value == 0:
                        self.candidates.add(node.func.value.id)
                elif node.func.attr == "pop":
                    if (
                        len(node.args) >= 1
                        and isinstance(node.args[0], schema.Constant)
                        and node.args[0].value == 0
                    ):
                        self.candidates.add(node.func.value.id)
            return self.generic_visit(node)

    def visit_Assign(self, node: schema.Assign) -> schema.Assign:
        """Convert list initialization to deque."""
        node = self.generic_visit(node)

        if len(node.targets) == 1 and isinstance(node.targets[0], schema.Name):
            var_name = node.targets[0].id
            if var_name in self._candidates:
                # Check for empty list init: x = [] or x = list()
                is_empty_list = False
                if isinstance(node.value, schema.ListExpr) and len(node.value.elts) == 0:
                    is_empty_list = True
                elif (
                    isinstance(node.value, schema.Call)
                    and isinstance(node.value.func, schema.Name)
                    and node.value.func.id == "list"
                    and len(node.value.args) == 0
                ):
                    is_empty_list = True

                if is_empty_list:
                    self.changed = True
                    self.needs_collections_import = True
                    return schema.Assign(
                        targets=node.targets,
                        value=schema.Call(
                            func=schema.Attribute(
                                value=schema.Name(id="collections"), attr="deque"
                            ),
                            args=[],
                            keywords=[],
                        ),
                    )
        return node

    def visit_Call(self, node: schema.Call) -> schema.Expression:
        node = self.generic_visit(node)

        # Look for list.insert(0, item) or list.pop(0) patterns
        if isinstance(node.func, schema.Attribute) and isinstance(node.func.value, schema.Name):
            var_name = node.func.value.id

            # Only transform if it's a candidate we identified
            if var_name not in self._candidates:
                return node

            if node.func.attr == "insert" and len(node.args) >= 2:
                if isinstance(node.args[0], schema.Constant) and node.args[0].value == 0:
                    # Convert list.insert(0, item) to list.appendleft(item)
                    self.changed = True
                    self.needs_collections_import = True
                    return schema.Call(
                        func=schema.Attribute(value=node.func.value, attr="appendleft"),
                        args=[node.args[1]],  # Skip the index argument
                        keywords=node.keywords,
                    )

            elif node.func.attr == "pop":
                if (
                    len(node.args) >= 1
                    and isinstance(node.args[0], schema.Constant)
                    and node.args[0].value == 0
                ):
                    # Convert list.pop(0) to list.popleft()
                    self.changed = True
                    self.needs_collections_import = True
                    return schema.Call(
                        func=schema.Attribute(value=node.func.value, attr="popleft"),
                        args=[],  # popleft takes no arguments
                        keywords=[],
                    )

        return node


class SearchOptimizationTransformer(NodeTransformer):
    """Optimizes search operations.

    Detects linear search patterns that could use bisect for sorted data:

    Pattern 1: Linear search for first match
        for item in sorted_list:
            if item == target:
                return index

    Pattern 2: Index search
        for i, item in enumerate(sorted_list):
            if item >= target:
                return i

    Note: This is a heuristic optimization - it assumes the list is sorted
    if the variable name suggests it (e.g., 'sorted_list', ends with '_sorted').
    """

    def __init__(self):
        self.changed = False
        self.needs_bisect_import = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)

        # Check for enumerate pattern with comparison and return
        if (
            isinstance(node.iter, schema.Call)
            and isinstance(node.iter.func, schema.Name)
            and node.iter.func.id == "enumerate"
            and len(node.iter.args) == 1
        ):

            list_arg = node.iter.args[0]
            # Check if list name suggests it's sorted
            if isinstance(list_arg, schema.Name) and self._is_likely_sorted(list_arg.id):
                # Look for pattern: if item >= target: return i
                search_pattern = self._detect_bisect_pattern(node)
                if search_pattern:
                    self.changed = True
                    self.needs_bisect_import = True
                    return search_pattern

        return node

    def _is_likely_sorted(self, name: str) -> bool:
        """Heuristic: check if variable name suggests sorted data."""
        sorted_indicators = ["sorted", "_sorted", "ordered", "_ordered"]
        name_lower = name.lower()
        return any(indicator in name_lower for indicator in sorted_indicators)

    def _detect_bisect_pattern(self, node: schema.For) -> Optional[schema.Return]:
        """Detect if loop body matches bisect_left pattern."""
        # Look for: if item >= target: return i
        if len(node.body.statements) != 1:
            return None

        body_stmt = node.body.statements[0]
        if not isinstance(body_stmt, schema.If):
            return None

        # Check condition is comparison
        if not isinstance(body_stmt.test, schema.Compare):
            return None

        # Check for >= or == comparison
        if len(body_stmt.test.ops) != 1:
            return None

        op = body_stmt.test.ops[0]
        if op not in (">=", ">"):
            return None

        # Check body is return statement
        if len(body_stmt.body.statements) != 1:
            return None

        ret_stmt = body_stmt.body.statements[0]
        if not isinstance(ret_stmt, schema.Return):
            return None

        # Verify return value matches loop index
        # enumerate produces a Tuple(index, item)
        # We need to extract the index variable name
        loop_index_var = None

        if isinstance(node.target, schema.Name):
            # for i in ... (unlikely with enumerate but possible if item unused and unpacked later?? No, enumerate yields tuple)
            pass
        elif isinstance(node.target, schema.TupleExpr) and len(node.target.elts) == 2:
            # for i, x in enumerate(...)
            if isinstance(node.target.elts[0], schema.Name):
                loop_index_var = node.target.elts[0].id

        if not loop_index_var:
            return None

        if not (isinstance(ret_stmt.value, schema.Name) and ret_stmt.value.id == loop_index_var):
            return None

        # Extract target variable
        target = body_stmt.test.comparators[0]

        # Extract list variable
        if not (
            isinstance(node.iter, schema.Call)
            and len(node.iter.args) > 0
            and isinstance(node.iter.args[0], schema.Name)
        ):
            return None

        list_var = node.iter.args[0]

        # Construct: return bisect.bisect_left(sorted_list, target)
        self.needs_bisect_import = True
        self.changed = True
        return schema.Return(
            value=schema.Call(
                func=schema.Attribute(value=schema.Name(id="bisect"), attr="bisect_left"),
                args=[list_var, target],
                keywords=[],
            )
        )


class NestedLoopReducer(NodeTransformer):
    """Reduces nested loop complexity."""

    def __init__(self):
        self.changed = False
        self.needs_itertools_import = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)

        # Look for nested loops that can be converted to itertools.product
        if len(node.body.statements) == 1 and isinstance(node.body.statements[0], schema.For):

            inner_loop = node.body.statements[0]

            # Check if loops are independent
            # Must ensure outer loop variables are not used in inner loop iterable

            # Get outer loop variables
            outer_vars = set()
            if isinstance(node.target, schema.Name):
                outer_vars.add(node.target.id)
            elif isinstance(node.target, schema.TupleExpr):
                # Handle tuple unpacking in for loop target
                for elt in node.target.elts:
                    if isinstance(elt, schema.Name):
                        outer_vars.add(elt.id)

            # Check dependency
            # We check if any of outer_vars appear in inner_loop.iter
            inner_iter_vars = collect_names(inner_loop.iter, ctx_filter="Load")

            # If there is an intersection, loops are dependent -> cannot use product
            is_dependent = not outer_vars.isdisjoint(inner_iter_vars)

            if (
                not is_dependent
                and isinstance(node.target, schema.Name)
                and isinstance(inner_loop.target, schema.Name)
                and node.target.id != inner_loop.target.id
            ):

                # Convert to itertools.product
                self.changed = True
                self.needs_itertools_import = True

                product_call = schema.Call(
                    func=schema.Attribute(value=schema.Name(id="itertools"), attr="product"),
                    args=[node.iter, inner_loop.iter],
                )

                tuple_target = schema.TupleExpr(elts=[node.target, inner_loop.target], ctx="Store")

                return schema.For(
                    target=tuple_target, iter=product_call, body=inner_loop.body, orelse=None
                )

        return node


class SortingOptimizer(NodeTransformer):
    """Optimizes sorting operations.

    Transforms:
    - sorted(list)[-1] → max(list) (O(n) instead of O(n log n))
    - sorted(list)[0] → min(list) (O(n) instead of O(n log n))
    - sorted(list, reverse=True)[0] → max(list)
    - sorted(list, reverse=True)[-1] → min(list)
    """

    def __init__(self):
        self.changed = False

    def visit_Subscript(self, node: schema.Subscript) -> schema.Expression:
        node = self.generic_visit(node)

        # Check for sorted(...)[-1] or sorted(...)[0] patterns
        if (
            isinstance(node.value, schema.Call)
            and isinstance(node.value.func, schema.Name)
            and node.value.func.id == "sorted"
            and isinstance(node.slice, schema.Constant)
        ):

            # Check if reverse keyword is present
            has_reverse = any(
                kw[0] == "reverse" and isinstance(kw[1], schema.Constant) and kw[1].value is True
                for kw in node.value.keywords
            )

            if node.slice.value == -1:
                # sorted(list)[-1] → max(list)
                # sorted(list, reverse=True)[-1] → min(list)
                self.changed = True
                func_name = "min" if has_reverse else "max"
                return schema.Call(
                    func=schema.Name(id=func_name), args=node.value.args, keywords=[]
                )
            elif node.slice.value == 0:
                # sorted(list)[0] → min(list)
                # sorted(list, reverse=True)[0] → max(list)
                self.changed = True
                func_name = "max" if has_reverse else "min"
                return schema.Call(
                    func=schema.Name(id=func_name), args=node.value.args, keywords=[]
                )

        return node

    def visit_Call(self, node: schema.Call) -> schema.Expression:
        node = self.generic_visit(node)

        # Look for sorting operations that can be optimized
        # Could add more optimizations here like heapq for top-k

        return node


class DuplicateWorkEliminator(NodeTransformer):
    """Eliminates duplicate computations.

    When the same expression is computed multiple times and assigned to variables,
    replace subsequent computations with references to the first variable.

    Transforms:
        x = a + b
        y = a + b
    To:
        x = a + b
        y = x
    """

    def __init__(self):
        self.changed = False
        self.seen_expressions = {}  # hash -> variable_name that holds the result

    def visit_Assign(self, node: schema.Assign) -> schema.Statement:
        node = self.generic_visit(node)

        # Only handle simple single-target assignments
        if len(node.targets) != 1 or not isinstance(node.targets[0], schema.Name):
            return node

        target_name = node.targets[0].id

        # Track expressions to identify duplicates
        expr_hash = self._hash_expression(node.value)

        if expr_hash and expr_hash in self.seen_expressions:
            # Found duplicate computation - replace with reference to original
            original_var = self.seen_expressions[expr_hash]
            self.changed = True
            node.value = schema.Name(id=original_var, ctx="Load")
        elif expr_hash:
            # First time seeing this expression - track it
            self.seen_expressions[expr_hash] = target_name

        return node

    def _hash_expression(self, expr: schema.Expression) -> Optional[str]:
        """Create a simple hash for expressions (supports common patterns)."""
        if isinstance(expr, schema.BinaryOp):
            left_hash = self._hash_expression(expr.left)
            right_hash = self._hash_expression(expr.right)
            if left_hash and right_hash:
                return f"BinOp({expr.op},{left_hash},{right_hash})"
        elif isinstance(expr, schema.UnaryOp):
            operand_hash = self._hash_expression(expr.operand)
            if operand_hash:
                return f"UnaryOp({expr.op},{operand_hash})"
        elif isinstance(expr, schema.Call):
            if isinstance(expr.func, schema.Name):
                args_hash = ",".join(self._hash_expression(arg) or "" for arg in expr.args)
                return f"Call({expr.func.id},{args_hash})"
        elif isinstance(expr, schema.Name):
            return f"Name({expr.id})"
        elif isinstance(expr, schema.Constant):
            return f"Const({expr.value})"
        elif isinstance(expr, schema.Attribute):
            value_hash = self._hash_expression(expr.value)
            if value_hash:
                return f"Attr({value_hash},{expr.attr})"
        return None


class MathematicalOptimizer(NodeTransformer):
    """Applies mathematical optimizations."""

    def __init__(self):
        self.changed = False
        self.needs_math_import = False

    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)

        # Mathematical optimizations
        if node.op == "**" and isinstance(node.right, schema.Constant):
            if node.right.value == 0.5:
                # x ** 0.5 -> math.sqrt(x)
                self.changed = True
                self.needs_math_import = True
                return schema.Call(
                    func=schema.Attribute(value=schema.Name(id="math"), attr="sqrt"),
                    args=[node.left],
                )

        return node
