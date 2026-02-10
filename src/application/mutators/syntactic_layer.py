"""
Syntactic Layer Mutators - Code Patterns and Idiom Improvements

These mutators focus on:
- Python idiom optimization
- Code pattern improvements
- Syntactic sugar utilization
- Readability and maintainability enhancements
"""

import logging
from typing import List, Optional, Set

from src.application.mutators.base import (LayeredMutator, MutationLayer,
                                           MutationResult, safe_deepcopy_ir)
from src.application.mutators.semantic_base import LLMMutatorBase
from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer
from src.utils.mutation_factory import create_mutation_result

logger = logging.getLogger(__name__)


class PythonicIdiomOptimizer(LayeredMutator):
    """
    Optimizes code to use Pythonic idioms and patterns.

    Focuses on converting verbose or non-Pythonic code into
    idiomatic Python that is both more readable and efficient.
    """

    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.SYNTACTIC, enabled_strategies)

    def get_available_strategies(self) -> List[str]:
        return [
            "Idiom_ComprehensionOptimization",
            "Idiom_BuiltinUtilization",
            "Idiom_IteratorOptimization",
            "Idiom_ContextManagerUsage",
        ]

    def mutate(self, ir: schema.Module) -> List[MutationResult]:
        """Apply Pythonic idiom optimization mutations."""
        results = []

        # Strategy 1: List/Dict/Set Comprehensions
        if self._is_strategy_enabled("Idiom_ComprehensionOptimization"):
            variant = self._optimize_comprehensions(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Idiom_ComprehensionOptimization",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.9,
                        description="Converted loops to comprehensions for better performance and readability",
                    )
                )

        # Strategy 2: Built-in Function Utilization
        if self._is_strategy_enabled("Idiom_BuiltinUtilization"):
            variant = self._utilize_builtins(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Idiom_BuiltinUtilization",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.85,
                        description="Replaced manual implementations with efficient built-in functions",
                    )
                )

        # Strategy 3: Iterator and Generator Optimization
        if self._is_strategy_enabled("Idiom_IteratorOptimization"):
            variant = self._optimize_iterators(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Idiom_IteratorOptimization",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.8,
                        description="Optimized iteration patterns using generators and iterators",
                    )
                )

        # Strategy 4: Context Manager Usage
        if self._is_strategy_enabled("Idiom_ContextManagerUsage"):
            variant = self._optimize_context_managers(ir)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Idiom_ContextManagerUsage",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.75,
                        description="Improved resource management using context managers",
                    )
                )

        return results

    def _optimize_comprehensions(self, ir: schema.Module) -> Optional[schema.Module]:
        """Convert loops to comprehensions where appropriate."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = ComprehensionOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _utilize_builtins(self, ir: schema.Module) -> Optional[schema.Module]:
        """Replace manual implementations with built-in functions."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = BuiltinUtilizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _optimize_iterators(self, ir: schema.Module) -> Optional[schema.Module]:
        """Optimize iteration patterns using generators and iterators."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = IteratorOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _optimize_context_managers(self, ir: schema.Module) -> Optional[schema.Module]:
        """Improve resource management using context managers."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = ContextManagerOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None


class CodePatternOptimizer(LayeredMutator, LLMMutatorBase):
    """
    Optimizes common code patterns using LLM-based analysis.

    Identifies and improves common coding patterns that can be
    made more efficient or readable through syntactic changes.
    """

    def __init__(
        self,
        llm_client,
        enabled_strategies: Optional[Set[str]] = None,
        allowed_imports: Optional[Set[str]] = None,
    ):
        LayeredMutator.__init__(self, MutationLayer.SYNTACTIC, enabled_strategies)
        LLMMutatorBase.__init__(self, llm_client, allowed_imports=allowed_imports)

    def get_available_strategies(self) -> List[str]:
        return [
            "Pattern_LoopOptimization",
            "Pattern_ConditionalSimplification",
            "Pattern_FunctionComposition",
            "Pattern_ErrorHandling",
        ]

    def mutate(self, ir: schema.Module) -> List[MutationResult]:
        """Apply code pattern optimization mutations."""
        results = []
        code = self.codegen.generate(ir)
        allowed_imports = self._get_imports(ir)

        # Strategy 1: Loop Pattern Optimization
        if self._is_strategy_enabled("Pattern_LoopOptimization"):
            variant = self._optimize_loop_patterns(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Pattern_LoopOptimization",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.8,
                        description="Optimized loop patterns for better performance and readability",
                    )
                )

        # Strategy 2: Conditional Simplification
        if self._is_strategy_enabled("Pattern_ConditionalSimplification"):
            variant = self._simplify_conditionals(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Pattern_ConditionalSimplification",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.85,
                        description="Simplified conditional logic and boolean expressions",
                    )
                )

        # Strategy 3: Function Composition
        if self._is_strategy_enabled("Pattern_FunctionComposition"):
            variant = self._optimize_function_composition(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Pattern_FunctionComposition",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.7,
                        description="Improved function composition and call patterns",
                    )
                )

        # Strategy 4: Error Handling Patterns
        if self._is_strategy_enabled("Pattern_ErrorHandling"):
            variant = self._optimize_error_handling(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="Pattern_ErrorHandling",
                        layer=MutationLayer.SYNTACTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.75,
                        description="Improved error handling patterns and exception management",
                    )
                )

        return results

    def _optimize_loop_patterns(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Optimize loop patterns for better performance."""
        prompt = f"""You are an expert in Python loop optimization, performance engineering, and iteration patterns.

Optimize the loop patterns in this code for maximum performance, memory efficiency, and readability:

LOOP PATTERN ANALYSIS:
1. IDENTIFY inefficient iteration patterns and manual indexing
2. RECOGNIZE opportunities for Pythonic constructs
3. ANALYZE memory usage patterns and potential optimizations
4. EVALUATE loop body complexity and optimization opportunities
5. CONSIDER data access patterns and cache locality

PERFORMANCE OPTIMIZATIONS:
- ENUMERATE REPLACEMENT: Convert manual index loops to enumerate() for clarity and performance
- PARALLEL ITERATION: Use zip() instead of manual indexing for multiple sequences
- DIRECT ITERATION: Replace range(len()) patterns with direct iteration over collections
- COMPREHENSIONS: Convert explicit loops to list/set/dict comprehensions for speed
- GENERATOR EXPRESSIONS: Use generators for memory efficiency in large datasets
- BUILT-IN FUNCTIONS: Leverage any()/all()/sum() instead of manual accumulation
- ITERTOOLS UTILITIES: Use product(), combinations(), permutations() for complex iterations

ADVANCED LOOP TECHNIQUES:
- LOOP INVARIANT CODE MOTION: Move computations out of loops where possible
- EARLY TERMINATION: Apply break/continue strategically to avoid unnecessary iterations
- LOCAL VARIABLE CACHING: Cache attribute lookups and method calls in hot loops
- CHUNKING: Process data in batches for better memory usage patterns
- LAZY EVALUATION: Use generators to defer computation until needed

MEMORY AND CACHE OPTIMIZATIONS:
- Minimize memory allocations in loops
- Optimize data access patterns for CPU cache efficiency
- Reduce object creation in hot loops
- Use appropriate data structures for iteration patterns

Available imports: {allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Loop optimizations must provide measurable performance improvement
- Preserve all existing functionality and edge case handling
- Maintain identical output format and behavior
- Do not change the public interface or external behavior
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _simplify_conditionals(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Simplify conditional logic and boolean expressions."""
        prompt = f"""You are an expert in boolean logic optimization, conditional analysis, and performance engineering.

Simplify the conditional logic in this code for maximum performance, readability, and maintainability:

CONDITIONAL ANALYSIS FRAMEWORK:
1. IDENTIFY redundant conditions and impossible branches
2. BOOLEAN ALGEBRA OPTIMIZATION: Apply logical equivalences for simplification
3. TRUTHINESS OPTIMIZATION: Leverage Python's truthiness for cleaner code
4. SHORT-CIRCUIT OPTIMIZATION: Order conditions for maximum efficiency
5. NESTING REDUCTION: Minimize conditional depth and complexity

BOOLEAN LOGIC OPTIMIZATIONS:
- DE MORGAN'S LAWS: Transform complex negations for better performance
  - not (a and b) → (not a) or (not b)
  - not (a or b) → (not a) and (not b)
- CONDITION MERGING: Combine related conditions to reduce evaluation overhead
- REDUNDANT ELIMINATION: Remove impossible conditions and tautologies
- TRUTHINESS SIMPLIFICATION:
  - if x == True: → if x:
  - if x == False: → if not x:
  - if len(x) > 0: → if x:
  - if x is not None: → if x: (when appropriate)

PERFORMANCE OPTIMIZATIONS:
- CONDITION REORDERING: Place most likely/least expensive conditions first
- EARLY RETURN PATTERNS: Use early returns to reduce nesting
- TERNARY OPERATORS: Use conditional expressions for simple assignments
- MEMOIZATION: Cache expensive boolean computations
- BRANCH PREDICTION: Structure conditions for CPU optimization

CODE STRUCTURE IMPROVEMENTS:
- Reduce cyclomatic complexity for better maintainability
- Improve readability through clearer conditional structure
- Maintain consistent error handling patterns
- Preserve debugging and testing capabilities

Available imports: {allowed_imports}

Code to simplify:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Conditional simplification must provide measurable performance or readability improvement
- Preserve all existing functionality, edge cases, and error handling
- Maintain identical logical behavior for all possible inputs
- Do not change the public interface or external behavior
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _optimize_function_composition(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Optimize function composition and call patterns."""
        prompt = f"""You are an expert in function optimization, call pattern analysis, and performance engineering.

Optimize function composition and calling patterns in this code for maximum performance and efficiency:

FUNCTION CALL ANALYSIS:
1. IDENTIFY redundant function calls and unnecessary intermediate steps
2. CALL PATTERN OPTIMIZATION: Analyze call frequency and overhead
3. COMPOSITION OPPORTUNITIES: Combine related function operations
4. RECURSION ANALYSIS: Optimize recursive patterns where beneficial
5. CACHING STRATEGIES: Identify memoization opportunities

FUNCTION OPTIMIZATION TECHNIQUES:
- FUNCTION COMPOSITION: Chain operations to reduce intermediate variables
- PARTIAL APPLICATION: Use functools.partial for specialized function variants
- LAMBDA OPTIMIZATION: Replace small functions with lambda expressions where appropriate
- CLOSURE OPTIMIZATION: Minimize closure variable capture overhead
- TAIL RECURSION: Convert recursive calls to iterative where beneficial
- INLINE OPTIMIZATION: Consider inlining small, hot functions

CALL PATTERN OPTIMIZATIONS:
- METHOD CHAINING: Combine multiple method calls for efficiency
- ARGUMENT OPTIMIZATION: Optimize parameter passing and unpacking
- DECORATOR PATTERNS: Apply cross-cutting concerns efficiently
- BATCHING: Group multiple operations into single calls
- LAZY EVALUATION: Defer function calls until actually needed

FUNCTIONAL PROGRAMMING OPTIMIZATIONS:
- MAP/FILTER/REDUCE: Use built-in functional primitives for performance
- GENERATOR FUNCTIONS: Use generators for memory-efficient processing
- ITERATOR PROTOCOLS: Optimize custom iterator implementations
- HIGHER-ORDER FUNCTIONS: Optimize functions that accept/return functions

PERFORMANCE CONSIDERATIONS:
- Minimize function call overhead in hot paths and critical sections
- Optimize for CPU cache locality in function call patterns
- Consider stack usage and recursion depth
- Balance between readability and performance optimizations

Available imports: {allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Function optimizations must provide measurable performance improvement
- Preserve all existing functionality and error handling
- Maintain identical input/output behavior and side effects
- Do not change the public interface or external behavior
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _optimize_error_handling(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Optimize error handling patterns."""
        prompt = f"""You are an expert in Python error handling optimization, exception management, and performance engineering.

Optimize error handling patterns in this code for maximum performance, reliability, and maintainability:

ERROR HANDLING ANALYSIS:
1. IDENTIFY inefficient error handling patterns and excessive checking
2. EAFP vs LBYL ANALYSIS: Choose the optimal pattern for each situation
3. EXCEPTION PERFORMANCE: Analyze the cost of exception handling vs prevention
4. RESOURCE MANAGEMENT: Optimize cleanup and resource release patterns
5. ERROR RECOVERY: Improve error handling robustness and recovery strategies

PERFORMANCE OPTIMIZATIONS:
- EAFP PATTERNS: Replace explicit checks with try/except where more efficient
  - if key in dict: value = dict[key] → try: value = dict[key] except KeyError:
  - if hasattr(obj, 'attr'): value = obj.attr → try: value = obj.attr except AttributeError:
- SPECIFIC EXCEPTIONS: Use precise exception types instead of broad catches
- EXCEPTION CHAINING: Properly chain exceptions for better debugging
- CONTEXT MANAGERS: Use with statements for automatic resource cleanup
- ELSE CLAUSES: Use try/except/else for no-exception success paths

ERROR HANDLING PATTERNS:
- GRACEFUL DEGRADATION: Handle errors without breaking program flow
- FAIL-FAST PRINCIPLE: Detect and report errors early and clearly
- DEFENSIVE PROGRAMMING: Validate inputs and handle edge cases
- RECOVERY STRATEGIES: Implement appropriate error recovery mechanisms
- LOGGING INTEGRATION: Optimize error reporting and logging patterns

ADVANCED TECHNIQUES:
- EXCEPTION CACHING: Cache exception objects for reuse in hot paths
- CUSTOM EXCEPTIONS: Create specific exception types for better error handling
- ERROR AGGREGATION: Collect multiple errors before reporting
- ASYNCHRONOUS ERROR HANDLING: Optimize error handling in async contexts
- PERFORMANCE MONITORING: Track error handling performance impact

CODE QUALITY IMPROVEMENTS:
- Maintain clear error messages and debugging information
- Ensure consistent error handling patterns across the codebase
- Preserve stack traces and exception context
- Balance between performance optimization and error handling robustness

Available imports: {allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Error handling optimizations must provide measurable performance improvement
- Preserve all existing functionality and error handling behavior
- Maintain identical exception types and error messages
- Do not compromise error handling robustness for performance
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)


# Transformer implementations for syntactic optimizations
class ComprehensionOptimizer(NodeTransformer):
    """
    Converts loops to comprehensions where appropriate.

    Detects patterns like:
        result = []
        for x in iter:
            result.append(expr)

    And transforms to:
        result = [expr for x in iter]
    """

    def __init__(self):
        self.changed = False
        # list_name -> (assign_stmt, block, index)
        self._pending_list_inits = {}

    def visit_Block(self, node: schema.Block) -> schema.Block:
        """Process blocks to find list init + append loop patterns."""
        new_statements = []
        skip_next = False

        i = 0
        while i < len(node.statements):
            if skip_next:
                skip_next = False
                i += 1
                continue

            stmt = node.statements[i]

            # Check for pattern: result = []
            list_name = self._get_empty_list_init(stmt)

            if list_name and i + 1 < len(node.statements):
                next_stmt = node.statements[i + 1]

                # Check if next statement is a for-loop with append to list_name
                comprehension = self._try_convert_loop_to_comprehension(next_stmt, list_name)

                if comprehension:
                    # Replace both statements with comprehension assignment
                    new_assign = schema.Assign(
                        targets=[schema.Name(id=list_name, ctx="Store")], value=comprehension
                    )
                    new_statements.append(new_assign)
                    skip_next = True  # Skip the for-loop
                    self.changed = True
                    i += 1
                    continue

            # Recursively visit the statement
            new_statements.append(self.visit(stmt))
            i += 1

        node.statements = new_statements
        return node

    def _get_empty_list_init(self, stmt: schema.Statement) -> Optional[str]:
        """Check if statement is `name = []` and return the name."""
        if isinstance(stmt, schema.Assign):
            if (
                len(stmt.targets) == 1
                and isinstance(stmt.targets[0], schema.Name)
                and isinstance(stmt.value, schema.ListExpr)
                and len(stmt.value.elts) == 0
            ):
                return stmt.targets[0].id
        return None

    def _try_convert_loop_to_comprehension(
        self, stmt: schema.Statement, list_name: str
    ) -> Optional[schema.ListComp]:
        """Try to convert a for-loop with append to list comprehension."""
        if not isinstance(stmt, schema.For):
            return None

        # Must have exactly one statement in body
        if len(stmt.body.statements) != 1:
            return None

        body_stmt = stmt.body.statements[0]
        ifs = []

        # Handle conditional appends: if cond: result.append(expr)
        if isinstance(body_stmt, schema.If):
            # Condition must not have else block
            if body_stmt.orelse and len(body_stmt.orelse.statements) > 0:
                return None

            # Condition body must have exactly one statement
            if len(body_stmt.body.statements) != 1:
                return None

            ifs.append(body_stmt.test)
            body_stmt = body_stmt.body.statements[0]

        if not isinstance(body_stmt, schema.ExprStmt):
            return None

        call = body_stmt.value
        if not isinstance(call, schema.Call):
            return None

        # Check for list_name.append(expr)
        if (
            isinstance(call.func, schema.Attribute)
            and isinstance(call.func.value, schema.Name)
            and call.func.value.id == list_name
            and call.func.attr == "append"
            and len(call.args) == 1
        ):

            return schema.ListComp(
                elt=call.args[0],
                generators=[schema.Comprehension(target=stmt.target, iter=stmt.iter, ifs=ifs)],
            )

        return None

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Handle nested for-loops and other patterns."""
        return self.generic_visit(node)


class BuiltinUtilizer(NodeTransformer):
    """
    Replaces manual implementations with built-in functions.

    Detects patterns like:
        total = 0
        for x in iter:
            total += x

    And transforms to:
        total = sum(iter)

    Also handles min/max patterns.
    """

    def __init__(self):
        self.changed = False

    def visit_Block(self, node: schema.Block) -> schema.Block:
        """Process blocks to find manual builtin patterns."""
        new_statements = []
        skip_next = False

        i = 0
        while i < len(node.statements):
            if skip_next:
                skip_next = False
                i += 1
                continue

            stmt = node.statements[i]

            # Check for sum pattern: total = 0
            sum_var = self._get_zero_init(stmt)

            if sum_var and i + 1 < len(node.statements):
                next_stmt = node.statements[i + 1]

                # Check for: for x in iter: total += x
                sum_call = self._try_convert_to_sum(next_stmt, sum_var)

                if sum_call:
                    # Replace both statements with sum() call
                    new_assign = schema.Assign(
                        targets=[schema.Name(id=sum_var, ctx="Store")], value=sum_call
                    )
                    new_statements.append(new_assign)
                    skip_next = True
                    self.changed = True
                    i += 1
                    continue

            # Check for min/max pattern: result = float('inf') or result = first_val
            minmax_info = self._get_minmax_init(stmt)

            if minmax_info and i + 1 < len(node.statements):
                next_stmt = node.statements[i + 1]
                var_name, is_min = minmax_info

                minmax_call = self._try_convert_to_minmax(next_stmt, var_name, is_min)

                if minmax_call:
                    new_assign = schema.Assign(
                        targets=[schema.Name(id=var_name, ctx="Store")], value=minmax_call
                    )
                    new_statements.append(new_assign)
                    skip_next = True
                    self.changed = True
                    i += 1
                    continue

            new_statements.append(self.visit(stmt))
            i += 1

        node.statements = new_statements
        return node

    def _get_zero_init(self, stmt: schema.Statement) -> Optional[str]:
        """Check if statement is `name = 0` and return the name."""
        if isinstance(stmt, schema.Assign):
            if (
                len(stmt.targets) == 1
                and isinstance(stmt.targets[0], schema.Name)
                and isinstance(stmt.value, schema.Constant)
                and stmt.value.value == 0
            ):
                return stmt.targets[0].id
        return None

    def _get_minmax_init(self, stmt: schema.Statement) -> Optional[tuple]:
        """Check for min/max initialization patterns."""
        if isinstance(stmt, schema.Assign):
            if len(stmt.targets) == 1 and isinstance(stmt.targets[0], schema.Name):
                var_name = stmt.targets[0].id
                value = stmt.value

                # float('inf') for min, float('-inf') or -float('inf') for max
                if isinstance(value, schema.Call):
                    if (
                        isinstance(value.func, schema.Name)
                        and value.func.id == "float"
                        and len(value.args) == 1
                        and isinstance(value.args[0], schema.Constant)
                    ):
                        if value.args[0].value == "inf":
                            return (var_name, True)  # is_min=True
                        elif value.args[0].value == "-inf":
                            return (var_name, False)  # is_min=False
        return None

    def _try_convert_to_sum(self, stmt: schema.Statement, sum_var: str) -> Optional[schema.Call]:
        """Try to convert a for-loop with += to sum() call."""
        if not isinstance(stmt, schema.For):
            return None

        # Must have exactly one statement: sum_var += loop_var
        if len(stmt.body.statements) != 1:
            return None

        body_stmt = stmt.body.statements[0]
        if not isinstance(body_stmt, schema.AugAssign):
            return None

        if body_stmt.op != "+":
            return None

        # Target must be sum_var
        if not isinstance(body_stmt.target, schema.Name):
            return None
        if body_stmt.target.id != sum_var:
            return None

        # Value being added must be the loop variable
        if not isinstance(body_stmt.value, schema.Name):
            return None
        if not isinstance(stmt.target, schema.Name):
            return None
        if body_stmt.value.id != stmt.target.id:
            return None

        # Create sum(iter) call
        return schema.Call(func=schema.Name(id="sum"), args=[stmt.iter], keywords=[])

    def _try_convert_to_minmax(
        self, stmt: schema.Statement, var_name: str, is_min: bool
    ) -> Optional[schema.Call]:
        """Try to convert a for-loop with comparison to min/max call.

        Detects patterns like:
            result = float('inf')  # or float('-inf') for max
            for x in iterable:
                if x < result:  # or x > result for max
                    result = x

        And converts to: result = min(iterable) or max(iterable)
        """
        if not isinstance(stmt, schema.For):
            return None

        # Look for: if x < var_name: var_name = x (for min)
        # or: if x > var_name: var_name = x (for max)
        if len(stmt.body.statements) != 1:
            return None

        body_stmt = stmt.body.statements[0]
        if not isinstance(body_stmt, schema.If):
            return None

        # Check the condition is a comparison
        if not isinstance(body_stmt.test, schema.Compare):
            return None

        compare = body_stmt.test

        # Must have exactly one comparison operator
        if len(compare.ops) != 1 or len(compare.comparators) != 1:
            return None

        op = compare.ops[0]

        # For min: looking for x < var_name or var_name > x
        # For max: looking for x > var_name or var_name < x
        left = compare.left
        right = compare.comparators[0]

        # Get the loop variable name
        if not isinstance(stmt.target, schema.Name):
            return None
        loop_var = stmt.target.id

        # Determine if pattern matches
        is_valid_pattern = False

        if is_min:
            # For min: loop_var < var_name
            if (
                op == "<"
                and isinstance(left, schema.Name)
                and left.id == loop_var
                and isinstance(right, schema.Name)
                and right.id == var_name
            ):
                is_valid_pattern = True
            # Also handle: var_name > loop_var
            elif (
                op == ">"
                and isinstance(left, schema.Name)
                and left.id == var_name
                and isinstance(right, schema.Name)
                and right.id == loop_var
            ):
                is_valid_pattern = True
        else:
            # For max: loop_var > var_name
            if (
                op == ">"
                and isinstance(left, schema.Name)
                and left.id == loop_var
                and isinstance(right, schema.Name)
                and right.id == var_name
            ):
                is_valid_pattern = True
            # Also handle: var_name < loop_var
            elif (
                op == "<"
                and isinstance(left, schema.Name)
                and left.id == var_name
                and isinstance(right, schema.Name)
                and right.id == loop_var
            ):
                is_valid_pattern = True

        if not is_valid_pattern:
            return None

        # Check the if body: var_name = loop_var
        if len(body_stmt.body.statements) != 1:
            return None

        assign_stmt = body_stmt.body.statements[0]
        if not isinstance(assign_stmt, schema.Assign):
            return None

        if len(assign_stmt.targets) != 1:
            return None

        target = assign_stmt.targets[0]
        if not isinstance(target, schema.Name) or target.id != var_name:
            return None

        if not isinstance(assign_stmt.value, schema.Name) or assign_stmt.value.id != loop_var:
            return None

        # Pattern matches! Create min/max call
        func_name = "min" if is_min else "max"
        return schema.Call(func=schema.Name(id=func_name), args=[stmt.iter], keywords=[])

    def visit_For(self, node: schema.For) -> schema.Statement:
        """Handle other for-loop patterns."""
        return self.generic_visit(node)


class IteratorOptimizer(NodeTransformer):
    """
    Optimizes iteration patterns.

    Detects patterns like:
        for i in range(len(arr)):
            ... arr[i] ...

    And transforms to:
        for i, _item in enumerate(arr):
            ... _item ...
    """

    def __init__(self):
        self.changed = False

    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)

        # Look for range(len(arr)) patterns
        if (
            isinstance(node.iter, schema.Call)
            and isinstance(node.iter.func, schema.Name)
            and node.iter.func.id == "range"
            and len(node.iter.args) == 1
            and isinstance(node.iter.args[0], schema.Call)
            and isinstance(node.iter.args[0].func, schema.Name)
            and node.iter.args[0].func.id == "len"
            and len(node.iter.args[0].args) == 1
        ):

            # Extract the array being iterated
            len_arg = node.iter.args[0].args[0]
            if isinstance(len_arg, schema.Name):
                arr_name = len_arg.id

                # Get the index variable name
                if isinstance(node.target, schema.Name):
                    idx_name = node.target.id

                    # Check if body uses arr[idx_name] pattern
                    if self._uses_indexed_access(node.body, arr_name, idx_name):
                        # Generate a unique item variable name
                        item_name = f"_item_{arr_name}"

                        # Replace arr[idx] with item in the body
                        replacer = IndexedAccessReplacer(arr_name, idx_name, item_name)
                        replacer.visit(node.body)

                        # Transform the loop header
                        node.iter = schema.Call(
                            func=schema.Name(id="enumerate"),
                            args=[schema.Name(id=arr_name)],
                            keywords=[],
                        )

                        node.target = schema.TupleExpr(
                            elts=[
                                schema.Name(id=idx_name, ctx="Store"),
                                schema.Name(id=item_name, ctx="Store"),
                            ],
                            ctx="Store",
                        )

                        self.changed = True

        return node

    def _uses_indexed_access(self, body: schema.Block, arr_name: str, idx_name: str) -> bool:
        """Check if body contains arr[idx] access pattern."""
        checker = IndexedAccessChecker(arr_name, idx_name)
        checker.visit(body)
        return checker.found


class IndexedAccessChecker(NodeTransformer):
    """Helper to check for arr[idx] patterns."""

    def __init__(self, arr_name: str, idx_name: str):
        self.arr_name = arr_name
        self.idx_name = idx_name
        self.found = False

    def visit_Subscript(self, node: schema.Subscript) -> schema.Expression:
        if (
            isinstance(node.value, schema.Name)
            and node.value.id == self.arr_name
            and isinstance(node.slice, schema.Name)
            and node.slice.id == self.idx_name
        ):
            self.found = True
        return self.generic_visit(node)


class IndexedAccessReplacer(NodeTransformer):
    """Replace arr[idx] with item_name."""

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


class ContextManagerOptimizer(NodeTransformer):
    """Optimizes resource management using context managers.

    Converts patterns like:
        f = open(...)
        try:
            ... use f ...
        finally:
            f.close()

    To:
        with open(...) as f:
            ... use f ...
    """

    def __init__(self):
        self.changed = False

    def visit_Block(self, node: schema.Block) -> schema.Block:
        """Process blocks to find resource init + try/finally patterns."""
        new_statements = []
        skip_next = False

        i = 0
        while i < len(node.statements):
            if skip_next:
                skip_next = False
                i += 1
                continue

            stmt = node.statements[i]

            # Check for pattern: resource = open(...) followed by try/finally with close()
            if isinstance(stmt, schema.Assign) and i + 1 < len(node.statements):
                resource_info = self._get_resource_assignment(stmt)
                if resource_info:
                    var_name, open_call = resource_info
                    next_stmt = node.statements[i + 1]

                    # Check if next statement is try/finally with close()
                    if isinstance(next_stmt, schema.Try):
                        with_stmt = self._try_convert_to_with(next_stmt, var_name, open_call)
                        if with_stmt:
                            new_statements.append(with_stmt)
                            skip_next = True
                            self.changed = True
                            i += 1
                            continue

            # Recursively visit the statement
            new_statements.append(self.visit(stmt))
            i += 1

        node.statements = new_statements
        return node

    def visit_Try(self, node: schema.Try) -> schema.Statement:
        """Also handle try/finally patterns where assignment is inside try."""
        node = self.generic_visit(node)

        # Check for: try: f = open(...); ... finally: f.close()
        if node.finalbody and len(node.finalbody.statements) >= 1:
            final_stmt = node.finalbody.statements[0]

            # Look for .close() call
            close_info = self._get_close_call(final_stmt)
            if close_info:
                resource_name = close_info

                # Look for open() assignment in try body
                for idx, body_stmt in enumerate(node.body.statements):
                    if isinstance(body_stmt, schema.Assign):
                        resource_info = self._get_resource_assignment(body_stmt)
                        if resource_info and resource_info[0] == resource_name:
                            _, open_call = resource_info

                            # Create with statement
                            remaining_body = schema.Block(
                                statements=node.body.statements[idx + 1 :]
                            )

                            self.changed = True
                            return schema.With(
                                items=[
                                    schema.WithItem(
                                        context_expr=open_call,
                                        optional_vars=schema.Name(id=resource_name, ctx="Store"),
                                    )
                                ],
                                body=remaining_body,
                            )

        return node

    def _get_resource_assignment(self, stmt: schema.Assign) -> Optional[tuple]:
        """Check if statement is resource = open(...) or similar."""
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], schema.Name):
            return None

        var_name = stmt.targets[0].id

        # Check for open() call
        if isinstance(stmt.value, schema.Call):
            if isinstance(stmt.value.func, schema.Name):
                if stmt.value.func.id in ("open", "file"):
                    return (var_name, stmt.value)
            elif isinstance(stmt.value.func, schema.Attribute):
                # Handle Path(...).open() etc.
                if stmt.value.func.attr == "open":
                    return (var_name, stmt.value)

        return None

    def _get_close_call(self, stmt: schema.Statement) -> Optional[str]:
        """Check for .close() call and return the resource name."""
        if isinstance(stmt, schema.ExprStmt) and isinstance(stmt.value, schema.Call):
            call = stmt.value
            if (
                isinstance(call.func, schema.Attribute)
                and call.func.attr == "close"
                and isinstance(call.func.value, schema.Name)
            ):
                return call.func.value.id
        return None

    def _try_convert_to_with(
        self, try_stmt: schema.Try, var_name: str, open_call: schema.Call
    ) -> Optional[schema.With]:
        """Try to convert a try/finally with close() to with statement."""
        if not try_stmt.finalbody:
            return None

        # Look for resource_name.close() in finally block
        for final_stmt in try_stmt.finalbody.statements:
            close_resource = self._get_close_call(final_stmt)
            if close_resource == var_name:
                # Found matching close() - create with statement
                return schema.With(
                    items=[
                        schema.WithItem(
                            context_expr=open_call,
                            optional_vars=schema.Name(id=var_name, ctx="Store"),
                        )
                    ],
                    body=try_stmt.body,
                )
