"""
Syntactic Reasoning Mutator - Granular syntactic optimizations.

Performs syntax-level optimizations including:
- List/Dict/Set comprehensions
- Boolean simplification
- Pythonic idioms (zip, enumerate)
"""
import logging
from typing import List, Tuple, Optional, Set
from src.domain.ir import schema
from src.application.mutators.semantic_base import LLMMutatorBase

logger = logging.getLogger(__name__)


class SyntacticReasoningMutator(LLMMutatorBase):
    """
    Uses LLM to perform granular syntactic optimizations.
    
    Focuses on syntax improvements that don't change algorithm complexity:
    - Comprehensions for loops
    - Boolean expression simplification
    - Pythonic idioms
    """
    
    # Mutation strategies with their instructions
    STRATEGIES = {
        "Syntactic_Comprehensions": "Identify loops that can be replaced with List/Dict/Set comprehensions or Generator Expressions. Replace them.",
        "Syntactic_Boolean": "Identify complex boolean expressions or redundant 'if' checks. Simplify them (De Morgan's laws, truthy checks).",
        "Syntactic_Idioms": "Identify manual counters or index tracking. Replace with 'enumerate', 'zip', or 'itertools'.",
    }
    
    def mutate(self, ir: schema.Module) -> List[Tuple[schema.Module, str]]:
        variants = []
        code = self.codegen.generate(ir)
        original_imports = self._get_imports(ir)
        
        for strategy_name, instruction in self.STRATEGIES.items():
            variant = self._apply_syntactic_mutation(code, instruction, strategy_name, original_imports)
            if variant:
                variants.append((variant, strategy_name))
            
        return variants

    def _apply_syntactic_mutation(
        self, 
        code: str, 
        instruction: str, 
        strategy_name: str,
        original_imports: Set[str]
    ) -> Optional[schema.Module]:
        """Apply a syntactic mutation with strict import validation."""
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
            response = self._complete_with_cache(prompt)
            optimized_code = self._clean_code(response)
            
            if optimized_code and optimized_code != code:
                new_ir = self._safe_parse(optimized_code)
                if new_ir:
                    # Strict validation: no new imports allowed for syntactic changes
                    new_imports = self._get_imports(new_ir)
                    if new_imports.issubset(original_imports):
                        return new_ir
                    else:
                        added = new_imports - original_imports
                        logger.warning(f"{strategy_name} added imports {added}, rejected")
        except Exception as e:
            logger.error(f"{strategy_name} failed: {e}")
            
        return None
