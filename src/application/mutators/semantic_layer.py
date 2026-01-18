"""
Semantic Layer Mutators - Algorithm Intent and High-Level Logic

These mutators operate at the highest abstraction level, focusing on:
- Algorithm selection and optimization
- High-level program intent and logic flow
- Architectural patterns and design improvements
"""
import logging
from typing import List, Optional, Set
from src.application.mutators.ir_mutator_base import IROnlyMutator
from src.application.mutators.base import MutationLayer, MutationResult, create_mutation_result
from src.application.mutators.semantic_base import LLMMutatorBase
from src.domain.ir import schema

logger = logging.getLogger(__name__)


class AlgorithmicIntentMutator(IROnlyMutator, LLMMutatorBase):
    """
    Focuses on high-level algorithmic improvements and intent optimization.
    
    This mutator understands the program's purpose and suggests algorithmic
    alternatives that maintain the same intent but with better characteristics.
    """
    
    def __init__(self, llm_client=None, enabled_strategies: Optional[Set[str]] = None):
        IROnlyMutator.__init__(self, MutationLayer.SEMANTIC, enabled_strategies)
        LLMMutatorBase.__init__(self, llm_client)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "AlgorithmicIntent_ComplexityReduction",
            "AlgorithmicIntent_PatternRecognition", 
            "AlgorithmicIntent_ArchitecturalImprovement"
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
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="AlgorithmicIntent_ComplexityReduction",
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.8,
                    description="Reduced algorithmic complexity through better algorithm selection"
                ))
        
        # Strategy 2: Pattern Recognition and Replacement
        if self._is_strategy_enabled("AlgorithmicIntent_PatternRecognition"):
            variant = self._recognize_and_optimize_patterns(code, allowed_imports)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="AlgorithmicIntent_PatternRecognition", 
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.7,
                    description="Recognized common algorithmic patterns and applied optimizations"
                ))
        
        # Strategy 3: Architectural Improvements
        if self._is_strategy_enabled("AlgorithmicIntent_ArchitecturalImprovement"):
            variant = self._improve_program_architecture(code, allowed_imports)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="AlgorithmicIntent_ArchitecturalImprovement",
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.6,
                    description="Improved program architecture and design patterns"
                ))
        
        return results
    
    def _optimize_algorithmic_complexity(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Focus on reducing Big-O complexity through algorithm selection."""
        prompt = f"""You are an expert algorithm designer and complexity analyst.

Analyze the following code and optimize its algorithmic complexity:

1. IDENTIFY the current algorithm and its time/space complexity
2. DETERMINE if there's a more efficient algorithm for the same problem
3. IMPLEMENT the optimized algorithm while preserving exact functionality
4. ENSURE the optimization provides measurable complexity improvement

Focus on:
- Sorting algorithms (quicksort vs mergesort vs timsort)
- Search algorithms (linear vs binary vs hash-based)
- Graph algorithms (BFS vs DFS vs specialized algorithms)
- Dynamic programming opportunities
- Divide and conquer optimizations

CONSTRAINT: Only use standard library imports that are already present: {allowed_imports}

Code to optimize:
{code}

Return ONLY the optimized Python code with better algorithmic complexity.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)
    
    def _recognize_and_optimize_patterns(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Recognize common algorithmic patterns and apply known optimizations."""
        prompt = f"""You are an expert in algorithmic patterns and optimizations.

Analyze the code for common algorithmic patterns and apply established optimizations:

PATTERNS TO RECOGNIZE:
- Two-pointer technique opportunities
- Sliding window problems
- Prefix sum optimizations
- Memoization/caching opportunities
- Greedy algorithm applications
- Union-find structures
- Topological sorting needs

OPTIMIZATION STRATEGIES:
- Replace nested loops with mathematical formulas where possible
- Use appropriate data structures (heaps, sets, deques)
- Apply mathematical optimizations (GCD, prime factorization, etc.)
- Implement early termination conditions
- Use bit manipulation where appropriate

Current imports available: {allowed_imports}

Code:
{code}

Return ONLY the optimized code with recognized patterns efficiently implemented.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)
    
    def _improve_program_architecture(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Improve high-level program architecture and design patterns."""
        prompt = f"""You are a software architect focused on program design and efficiency.

Improve the architectural design of this code:

ARCHITECTURAL IMPROVEMENTS:
- Separate concerns and improve modularity
- Reduce coupling between components
- Eliminate redundant computations across functions
- Optimize data flow and minimize data copying
- Apply appropriate design patterns (Strategy, Factory, etc.)
- Improve error handling and edge case management

PERFORMANCE ARCHITECTURE:
- Minimize function call overhead where beneficial
- Reduce memory allocations
- Optimize hot paths and critical sections
- Improve cache locality in data access patterns

Available imports: {allowed_imports}

Code:
{code}

Return ONLY the architecturally improved code that maintains functionality.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)


class ProgramIntentMutator(IROnlyMutator, LLMMutatorBase):
    """
    Focuses on understanding and optimizing program intent and logic flow.
    
    This mutator analyzes what the program is trying to accomplish and
    suggests alternative approaches that achieve the same goal more efficiently.
    """
    
    def __init__(self, llm_client=None, enabled_strategies: Optional[Set[str]] = None):
        IROnlyMutator.__init__(self, MutationLayer.SEMANTIC, enabled_strategies)
        LLMMutatorBase.__init__(self, llm_client)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "ProgramIntent_LogicSimplification",
            "ProgramIntent_FlowOptimization",
            "ProgramIntent_PurposeAlignment"
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
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="ProgramIntent_LogicSimplification",
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.9,
                    description="Simplified program logic while maintaining intent"
                ))
        
        # Strategy 2: Control Flow Optimization  
        if self._is_strategy_enabled("ProgramIntent_FlowOptimization"):
            variant = self._optimize_control_flow(code, allowed_imports)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="ProgramIntent_FlowOptimization",
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.8,
                    description="Optimized control flow and execution paths"
                ))
        
        # Strategy 3: Purpose Alignment
        if self._is_strategy_enabled("ProgramIntent_PurposeAlignment"):
            variant = self._align_implementation_with_purpose(code, allowed_imports)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="ProgramIntent_PurposeAlignment",
                    layer=MutationLayer.SEMANTIC,
                    confidence=0.7,
                    description="Aligned implementation more closely with intended purpose"
                ))
        
        return results
    
    def _simplify_program_logic(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Simplify complex logic while preserving functionality."""
        prompt = f"""You are an expert in program logic simplification and clarity.

Simplify the logic in this code while maintaining exact functionality:

SIMPLIFICATION TECHNIQUES:
- Eliminate unnecessary conditional branches
- Combine redundant checks and operations
- Use mathematical relationships to reduce complexity
- Apply logical equivalences (De Morgan's laws, etc.)
- Remove intermediate variables that don't add clarity
- Simplify boolean expressions and conditions

MAINTAIN:
- Exact same input/output behavior
- All edge case handling
- Error conditions and exceptions

Available imports: {allowed_imports}

Code:
{code}

Return ONLY the logically simplified code.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)
    
    def _optimize_control_flow(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Optimize control flow for better performance and clarity."""
        prompt = f"""You are an expert in control flow optimization and program efficiency.

Optimize the control flow in this code:

CONTROL FLOW OPTIMIZATIONS:
- Minimize branching and conditional complexity
- Use early returns to reduce nesting
- Optimize loop structures and iteration patterns
- Eliminate redundant function calls
- Reduce the number of execution paths
- Apply short-circuit evaluation effectively

PERFORMANCE IMPROVEMENTS:
- Move expensive operations out of loops where possible
- Optimize the order of conditional checks (most likely first)
- Reduce function call overhead in hot paths
- Minimize state changes and side effects

Available imports: {allowed_imports}

Code:
{code}

Return ONLY the control-flow optimized code.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)
    
    def _align_implementation_with_purpose(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Align the implementation more closely with its intended purpose."""
        prompt = f"""You are an expert in program design and implementation alignment.

Analyze this code's purpose and align the implementation for maximum efficiency:

ALIGNMENT STRATEGIES:
- Identify the core purpose and optimize for that specific use case
- Remove general-purpose overhead if not needed
- Specialize data structures for the specific problem domain
- Optimize for the expected input characteristics
- Align memory usage patterns with the problem requirements
- Choose algorithms that match the expected data distribution

SPECIALIZATION OPPORTUNITIES:
- If sorting small arrays, use insertion sort instead of quicksort
- If searching in sorted data, use binary search
- If working with unique elements, use sets instead of lists
- If counting occurrences, use Counter or defaultdict

Available imports: {allowed_imports}

Code:
{code}

Return ONLY the purpose-aligned optimized code.
"""
        return self._mutate_with_prompt(code, prompt, allowed_imports)