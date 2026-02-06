"""
LLM Client - Unified interface for LLM providers.

Supports:
- OpenAI (GPT-4o and variants)
- Google Gemini

Features:
- Automatic retry with exponential backoff
- Rate limit handling
- Consistent error handling
"""

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base class for LLM clients."""

    @abstractmethod
    def complete(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Generate a completion for the given prompt."""


class RetryConfig:
    """Configuration for retry behavior."""

    __slots__ = ("max_retries", "base_delay", "max_delay", "jitter")

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        jitter: float = 1.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        return delay + (random.random() * self.jitter)


class OpenAIClient(LLMClient):
    """OpenAI API client with retry support."""

    def __init__(
        self, api_key: str, model: str = "gpt-4o", retry_config: Optional[RetryConfig] = None
    ):
        try:
            from openai import OpenAI

            self.client = OpenAI(api_key=api_key)
            self.api_key = api_key
            self.model = model
            self.model_name = model
            self.retry_config = retry_config or RetryConfig()
        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            raise

    def complete(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        for attempt in range(self.retry_config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert code optimization assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    stop=stop,
                    temperature=0.2,
                )
                result = response.choices[0].message.content or ""
                if result:
                    logger.info(f"OpenAI completion successful ({len(result)} chars)")
                return result

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "429" in error_str or "rate" in error_str or "quota" in error_str

                if is_rate_limit and attempt < self.retry_config.max_retries - 1:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"OpenAI rate limit (attempt {attempt+1}). Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue

                logger.error(f"OpenAI API call failed: {e}")
                return ""

        return ""


class GeminiClient(LLMClient):
    """Google Gemini API client with retry support."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        retry_config: Optional[RetryConfig] = None,
    ):
        try:
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            self.api_key = api_key
            self.model = genai.GenerativeModel(model)
            self.model_name = model
            self.retry_config = retry_config or RetryConfig()
        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            raise

    def complete(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        for attempt in range(self.retry_config.max_retries):
            try:
                import google.generativeai as genai

                generation_config = None
                if stop:
                    generation_config = genai.types.GenerationConfig(stop_sequences=stop)

                response = self.model.generate_content(prompt, generation_config=generation_config)
                # Safely handle response text extraction
                if (
                    response.candidates
                    and response.candidates[0].content
                    and response.candidates[0].content.parts
                ):
                    result = response.text
                    logger.info(f"Gemini completion successful ({len(result)} chars)")
                    return result
                return ""

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str or "quota" in error_str or "resource" in error_str
                )

                if is_rate_limit and attempt < self.retry_config.max_retries - 1:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"Gemini rate limit (attempt {attempt+1}). Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue

                logger.error(f"Gemini API call failed: {e}")
                return ""

        return ""


def create_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None,
) -> LLMClient:
    """
    Factory function to create LLM clients.

    Args:
        provider: "openai" or "gemini" (loads from config if None)
        api_key: API key (loads from environment if None)
        model: Optional model name override (loads from config if None)
        retry_config: Optional retry configuration

    Returns:
        Configured LLM client
    """
    # Load defaults from config if needed
    if provider is None or model is None:
        try:
            from src.utils.config_manager import get_llm_config

            llm_cfg = get_llm_config()
            provider = provider or llm_cfg["provider"]
            model = model or llm_cfg["model"]
        except ImportError:
            # Fallback if config utility is missing
            provider = provider or "gemini"
            model = model or ("gemini-2.5-flash" if provider == "gemini" else "gpt-4o")

    # Get API key from environment if not provided
    if api_key is None:
        api_key = os.getenv(f"{provider.upper()}_API_KEY")

    if not api_key:
        raise ValueError(
            f"API key not found for {provider}. Set {provider.upper()}_API_KEY environment variable."
        )

    provider_lower = provider.lower()

    if provider_lower == "openai":
        return OpenAIClient(api_key, model or "gpt-4o", retry_config)
    elif provider_lower == "gemini":
        return GeminiClient(api_key, model or "gemini-2.5-flash", retry_config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Use 'openai' or 'gemini'.")
