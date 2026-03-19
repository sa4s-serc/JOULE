"""
Gemini LLM Client Implementation

This module provides a client for interacting with Google's Gemini API
for semantic code analysis and mutation suggestions.

Supports multi-key rotation: set GEMINI_API_KEYS (comma-separated) in the
environment to automatically rotate keys on rate-limit (429) errors.
"""

import logging
import os
from typing import List, Optional, Dict, Any

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerateContentResponse
except ImportError:
    genai = None
    GenerateContentResponse = None

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Client for Google's Gemini API.

    Provides interface for semantic code analysis and mutation suggestions
    to be used by higher-level mutators in the HEDGE system.

    When GEMINI_API_KEYS is set (comma-separated list), keys are rotated
    automatically on ResourceExhausted / 429 rate-limit errors.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini client.

        Args:
            api_key: Google API key (if None, tries to get from environment)
            model_name: Name of the Gemini model to use
        """
        if genai is None:
            raise ImportError(
                "google-generativeai package is required. Install with: "
                "pip install google-generativeai"
            )

        # Build ordered list of keys to try
        keys: List[str] = []

        # Prefer explicit multi-key env var
        multi_key_str = os.getenv("GEMINI_API_KEYS", "")
        if multi_key_str:
            keys = [k.strip() for k in multi_key_str.split(",") if k.strip()]

        # Then check single-key env var
        if not keys:
            single = os.getenv("GEMINI_API_KEY", "")
            if single:
                keys = [single.strip()]

        # Explicit argument takes highest priority (prepend if not already present)
        if api_key and api_key not in keys:
            keys.insert(0, api_key)

        if not keys:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY (or GEMINI_API_KEYS for "
                "rotation) environment variable, or pass api_key parameter."
            )

        self._keys = keys
        self._current_key_idx = 0
        self.model_name = model_name

        self._configure_current_key()
        logger.info(
            f"GeminiClient initialized with {len(self._keys)} key(s), model={model_name}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _configure_current_key(self) -> None:
        """(Re)configure genai with the currently active key and rebuild model."""
        self.api_key = self._keys[self._current_key_idx]
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def _rotate_key(self) -> bool:
        """
        Advance to the next available key.

        Returns True if a new key was selected, False if only one key exists.
        """
        if len(self._keys) <= 1:
            return False
        next_idx = (self._current_key_idx + 1) % len(self._keys)
        if next_idx == self._current_key_idx:
            return False  # full circle with single key
        self._current_key_idx = next_idx
        self._configure_current_key()
        logger.info(
            f"[GeminiClient] Rotated to key index {self._current_key_idx} "
            f"({self._current_key_idx + 1}/{len(self._keys)})"
        )
        return True

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        """Return True if the exception looks like a quota / rate-limit error."""
        msg = str(exc).lower()
        return (
            "429" in msg
            or "resourceexhausted" in msg
            or "quota" in msg
            or "rate" in msg
            or "too many requests" in msg
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def complete(self, prompt: str) -> str:
        """
        Complete a text prompt using Gemini.

        Rotates through available API keys on rate-limit errors.

        Args:
            prompt: The prompt to complete

        Returns:
            The completed text response
        """
        last_exc = None
        # Try each key at most once before giving up
        for attempt in range(len(self._keys)):
            try:
                response: GenerateContentResponse = self.model.generate_content(prompt)
                return response.text if response.text else ""
            except Exception as exc:
                if self._is_rate_limit_error(exc):
                    logger.warning(
                        f"[GeminiClient] Rate limit on key {self._current_key_idx} "
                        f"(attempt {attempt + 1}/{len(self._keys)}): {exc}"
                    )
                    last_exc = exc
                    if not self._rotate_key():
                        break  # no more keys to try
                else:
                    logger.error(f"Gemini completion error: {exc}")
                    return ""

        logger.error(
            f"[GeminiClient] All {len(self._keys)} key(s) exhausted. Last error: {last_exc}"
        )
        return ""

    def analyze_code(self, code: str, prompt: str) -> Optional[str]:
        """
        Analyze code using Gemini.

        Args:
            code: Code to analyze
            prompt: Analysis prompt

        Returns:
            Analysis result or None if failed
        """
        full_prompt = f"{prompt}\n\nCode:\n{code}"
        result = self.complete(full_prompt)
        return result if result else None

    def suggest_mutations(self, code: str, context: str = "") -> List[Dict[str, Any]]:
        """
        Suggest code mutations using Gemini.

        Args:
            code: Code to mutate
            context: Additional context about the code

        Returns:
            List of mutation suggestions
        """
        prompt = f"""
        Analyze the following code and suggest optimizations or improvements.
        Focus on performance, readability, and best practices.

        Context: {context}

        Provide suggestions in JSON format:
        {{
            "suggestions": [
                {{
                    "type": "optimization_type",
                    "description": "What to change",
                    "confidence": 0.8,
                    "code_change": "specific change description"
                }}
            ]
        }}
        """

        try:
            result = self.analyze_code(code, prompt)
            if result:
                import json
                parsed = json.loads(result)
                return parsed.get("suggestions", [])
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")

        return []

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        try:
            _ = self.model.generate_content("test")
            return True
        except Exception:
            return False
