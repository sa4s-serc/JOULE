
import logging
from typing import Optional, Set
from src.domain.interfaces import Mutator
from src.domain.ir import schema
from src.infrastructure.parsing.python_parser import PythonParser
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator

logger = logging.getLogger(__name__)

class LLMMutatorBase(Mutator):
    """
    Base class for LLM-based mutations.
    Handles:
    - Code generation from IR
    - Parsing LLM response
    - Self-repair loop
    - Import extraction
    """
    
    def __init__(self, llm_client, max_retries: int = 3):
        self.llm = llm_client
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.max_retries = max_retries
        
    def _clean_code(self, response: str) -> str:
        """Extract code from LLM response."""
        if "```python" in response:
            response = response.split("```python", 1)[1]
        elif "```" in response:
            response = response.split("```", 1)[1]
        
        if "```" in response:
            response = response.split("```", 0)[0] # Fix logic error: split[0] keeps content before second `
            # Actually if we split by ``` again, it cleans the trailing block.
            response = response.split("```")[0]
            
        return response.strip()

    def _get_imports(self, ir: schema.Module) -> Set[str]:
        """Extract set of imported module names from IR."""
        imports = set()
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(stmt, schema.ImportFrom):
                if stmt.module:
                    imports.add(stmt.module.split('.')[0])
        return imports

    def _repair_code(self, broken_code: str, error_msg: str) -> Optional[schema.Module]:
        """Attempt to repair broken code using the LLM."""
        logger.info(f"Attempting to repair code. Error: {error_msg}")
        
        prompt = f"""You are an expert Python debugger.
The following code has a syntax error or is invalid.
Error: {error_msg}

Code:
{broken_code}

Fix the code and return ONLY the corrected Python code.
"""
        try:
            response = self.llm.complete(prompt).strip()
            fixed_code = self._clean_code(response)
            return self.parser.parse(fixed_code)
        except Exception as e:
            logger.warning(f"Repair failed: {e}")
            return None

    def _safe_parse(self, code: str) -> Optional[schema.Module]:
        """Parse code with a repair loop."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.parser.parse(code)
            except Exception as e:
                if attempt < self.max_retries:
                    logger.debug(f"Parse failed (attempt {attempt+1}): {e}")
                    repaired_ir = self._repair_code(code, str(e))
                    if repaired_ir:
                        return repaired_ir
                    break # Repair failed
                else:
                    logger.warning(f"Final parse failed: {e}")
        return None

    def _validate_imports(self, new_ir: schema.Module, allowed_imports: Set[str]) -> bool:
        """Ensure no new unauthorized imports are added."""
        new_imports = self._get_imports(new_ir)
        
        # Comprehensive standard library whitelist
        STDLIB_WHITELIST = {
            'math', 'itertools', 'functools', 'collections', 'heapq', 'bisect',
            'typing', 'random', 'time', 'datetime', 're', 'sys', 'os', 'copy',
            'statistics', 'operator', 'string', 'json', 'uuid', 'pathlib'
        }
        
        for imp in new_imports:
            if imp not in allowed_imports and imp not in STDLIB_WHITELIST:
                logger.warning(f"Mutation rejected using unauthorized import: {imp}")
                return False
        return True

    def _mutate_with_prompt(self, code: str, prompt: str, allowed_imports: Set[str]) -> Optional[schema.Module]:
        """Generic mutation helper with CoT and repair."""
        try:
            response = self.llm.complete(prompt).strip()
            optimized_code = self._clean_code(response)
            
            if optimized_code and optimized_code != code:
                # Use the retry/repair logic from _safe_parse
                new_ir = self._safe_parse(optimized_code)
                if new_ir:
                    if self._validate_imports(new_ir, allowed_imports):
                        return new_ir
        except Exception as e:
            logger.error(f"Mutation failed: {e}")
        return None

    def mutate(self, ir: schema.Module):
        raise NotImplementedError
