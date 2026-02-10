"""
Semantic Layer Mutators - Algorithm Intent and High-Level Logic

These mutators operate at the highest abstraction level, focusing on:
- Algorithm selection and optimization
- High-level program intent and logic flow
- Architectural patterns and design improvements
"""

import logging
from typing import List, Optional, Set

from src.application.mutators.base import MutationLayer, MutationResult
from src.application.mutators.ir_mutator_base import IROnlyMutator
from src.application.mutators.semantic_base import LLMMutatorBase
from src.domain.ir import schema
from src.utils.mutation_factory import create_mutation_result

logger = logging.getLogger(__name__)


class AlgorithmicIntentMutator(IROnlyMutator, LLMMutatorBase):
    """
    Focuses on high-level algorithmic improvements and intent optimization.

    This mutator understands the program's purpose and suggests algorithmic
    alternatives that maintain the same intent but with better characteristics.
    """

    def __init__(
        self,
        llm_client=None,
        enabled_strategies: Optional[Set[str]] = None,
        allowed_imports: Optional[Set[str]] = None,
    ):
        IROnlyMutator.__init__(self, MutationLayer.SEMANTIC, enabled_strategies)
        LLMMutatorBase.__init__(self, llm_client, allowed_imports=allowed_imports)

    def get_available_strategies(self) -> List[str]:
        return [
            "AlgorithmicIntent_ComplexityReduction",
            "AlgorithmicIntent_PatternRecognition",
            "AlgorithmicIntent_ArchitecturalImprovement",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply semantic-level algorithmic mutations."""
        results = []
        code = self.codegen.generate(ir)
        allowed_imports = self._get_imports(ir)

        # Strategy 1: Complexity Reduction
        if self._is_strategy_enabled("AlgorithmicIntent_ComplexityReduction"):
            variant = self._optimize_algorithmic_complexity(code, allowed_imports)
            if variant:
                result = create_mutation_result(
                    ir=variant,
                    strategy_name="AlgorithmicIntent_ComplexityReduction",
                    layer=MutationLayer.SEMANTIC,
                    mutator_name=self.__class__.__name__,
                    confidence=0.8,
                    description="Reduced algorithmic complexity through better algorithm selection",
                )
                logger.debug(
                    f"[SEMANTIC_DEBUG] Created result with mutator_name='{result.mutator_name}'"
                )
                results.append(result)

        # Strategy 2: Pattern Recognition and Replacement
        if self._is_strategy_enabled("AlgorithmicIntent_PatternRecognition"):
            variant = self._recognize_and_optimize_patterns(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="AlgorithmicIntent_PatternRecognition",
                        layer=MutationLayer.SEMANTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.7,
                        description="Recognized common algorithmic patterns and applied optimizations",
                    )
                )

        # Strategy 3: Architectural Improvements
        if self._is_strategy_enabled("AlgorithmicIntent_ArchitecturalImprovement"):
            variant = self._improve_program_architecture(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="AlgorithmicIntent_ArchitecturalImprovement",
                        layer=MutationLayer.SEMANTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.6,
                        description="Improved program architecture and design patterns",
                    )
                )

        return results

    def _optimize_algorithmic_complexity(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Focus on reducing Big-O complexity through algorithm selection."""
        prompt = f"""You are an expert algorithm designer and complexity analyst specializing in performance optimization.

Analyze the following code and optimize its algorithmic complexity for measurable performance improvements:

ANALYSIS REQUIREMENTS:
1. IDENTIFY current algorithm and its exact time/space complexity (Big-O notation)
2. BOTTLENECK ANALYSIS: Find the dominant operations causing complexity
3. INPUT PATTERNS: Consider typical input sizes and characteristics
4. OPTIMAL ALGORITHM SELECTION: Choose the best algorithm for this specific problem
5. IMPLEMENTATION: Rewrite with the optimized algorithm while preserving exact functionality

PERFORMANCE TARGETS:
- Aim for at least one order of magnitude improvement in time complexity
- Reduce space complexity where possible without sacrificing time gains
- Consider real-world performance (cache locality, constant factors)
- Ensure optimization is beneficial for expected input sizes

ALGORITHM FAMILIES TO CONSIDER:
- SORTING: Replace O(n²) with O(n log n) or specialized O(n) algorithms
- SEARCH: Linear → Binary → Hash-based O(1) lookups
- GRAPHS: BFS/DFS → Dijkstra/Floyd-Warshall/A* as appropriate
- DYNAMIC PROGRAMMING: Memoization → Tabulation → Space optimization
- DIVIDE AND CONQUER: Recursive → Iterative improvements
- GREEDY: Local optimal → Global optimal verification

OPTIMIZATION VERIFICATION:
- Ensure all edge cases are preserved (empty inputs, duplicates, etc.)
- Maintain identical output format and type
- Preserve all error conditions and exception handling
- Verify numerical stability for floating-point operations

CONSTRAINT: Only use standard library imports that are already present or explicitly allowed: {allowed_imports | self.allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Ensure the optimized version produces identical results for all inputs
- The optimization must provide measurable complexity improvement
- Do not break existing functionality or change the public interface
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _recognize_and_optimize_patterns(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Recognize common algorithmic patterns and apply known optimizations."""
        prompt = f"""You are an expert in algorithmic pattern recognition and performance optimization.

Analyze the code for recognizable algorithmic patterns and apply established, proven optimizations:

PATTERN RECOGNITION CHECKLIST:
- TWO-POINTER: Opposite-direction scanning for sorted/paired problems
- SLIDING WINDOW: Fixed/variable window for subarray/subsequence problems
- PREFIX SUM: Cumulative sums for range sum queries
- MEMOIZATION: Overlapping subproblems in recursive solutions
- GREEDY: Local optimal choices leading to global optimum
- UNION-FIND: Connected components and dynamic connectivity
- TOPOLOGICAL SORT: Dependency resolution in directed acyclic graphs
- BINARY SEARCH: Monotonic properties in sorted/search spaces

OPTIMIZATION STRATEGIES WITH PERFORMANCE IMPACT:
- NESTED LOOP ELIMINATION: O(n²) → O(n) using mathematical insights
- DATA STRUCTURE SELECTION: Lists → Sets/Dicts for O(1) operations
- EARLY TERMINATION: Break conditions to avoid unnecessary computation
- BIT MANIPULATION: Use bitwise operations for speed (AND, OR, XOR, shifts)
- MATHEMATICAL OPTIMIZATIONS: GCD, prime factorization, modular arithmetic
- CACHE-FRIENDLY ACCESS: Improve memory locality and reduce cache misses

PERFORMANCE VERIFICATION:
- Quantify complexity improvement (e.g., O(n²) → O(n log n))
- Ensure optimization doesn't increase constant factors excessively
- Verify space-time tradeoffs are beneficial
- Test edge cases: empty inputs, single elements, maximum constraints

IMPLEMENTATION REQUIREMENTS:
- Maintain exact functional behavior and output format
- Preserve all error handling and edge case management
- Use appropriate data structures from available imports
- Ensure numerical stability and precision

Available imports: {allowed_imports | self.allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Applied optimization must provide measurable performance improvement
- Preserve all existing functionality and edge case handling
- Do not introduce new dependencies beyond allowed imports
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _improve_program_architecture(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Improve high-level program architecture and design patterns."""
        prompt = f"""You are a software architect specializing in high-performance program design and efficiency optimization.

Improve the architectural design of this code for better performance, maintainability, and scalability:

ARCHITECTURAL ANALYSIS:
1. RESPONSIBILITY SEPARATION: Identify mixed concerns and separate into focused modules
2. COUPLING REDUCTION: Minimize dependencies between components
3. COHESION IMPROVEMENT: Group related functionality together
4. DATA FLOW OPTIMIZATION: Minimize data copying and improve data movement patterns
5. DESIGN PATTERN APPLICATION: Apply appropriate patterns (Strategy, Factory, Observer, etc.)

PERFORMANCE ARCHITECTURE:
- HOT PATH OPTIMIZATION: Identify and optimize critical execution paths
- MEMORY EFFICIENCY: Reduce allocations, improve memory reuse patterns
- CACHE LOCALITY: Structure data access for optimal CPU cache utilization
- CONSIDERATION: Minimize function call overhead in performance-critical sections
- LAZY EVALUATION: Defer computations until actually needed
- BATCHING: Group operations to reduce overhead

SCALABILITY CONSIDERATIONS:
- MODULAR DESIGN: Enable independent optimization of components
- EXTENSIBILITY: Design for future performance improvements
- RESOURCE MANAGEMENT: Efficient handling of memory, CPU, and I/O resources
- PARALLELISM OPPORTUNITIES: Identify sections suitable for concurrent execution

CODE QUALITY IMPROVEMENTS:
- ERROR HANDLING: Implement robust error management and recovery
- EDGE CASE MANAGEMENT: Ensure comprehensive handling of boundary conditions
- TYPE SAFETY: Use appropriate type hints and validation
- DOCUMENTATION: Clear interfaces and contracts between components

Available imports: {allowed_imports | self.allowed_imports}

Code to refactor:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Maintain identical external behavior and interface
- Architectural changes must provide measurable performance or maintainability benefits
- Preserve all existing functionality and error handling
- Do not break backward compatibility
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)


class ProgramIntentMutator(IROnlyMutator, LLMMutatorBase):
    """
    Focuses on understanding and optimizing program intent and logic flow.

    This mutator analyzes what the program is trying to accomplish and
    suggests alternative approaches that achieve the same goal more efficiently.
    """

    def __init__(
        self,
        llm_client=None,
        enabled_strategies: Optional[Set[str]] = None,
        allowed_imports: Optional[Set[str]] = None,
    ):
        IROnlyMutator.__init__(self, MutationLayer.SEMANTIC, enabled_strategies)
        LLMMutatorBase.__init__(self, llm_client, allowed_imports=allowed_imports)

    def get_available_strategies(self) -> List[str]:
        return [
            "ProgramIntent_LogicSimplification",
            "ProgramIntent_FlowOptimization",
            "ProgramIntent_PurposeAlignment",
        ]

    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply program intent optimization mutations."""
        results = []
        code = self.codegen.generate(ir)
        allowed_imports = self._get_imports(ir)

        # Strategy 1: Logic Simplification
        if self._is_strategy_enabled("ProgramIntent_LogicSimplification"):
            variant = self._simplify_program_logic(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="ProgramIntent_LogicSimplification",
                        layer=MutationLayer.SEMANTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.9,
                        description="Simplified program logic while maintaining intent",
                    )
                )

        # Strategy 2: Control Flow Optimization
        if self._is_strategy_enabled("ProgramIntent_FlowOptimization"):
            variant = self._optimize_control_flow(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="ProgramIntent_FlowOptimization",
                        layer=MutationLayer.SEMANTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.8,
                        description="Optimized control flow and execution paths",
                    )
                )

        # Strategy 3: Purpose Alignment
        if self._is_strategy_enabled("ProgramIntent_PurposeAlignment"):
            variant = self._align_implementation_with_purpose(code, allowed_imports)
            if variant:
                results.append(
                    create_mutation_result(
                        ir=variant,
                        strategy_name="ProgramIntent_PurposeAlignment",
                        layer=MutationLayer.SEMANTIC,
                        mutator_name=self.__class__.__name__,
                        confidence=0.7,
                        description="Aligned implementation more closely with intended purpose",
                    )
                )

        return results

    def _simplify_program_logic(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Simplify complex logic while preserving functionality."""
        prompt = f"""You are an expert in program logic simplification, boolean algebra, and performance optimization.

Simplify the logic in this code while maintaining exact functionality and improving performance:

LOGIC SIMPLIFICATION ANALYSIS:
1. IDENTIFY redundant conditional branches and unnecessary complexity
2. BOOLEAN ALGEBRA: Apply logical equivalences to reduce expression complexity
3. MATHEMATICAL RELATIONSHIPS: Use mathematical properties to simplify computations
4. CONTROL FLOW: Eliminate unnecessary nesting and branching
5. EXPRESSION OPTIMIZATION: Reduce computational complexity of boolean expressions

SIMPLIFICATION TECHNIQUES WITH PERFORMANCE IMPACT:
- CONDITION MERGING: Combine related conditions to reduce evaluation overhead
- DE MORGAN'S LAWS: not (a and b) → (not a) or (not b) for optimization
- SHORT-CIRCUIT OPTIMIZATION: Order conditions by likelihood and cost
- MATHEMATICAL REDUCTION: Replace complex expressions with simpler equivalents
- VARIABLE ELIMINATION: Remove intermediate variables that don't add value
- TRUTHINESS OPTIMIZATION: Use Python's truthiness for cleaner, faster code

PERFORMANCE CONSIDERATIONS:
- Reduce the number of boolean operations and comparisons
- Minimize function calls in conditional expressions
- Optimize for common case execution paths
- Consider branch prediction implications
- Reduce cyclomatic complexity for better maintainability

CORRECTNESS PRESERVATION:
- Maintain exact same input/output behavior for all possible inputs
- Preserve all edge case handling (None values, empty collections, etc.)
- Keep all error conditions and exception handling intact
- Ensure numerical precision is maintained for floating-point operations
- Verify timing-sensitive behavior is preserved

Available imports: {allowed_imports | self.allowed_imports}

Code to simplify:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Simplification must provide measurable performance or readability improvement
- Preserve all existing functionality, edge cases, and error handling
- Do not change the public interface or external behavior
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _optimize_control_flow(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Optimize control flow for better performance and clarity."""
        prompt = f"""You are an expert in control flow optimization, compiler theory, and performance engineering.

Optimize the control flow in this code for maximum performance and execution efficiency:

CONTROL FLOW ANALYSIS:
1. BRANCHING OPTIMIZATION: Minimize conditional complexity and branching overhead
2. LOOP STRUCTURE ANALYSIS: Optimize iteration patterns and loop constructs
3. EXECUTION PATH ANALYSIS: Identify and optimize hot paths and common cases
4. FUNCTION CALL OPTIMIZATION: Reduce call overhead in critical sections
5. STATE MANAGEMENT: Minimize state changes and side effects

PERFORMANCE OPTIMIZATION STRATEGIES:
- EARLY RETURN PATTERNS: Reduce nesting and improve exit efficiency
- CONDITION REORDERING: Place most likely/least expensive conditions first
- LOOP OPTIMIZATION: Convert recursive patterns to iterative where beneficial
- TAIL RECURSION: Optimize recursive calls for better stack usage
- SHORT-CIRCUIT EVALUATION: Leverage boolean logic for performance
- BRANCH PREDICTION: Structure conditions for CPU branch prediction

ADVANCED OPTIMIZATIONS:
- LOOP INVARIANT CODE MOTION: Move computations out of loops
- FUNCTION INLINING: Reduce call overhead for small, hot functions
- LAZY EVALUATION: Defer computations until actually needed
- MEMOIZATION: Cache results of expensive computations
- BATCHING: Group operations to reduce overhead

CODE QUALITY IMPROVEMENTS:
- Reduce cyclomatic complexity for better maintainability
- Improve readability through clearer control structures
- Maintain consistent error handling patterns
- Preserve debugging and profiling capabilities

Available imports: {allowed_imports | self.allowed_imports}

Code to optimize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Control flow changes must provide measurable performance improvement
- Preserve all existing functionality, error handling, and edge cases
- Maintain the same external interface and behavior
- Do not introduce new dependencies beyond allowed imports
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)

    def _align_implementation_with_purpose(
        self, code: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Align the implementation more closely with its intended purpose."""
        prompt = f"""You are an expert in program optimization, algorithmic analysis, and performance engineering.

Analyze this code's core purpose and realign the implementation for maximum efficiency and performance:

PURPOSE ANALYSIS FRAMEWORK:
1. CORE FUNCTIONALITY IDENTIFICATION: Determine the fundamental problem being solved
2. INPUT CHARACTERISTICS: Analyze expected input patterns, sizes, and distributions
3. PERFORMANCE REQUIREMENTS: Identify bottlenecks and critical performance factors
4. USAGE PATTERNS: Consider how the code is typically used in practice
5. OPTIMIZATION TARGETS: Focus on the most impactful improvements

SPECIALIZATION STRATEGIES:
- ALGORITHM SPECIALIZATION: Choose algorithms optimized for specific input characteristics
- DATA STRUCTURE SPECIALIZATION: Select structures based on access patterns and constraints
- SIZE-BASED OPTIMIZATION: Tailor algorithms for expected input sizes
- DISTRIBUTION-AWARE DESIGN: Optimize for known input distributions (sorted, random, etc.)
- FREQUENCY-BASED OPTIMIZATION: Prioritize optimizations for frequently used code paths

PERFORMANCE OPTIMIZATION TECHNIQUES:
- MICRO-OPTIMIZATIONS: Bit manipulation, mathematical shortcuts, memory layout
- ALGORITHMIC IMPROVEMENTS: Better complexity, cache-friendly access patterns
- LAZY EVALUATION: Defer work until actually needed
- BATCHING: Group operations to reduce overhead
- PREDICTION: Use heuristics to make better decisions

SPECIALIZATION EXAMPLES:
- SMALL ARRAYS: Use insertion sort instead of quicksort for n < 50
- SORTED DATA: Use binary search instead of linear search
- UNIQUE ELEMENTS: Use sets for O(1) operations instead of lists
- COUNTING OPERATIONS: Use Counter or defaultdict for frequency analysis
- NUMERICAL COMPUTATIONS: Use numpy or specialized math functions

IMPLEMENTATION REQUIREMENTS:
- Maintain exact functional behavior and output format
- Preserve all error handling and edge case management
- Ensure numerical stability and precision
- Consider maintainability and readability
- Optimize for real-world usage patterns

Available imports: {allowed_imports}

Code to specialize:
{code}

CRITICAL REQUIREMENTS:
- Return ONLY valid Python code with NO markdown, NO explanations, NO comments
- Use EXACTLY 4 spaces per indentation level
- Specialization must provide measurable performance improvement
- Preserve all existing functionality and edge case handling
- Maintain the same external interface and behavior
- Do not introduce unnecessary complexity or reduce maintainability
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)
