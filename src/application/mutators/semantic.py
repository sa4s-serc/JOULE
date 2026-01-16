"""
Semantic Mutator - High-level LLM-based optimizations.

Performs semantic-level optimizations including:
- Standard library utilization
- Algorithmic complexity improvements
"""
import logging
from typing import List, Tuple, Optional, Set
from src.domain.ir import schema
from src.application.mutators.semantic_base import LLMMutatorBase

logger = logging.getLogger(__name__)


class SemanticMutator(LLMMutatorBase):
    """
    Uses LLM to perform high-level semantic optimizations.
    
    Strategies:
    - Library: Replace manual implementations with stdlib
    - Algorithmic: Improve time/space complexity
    """
    
    # Import constraint appended to all prompts
    IMPORT_CONSTRAINT = "\nCONSTRAINT: Do NOT import external libraries (numpy, pandas, etc). Only use standard library."
    
    def mutate(self, ir: schema.Module) -> List[Tuple[schema.Module, str]]:
        variants = []
        allowed_imports = self._get_imports(ir)
        code = self.codegen.generate(ir)
        
        # Strategy 1: Library optimization (StdLib)
        variant = self._mutate_library(code, allowed_imports)
        if variant:
            variants.append((variant, "Semantic_Library"))
        
        # Strategy 2: Algorithmic improvement
        variant = self._mutate_algorithmic(code, allowed_imports)
        if variant:
            variants.append((variant, "Semantic_Algorithmic"))
        
        return variants

    def _mutate_with_constrained_prompt(self, code: str, prompt: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Mutation helper that appends import constraint to prompt."""
        full_prompt = prompt + self.IMPORT_CONSTRAINT
        return self._mutate_with_prompt(code, full_prompt, allowed_imports)
    
    def _mutate_library(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Replace manual implementations with standard library."""
        prompt = f"""You are an expert Python performance engineer.
Optimize the following code by replacing manual implementations with standard library functions.

Steps:
1. Identify manually implemented algorithms (sorting, searching, counting)
2. Replace with itertools, collections, functools, or math equivalents
3. Ensure performance is improved

Return ONLY the Python code, no markdown, no explanations.

Code:
{code}
"""
        return self._mutate_with_constrained_prompt(code, prompt, allowed_imports)
    
    def _mutate_algorithmic(self, code: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Improve algorithmic complexity."""
        prompt = f"""You are an expert algorithm designer.
Analyze and optimize the time or space complexity of this code.

Steps:
1. Analyze current Big-O complexity
2. Identify bottlenecks
3. Propose more efficient data structure or algorithm
4. Implement the optimization

Return ONLY the Python code, no markdown, no explanations.

Code:
{code}
"""
        return self._mutate_with_constrained_prompt(code, prompt, allowed_imports)

