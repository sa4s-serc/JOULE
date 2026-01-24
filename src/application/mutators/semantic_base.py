"""
LLM Mutator Base - Shared functionality for LLM-based mutations.

This module provides the base class for all LLM-powered mutators,
consolidating common functionality like:
- Code extraction from LLM responses
- Import validation with whitelist
- Parse/repair loops
- Response caching for API efficiency
- Comment sanitization for security
"""

import hashlib
import logging
from typing import Dict, Optional, Set

from src.domain.interfaces import Mutator
from src.domain.ir import schema
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser
from src.utils.comment_sanitizer import sanitize_code_for_llm

logger = logging.getLogger(__name__)

# Comprehensive standard library whitelist - shared across all LLM mutators
STDLIB_WHITELIST: frozenset = frozenset(
    {
        "math",
        "itertools",
        "functools",
        "collections",
        "heapq",
        "bisect",
        "typing",
        "random",
        "time",
        "datetime",
        "re",
        "sys",
        "os",
        "copy",
        "statistics",
        "operator",
        "string",
        "json",
        "uuid",
        "pathlib",
        "decimal",
        "fractions",
        "numbers",
        "cmath",
        "array",
        "enum",
        "dataclasses",
        "abc",
        "contextlib",
        "io",
        "struct",
        "codecs",
    }
)


class LLMResponseCache:
    """
    Simple LRU cache for LLM responses to reduce API calls.

    Caches responses based on prompt hash to avoid redundant API calls
    for identical or similar code patterns.
    """

    __slots__ = ("_cache", "_max_size", "_hits", "_misses")

    def __init__(self, max_size: int = 500):
        self._cache: Dict[str, str] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def _hash_prompt(self, prompt: str) -> str:
        """Create a hash key for the prompt."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

    def get(self, prompt: str) -> Optional[str]:
        """Get cached response for prompt."""
        key = self._hash_prompt(prompt)
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def set(self, prompt: str, response: str) -> None:
        """Cache a response for a prompt."""
        if len(self._cache) >= self._max_size:
            # Simple eviction: remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        key = self._hash_prompt(prompt)
        self._cache[key] = response

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Global cache instance shared across all LLM mutators
_llm_response_cache = LLMResponseCache()


def get_llm_cache() -> LLMResponseCache:
    """Get the global LLM response cache."""
    return _llm_response_cache


class LLMMutatorBase(Mutator):
    """
    Base class for LLM-based mutations.

    Provides shared functionality:
    - Code generation from IR
    - LLM response parsing and cleaning
    - Self-repair loop for invalid code
    - Import extraction and validation
    - Response caching for API efficiency
    """

    def __init__(self, llm_client, max_retries: int = 3, use_cache: bool = True):
        self.llm = llm_client
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.max_retries = max_retries
        self.use_cache = use_cache
        self._cache = _llm_response_cache

    def _clean_code(self, response: str) -> str:
        """
        Extract code from LLM response, handling markdown code blocks.

        Handles formats:
        - ```python ... ```
        - ``` ... ```
        - Plain code
        """
        if not response:
            return ""

        # Handle ```python blocks
        if "```python" in response:
            parts = response.split("```python", 1)
            if len(parts) > 1:
                response = parts[1]
        elif "```" in response:
            parts = response.split("```", 1)
            if len(parts) > 1:
                response = parts[1]

        # Remove trailing ``` if present
        if "```" in response:
            response = response.split("```")[0]

        return response.strip()

    def _get_imports(self, ir: schema.Module) -> Set[str]:
        """
        Extract set of imported module names from IR.

        Returns the base module name (e.g., 'os' from 'os.path').
        """
        imports = set()
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(stmt, schema.ImportFrom):
                if stmt.module:
                    imports.add(stmt.module.split(".")[0])
        return imports

    def _repair_code(self, broken_code: str, error_msg: str) -> Optional[schema.Module]:
        """Attempt to repair broken code using the LLM."""
        logger.debug(f"Attempting to repair code. Error: {error_msg}")

        prompt = f"""You are an expert Python debugger.
The following code has a syntax error or is invalid.
Error: {error_msg}

Code:
{broken_code}

Fix the code and return ONLY the corrected Python code, no explanations.
"""
        try:
            response = self.llm.complete(prompt).strip()
            fixed_code = self._clean_code(response)
            return self.parser.parse(fixed_code)
        except Exception as e:
            logger.warning(f"Repair failed: {e}")
            return None

    def _safe_parse(self, code: str) -> Optional[schema.Module]:
        """Parse code with a repair loop on failure."""
        for attempt in range(self.max_retries + 1):
            try:
                return self.parser.parse(code)
            except Exception as e:
                if attempt < self.max_retries:
                    logger.debug(f"Parse failed (attempt {attempt+1}): {e}")
                    repaired_ir = self._repair_code(code, str(e))
                    if repaired_ir:
                        return repaired_ir
                    break  # Repair failed, don't retry
                else:
                    logger.warning(f"Final parse failed: {e}")
        return None

    def _validate_imports(self, new_ir: schema.Module, allowed_imports: Set[str]) -> bool:
        """
        Ensure no new unauthorized imports are added.

        Allows:
        - Imports already present in the original code
        - Standard library imports from STDLIB_WHITELIST
        """
        new_imports = self._get_imports(new_ir)

        for imp in new_imports:
            if imp not in allowed_imports and imp not in STDLIB_WHITELIST:
                logger.warning(f"Mutation rejected: unauthorized import '{imp}'")
                return False
        return True

    def _complete_with_cache(self, prompt: str) -> str:
        """
        Get LLM completion with caching support.

        Checks cache first, falls back to API call if not cached.
        """
        if self.use_cache:
            cached = self._cache.get(prompt)
            if cached is not None:
                logger.debug("LLM cache hit")
                return cached

        response = self.llm.complete(prompt).strip()

        if self.use_cache and response:
            self._cache.set(prompt, response)

        return response

    def _mutate_with_prompt(
        self, code: str, prompt: str, allowed_imports: Set[str]
    ) -> Optional[schema.Module]:
        """
        Generic mutation helper with caching, parsing, and validation.

        Args:
            code: Original code string
            prompt: LLM prompt for mutation
            allowed_imports: Set of allowed import names

        Returns:
            Mutated IR module or None if mutation failed/invalid
        """
        try:
            # SECURITY: Sanitize code before sending to LLM
            sanitization_result = sanitize_code_for_llm(code)

            if not sanitization_result.is_safe:
                logger.warning(
                    f"Code contains sensitive patterns, skipping LLM mutation: {sanitization_result.sensitive_patterns_found}"
                )
                return None

            if sanitization_result.removed_comments:
                logger.info(
                    f"Removed {len(sanitization_result.removed_comments)} comments before LLM transmission"
                )

            # Use sanitized code in prompt
            sanitized_code = sanitization_result.sanitized_code
            sanitized_prompt = prompt.replace(code, sanitized_code)

            response = self._complete_with_cache(sanitized_prompt)
            optimized_code = self._clean_code(response)

            if optimized_code and optimized_code != code:
                new_ir = self._safe_parse(optimized_code)
                if new_ir and self._validate_imports(new_ir, allowed_imports):
                    return new_ir
        except Exception as e:
            logger.error(f"Mutation failed: {e}")
        return None

    def mutate(self, ir: schema.Module):
        raise NotImplementedError("Subclasses must implement mutate()")
