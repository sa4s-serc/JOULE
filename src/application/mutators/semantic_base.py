"""
LLM Mutator Base - Shared functionality for LLM-based mutations.

This module provides the base class for all LLM-powered mutators,
consolidating common functionality like:
- Code extraction from LLM responses
- Parse/repair loops
- Response caching for API efficiency
- Comment sanitization for security

Import validation has been moved to src.utils.import_validator for centralization.
"""

import hashlib
import logging
from typing import Dict, Optional, Set

from src.domain.interfaces import Mutator
from src.domain.ir import schema
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser
from src.utils.comment_sanitizer import sanitize_code_for_llm
from src.utils.import_validator import ImportValidator

logger = logging.getLogger(__name__)


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
    - Response caching for API efficiency

    Import validation is handled by ImportValidator utility.
    """

    def __init__(
        self,
        llm_client,
        max_retries: int = 3,
        use_cache: bool = True,
        allowed_imports: Optional[Set[str]] = None,
    ):
        self.llm = llm_client
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.max_retries = max_retries
        self.use_cache = use_cache
        self._cache = _llm_response_cache

        # Store allowed_imports for direct access by subclasses
        self.allowed_imports = allowed_imports or set()

        # Initialize import validator with additional allowed imports
        self.import_validator = ImportValidator(allowed_imports)

    def _clean_code(self, response: str) -> str:
        """
        Extract code from LLM response, handling markdown code blocks.

        Handles formats:
        - ```python ... ```
        - ``` ... ```
        - Plain code

        Also normalizes indentation to prevent IndentationError.
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

        code = response.strip()

        # Normalize indentation FIRST (convert tabs to spaces, fix inconsistencies)
        code = self._normalize_indentation(code)

        # Then fix common syntax errors
        code = self._fix_common_syntax_errors(code)

        return code

    def _normalize_indentation(self, code: str) -> str:
        """
        Normalize indentation to consistent 4-space indents.

        This is the FIRST step in cleaning code - it ensures all indentation
        is consistent before any other processing.

        Handles:
        - Mixed tabs and spaces
        - Inconsistent indent levels
        - Unindent to invalid levels

        Note: We use a simple stack-based approach. Block continuation keywords
        (else, elif, except, finally) are handled by the normal unindent logic.
        """
        # Convert all tabs to 4 spaces
        code = code.replace("\t", "    ")

        lines = code.split("\n")
        normalized_lines = []
        indent_stack = [0]  # Stack of valid indentation levels

        for i, line in enumerate(lines):
            # Preserve empty lines
            if not line.strip():
                normalized_lines.append("")
                continue

            stripped = line.lstrip()
            current_indent = len(line) - len(stripped)

            # Determine the correct indentation level
            if current_indent > indent_stack[-1]:
                # Indenting: should be exactly 4 more than previous
                correct_indent = indent_stack[-1] + 4
                indent_stack.append(correct_indent)
            elif current_indent < indent_stack[-1]:
                # Unindenting: must match a previous level
                # Pop stack until we find a matching or smaller level
                while len(indent_stack) > 1 and indent_stack[-1] > current_indent:
                    indent_stack.pop()

                # Use the current stack top as the correct indent
                correct_indent = indent_stack[-1]

                # If current_indent doesn't match any valid level, snap to closest
                if current_indent != correct_indent and current_indent < correct_indent:
                    # Find the closest valid level
                    for level in reversed(indent_stack[:-1]):
                        if level <= current_indent:
                            correct_indent = level
                            # Update stack
                            while indent_stack[-1] > correct_indent:
                                indent_stack.pop()
                            break
            else:
                # Same level as before
                correct_indent = indent_stack[-1]

            # Reconstruct line with correct indentation
            normalized_lines.append(" " * correct_indent + stripped)

        return "\n".join(normalized_lines)

    def _fix_common_syntax_errors(self, code: str) -> str:
        """
        Fix common syntax errors in LLM-generated code.

        Common issues:
        - Empty else/elif/except/finally blocks
        - Incomplete statements
        - Missing pass statements

        NOTE: Indentation should already be normalized by _normalize_indentation()
        """
        lines = code.split("\n")
        fixed_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Keep the line as-is
            fixed_lines.append(line)

            # Check if this line starts a block (ends with colon)
            if stripped and stripped.endswith(":"):
                current_indent = len(line) - len(line.lstrip())

                # Look ahead to see if there's a properly indented body
                needs_pass = True

                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()

                    if next_stripped:  # Non-empty next line
                        next_indent = len(next_line) - len(next_line.lstrip())

                        # If next line is indented more, block has content
                        if next_indent > current_indent:
                            needs_pass = False

                # Add pass if block is empty
                if needs_pass:
                    fixed_lines.append(" " * (current_indent + 4) + "pass")

        return "\n".join(fixed_lines)

    def _get_imports(self, ir: schema.Module) -> Set[str]:
        """
        DEPRECATED: Use ImportValidator.extract_imports() instead.

        Extract set of imported module names from IR.
        Returns the base module name (e.g., 'os' from 'os.path').
        """
        import warnings

        warnings.warn(
            "_get_imports is deprecated. Use ImportValidator.extract_imports() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.import_validator.extract_imports(ir)

    def _repair_code(self, broken_code: str, error_msg: str) -> Optional[schema.Module]:
        """Attempt to repair broken code using the LLM."""
        logger.debug(f"Attempting to repair code. Error: {error_msg}")

        prompt = f"""You are an expert Python debugger specializing in fixing indentation and syntax errors.

ERROR: {error_msg}

BROKEN CODE:
{broken_code}

Fix the code and return ONLY the corrected Python code with NO explanations, NO markdown, NO comments.

CRITICAL INDENTATION RULES (IndentationError is the most common issue):
1. Use EXACTLY 4 spaces per indentation level (NEVER use tabs)
2. Each indent must be EXACTLY 4 spaces more than the parent
3. Each unindent must return to a PREVIOUS valid indentation level
4. Empty blocks MUST contain 'pass' statement
5. All lines at the same logical level must have IDENTICAL indentation

CORRECT EXAMPLE:
def example(x):
    if x > 0:
        return x * 2
    else:
        pass

INCORRECT (will cause IndentationError):
def example(x):
  if x > 0:  # Wrong: 2 spaces instead of 4
      return x * 2  # Wrong: 6 spaces (not a multiple of 4)
    else:  # Wrong: doesn't match any previous level
        pass

Return ONLY the fixed code:"""
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
                    # If repair returned None, try one more time with normalized code
                    logger.debug("LLM repair failed, attempting local normalization")
                    try:
                        normalized = self._normalize_indentation(code)
                        normalized = self._fix_common_syntax_errors(normalized)
                        return self.parser.parse(normalized)
                    except Exception as e2:
                        logger.debug(f"Local normalization also failed: {e2}")
                        break  # Give up on this code
                else:
                    logger.warning(f"Final parse failed after {self.max_retries} retries: {e}")
        return None

    def _validate_imports(self, new_ir: schema.Module, allowed_imports: Set[str]) -> bool:
        """
        DEPRECATED: Use ImportValidator.validate_imports() instead.

        Ensure no new unauthorized imports are added.
        """
        import warnings

        warnings.warn(
            "_validate_imports is deprecated. Use ImportValidator.validate_imports() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.import_validator.validate_imports(new_ir, allowed_imports)

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
                if new_ir and self.import_validator.validate_imports(new_ir, allowed_imports):
                    return new_ir
        except Exception as e:
            logger.error(f"Mutation failed: {e}")
        return None

    def mutate(self, ir: schema.Module):
        raise NotImplementedError("Subclasses must implement mutate()")
