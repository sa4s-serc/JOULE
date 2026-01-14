

import logging
from typing import List, Tuple, Optional
from src.domain.ir import schema
from src.application.mutators.semantic_base import LLMMutatorBase

logger = logging.getLogger(__name__)

class SyntacticReasoningMutator(LLMMutatorBase):
    """
    Uses LLM to perform granular syntactic optimizations.
    Focuses on:
    - List/Dict/Set comprehensions
    - Simplified boolean logic
    - Pythonic idioms (zip, enumerate)
    - Removing redundant variables
    """
    
    def mutate(self, ir: schema.Module) -> List[Tuple[schema.Module, str]]:
        variants = []
        code = self.codegen.generate(ir)
        
        # Strategy 1: Comprehensions
        variant = self._mutate_with_prompt(
            code,
            "Identify loops that can be replaced with List/Dict/Set comprehensions or Generator Expressions. Replace them.",
            "Syntactic_Comprehension"
        )
        if variant:
            variants.append((variant, "Syntactic_Comprehensions"))

        # Strategy 2: Boolean Simplification
        variant = self._mutate_with_prompt(
            code,
            "Identify complex boolean expressions or redundant 'if' checks. Simplify them significantly (e.g. De Morgan's laws, truthy checks).",
            "Syntactic_Boolean"
        )
        if variant:
            variants.append((variant, "Syntactic_Boolean"))

        # Strategy 3: Built-in Idioms
        variant = self._mutate_with_prompt(
            code,
            "Identify manual counters or index tracking. Replace with 'enumerate', 'zip', or 'itertools'.",
            "Syntactic_Idioms"
        )
        if variant:
            variants.append((variant, "Syntactic_Idioms"))
            
        return variants

    def _mutate_with_prompt(self, code: str, instruction: str, strategy_name: str) -> Optional[schema.Module]:
        prompt = f"""You are an expert Python linter and refactoring tool.
Objective: {instruction}

Constraints:
1. Do NOT change the algorithm complexity or logic.
2. Only change the SYNTAX to be more efficient and pythonic.
3. Keep imports exactly as they are. Do NOT add new imports.

Code:
{code}

Return ONLY the refactored Python code.
"""
        try:
            response = self.llm.complete(prompt).strip()
            optimized_code = self._clean_code(response)
            
            if optimized_code and optimized_code != code:
                new_ir = self._safe_parse(optimized_code)
                # Validation: Syntactic mutator shouldn't change imports at all
                if new_ir:
                     # Reuse import validation logic - ensure no new imports
                     old_imports = self._get_imports(self.parser.parse(code))
                     new_imports = self._get_imports(new_ir)
                     if new_imports.issubset(old_imports):
                         return new_ir
                     else:
                         logger.warning(f"{strategy_name} added new imports, which is forbidden.")
        except Exception as e:
            logger.error(f"{strategy_name} failed: {e}")
            
        return None
