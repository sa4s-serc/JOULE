"""
Batch LLM Client - High-Performance Semantic Mutation Processing

This module provides advanced batch processing for LLM-based semantic mutations:
- Concurrent API requests with intelligent batching
- Request deduplication and caching
- Adaptive rate limiting and retry logic
- Cost optimization and usage tracking
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from threading import Lock, Semaphore
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp: Any = None  # type: ignore

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai: Any = None  # type: ignore

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai: Any = None  # type: ignore

from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """A single request in a batch."""

    request_id: str
    prompt: str
    context: Dict[str, Any]
    priority: float = 1.0
    max_tokens: int = 2000
    temperature: float = 0.1

    def get_cache_key(self) -> str:
        """Generate cache key for deduplication."""
        content = f"{self.prompt}:{self.max_tokens}:{self.temperature}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class BatchResponse:
    """Response for a batch request."""

    request_id: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    latency_ms: float = 0.0
    cached: bool = False


@dataclass
class BatchStats:
    """Statistics for batch processing."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cached_requests: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    average_latency_ms: float = 0.0
    batch_efficiency: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successful_requests / max(1, self.total_requests)

    @property
    def cache_hit_rate(self) -> float:
        return self.cached_requests / max(1, self.total_requests)


class ResponseCache:
    """LRU cache for LLM responses with TTL support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[str, float]] = {}  # key -> (response, timestamp)
        self.access_order: List[str] = []
        self.lock = Lock()

    def get(self, key: str) -> Optional[str]:
        """Get cached response if valid."""
        with self.lock:
            if key not in self.cache:
                return None

            response, timestamp = self.cache[key]

            # Check TTL
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                return None

            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

            return response

    def put(self, key: str, response: str):
        """Cache a response."""
        with self.lock:
            # Remove oldest if at capacity
            while len(self.cache) >= self.max_size and self.access_order:
                oldest_key = self.access_order.pop(0)
                if oldest_key in self.cache:
                    del self.cache[oldest_key]

            self.cache[key] = (response, time.time())
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)

    def clear(self):
        """Clear the cache."""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_rate": 0.0,  # Would need to track hits/misses
                "ttl_seconds": self.ttl_seconds,
            }


class RateLimiter:
    """Adaptive rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 60, tokens_per_minute: int = 90000):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_semaphore = Semaphore(requests_per_minute)
        self.token_semaphore = Semaphore(tokens_per_minute)
        self.request_times: List[float] = []
        self.token_usage: List[Tuple[float, int]] = []  # (timestamp, tokens)
        self.lock = Lock()

    async def acquire(self, estimated_tokens: int = 1000):
        """Acquire rate limit permits."""
        current_time = time.time()

        # Clean old entries
        with self.lock:
            self.request_times = [t for t in self.request_times if current_time - t < 60]
            self.token_usage = [
                (t, tokens) for t, tokens in self.token_usage if current_time - t < 60
            ]

        # Check if we need to wait
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (current_time - self.request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        current_token_usage = sum(tokens for _, tokens in self.token_usage)
        if current_token_usage + estimated_tokens > self.tokens_per_minute:
            # Find when we can make the request
            sorted_usage = sorted(self.token_usage, key=lambda x: x[0])
            for timestamp, tokens in sorted_usage:
                if current_token_usage - tokens + estimated_tokens <= self.tokens_per_minute:
                    wait_time = 60 - (current_time - timestamp)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    break

        # Record the request
        with self.lock:
            self.request_times.append(current_time)
            self.token_usage.append((current_time, estimated_tokens))


class BatchLLMClient:
    """
    High-performance batch LLM client with advanced optimization features.

    Features:
    - Concurrent request processing with intelligent batching
    - Request deduplication and response caching
    - Adaptive rate limiting and retry logic
    - Cost optimization and usage tracking
    - Multiple provider support (OpenAI, Anthropic, etc.)
    """

    # Type hints for attributes
    provider: str
    model: str
    api_key: Optional[str]
    max_concurrent_requests: int
    cache: ResponseCache
    rate_limiter: RateLimiter
    stats: BatchStats
    client: Any  # Union[openai.AsyncOpenAI, genai.GenerativeModel]
    request_semaphore: Semaphore

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        max_concurrent_requests: int = 10,
        cache_size: int = 1000,
        rate_limit_rpm: int = 60,
        rate_limit_tpm: int = 90000,
    ):
        if not OPENAI_AVAILABLE and provider == "openai":
            raise ImportError("OpenAI library not available. Install with: pip install openai")

        if not GEMINI_AVAILABLE and provider == "gemini":
            raise ImportError(
                "Google Generative AI library not available. Install with: pip install google-generativeai"
            )

        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.max_concurrent_requests = max_concurrent_requests

        # Initialize components
        self.cache = ResponseCache(max_size=cache_size)
        self.rate_limiter = RateLimiter(rate_limit_rpm, rate_limit_tpm)
        self.stats = BatchStats()

        # Initialize provider client
        if provider == "openai" and OPENAI_AVAILABLE:
            self.client = openai.AsyncOpenAI(api_key=api_key)
        elif provider == "gemini" and GEMINI_AVAILABLE:
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(model)
        else:
            self.client = None
            if provider == "openai":
                raise ValueError("OpenAI not available")
            elif provider == "gemini":
                raise ValueError("Gemini not available")
            else:
                raise ValueError(f"Unsupported provider: {provider}")

        # Semaphore for concurrent requests
        self.request_semaphore = Semaphore(max_concurrent_requests)

    async def process_batch(
        self,
        requests: List[BatchRequest],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[BatchResponse]:
        """
        Process a batch of requests with optimization.

        Args:
            requests: List of batch requests
            progress_callback: Optional callback for progress updates

        Returns:
            List of batch responses
        """
        start_time = time.time()

        # Deduplicate requests
        deduplicated_requests, duplicate_map = self._deduplicate_requests(requests)

        logger.info(f"Processing {len(requests)} requests ({len(deduplicated_requests)} unique)")

        # Process unique requests
        unique_responses = await self._process_unique_requests(
            deduplicated_requests, progress_callback
        )

        # Map responses back to original requests
        all_responses = self._map_responses_to_original(unique_responses, duplicate_map, requests)

        # Update statistics
        self._update_stats(all_responses, time.time() - start_time)

        return all_responses

    def _deduplicate_requests(
        self, requests: List[BatchRequest]
    ) -> Tuple[List[BatchRequest], Dict[str, List[str]]]:
        """Deduplicate requests and create mapping."""
        unique_requests = []
        duplicate_map: Dict[str, List[str]] = {}  # cache_key -> list of request_ids
        seen_keys = set()

        for request in requests:
            cache_key = request.get_cache_key()

            if cache_key not in duplicate_map:
                duplicate_map[cache_key] = []
            duplicate_map[cache_key].append(request.request_id)

            if cache_key not in seen_keys:
                unique_requests.append(request)
                seen_keys.add(cache_key)

        return unique_requests, duplicate_map

    async def _process_unique_requests(
        self,
        requests: List[BatchRequest],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, BatchResponse]:
        """Process unique requests concurrently."""
        responses = {}
        completed = 0

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def process_single_request(request: BatchRequest) -> Tuple[str, BatchResponse]:
            nonlocal completed

            async with semaphore:
                response = await self._process_single_request(request)
                completed += 1

                if progress_callback:
                    progress_callback(completed, len(requests))

                return request.get_cache_key(), response

        # Execute all requests concurrently
        tasks = [process_single_request(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Request failed: {result}")
            elif isinstance(result, tuple) and len(result) == 2:
                cache_key, response = result
                responses[cache_key] = response

        return responses

    async def _process_single_request(self, request: BatchRequest) -> BatchResponse:
        """Process a single request with caching and rate limiting."""
        start_time = time.time()

        # Check cache first
        cache_key = request.get_cache_key()
        cached_response = self.cache.get(cache_key)
        if cached_response:
            return BatchResponse(
                request_id=request.request_id,
                success=True,
                content=cached_response,
                latency_ms=(time.time() - start_time) * 1000,
                cached=True,
            )

        # Apply rate limiting
        await self.rate_limiter.acquire(request.max_tokens)

        # Make API request with retry logic
        try:
            response = await self._make_api_request(request)

            # Cache successful response
            if response.success and response.content:
                self.cache.put(cache_key, response.content)

            response.latency_ms = (time.time() - start_time) * 1000
            return response

        except Exception as e:
            logger.error(f"API request failed: {e}")
            return BatchResponse(
                request_id=request.request_id,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),  # Generic exception for now
    )
    async def _make_api_request(self, request: BatchRequest) -> BatchResponse:
        """Make the actual API request with retry logic."""
        try:
            if self.provider == "openai" and OPENAI_AVAILABLE and self.client:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": request.prompt}],
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )

                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens if response.usage else 0

                return BatchResponse(
                    request_id=request.request_id,
                    success=True,
                    content=content,
                    tokens_used=tokens_used,
                )
            elif self.provider == "gemini" and GEMINI_AVAILABLE and self.client:
                # Use generate_content_async for Gemini
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=request.max_tokens, temperature=request.temperature
                )

                response = await self.client.generate_content_async(
                    request.prompt, generation_config=generation_config
                )

                # Extract content safely
                content = ""
                if (
                    response.candidates
                    and response.candidates[0].content
                    and response.candidates[0].content.parts
                ):
                    content = response.text

                # Gemini async response doesn't always provide usage immediately in some versions
                # but we can try to estimate or get it if available
                tokens_used = 0
                try:
                    # In newer versions of the SDK, usage_metadata might be available
                    if hasattr(response, "usage_metadata"):
                        tokens_used = response.usage_metadata.total_token_count
                except Exception:
                    pass

                return BatchResponse(
                    request_id=request.request_id,
                    success=True,
                    content=content,
                    tokens_used=tokens_used,
                )
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        except Exception as e:
            return BatchResponse(request_id=request.request_id, success=False, error=str(e))

    def _map_responses_to_original(
        self,
        unique_responses: Dict[str, BatchResponse],
        duplicate_map: Dict[str, List[str]],
        original_requests: List[BatchRequest],
    ) -> List[BatchResponse]:
        """Map unique responses back to all original requests."""
        response_map = {}

        # Create mapping from request_id to response
        for cache_key, response in unique_responses.items():
            request_ids = duplicate_map.get(cache_key, [])
            for request_id in request_ids:
                # Create a copy of the response with the correct request_id
                mapped_response = BatchResponse(
                    request_id=request_id,
                    success=response.success,
                    content=response.content,
                    error=response.error,
                    tokens_used=response.tokens_used,
                    latency_ms=response.latency_ms,
                    cached=response.cached,
                )
                response_map[request_id] = mapped_response

        # Return responses in original order
        return [response_map.get(req.request_id) for req in original_requests]  # type: ignore

    def _update_stats(self, responses: List[BatchResponse], total_time: float):
        """Update batch processing statistics."""
        self.stats.total_requests += len(responses)

        for response in responses:
            if response:
                if response.success:
                    self.stats.successful_requests += 1
                else:
                    self.stats.failed_requests += 1

                if response.cached:
                    self.stats.cached_requests += 1

                self.stats.total_tokens_used += response.tokens_used

                # Estimate cost (OpenAI GPT-4 pricing as example)
                if response.tokens_used > 0:
                    cost_per_token = 0.00003  # $0.03 per 1K tokens
                    self.stats.total_cost_usd += response.tokens_used * cost_per_token

        # Calculate average latency
        valid_latencies = [r.latency_ms for r in responses if r and r.latency_ms > 0]
        if valid_latencies:
            self.stats.average_latency_ms = sum(valid_latencies) / len(valid_latencies)

        # Calculate batch efficiency (requests per second)
        if total_time > 0:
            self.stats.batch_efficiency = len(responses) / total_time

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive batch processing statistics."""
        cache_stats = self.cache.get_stats()

        return {
            "batch_stats": {
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "cached_requests": self.stats.cached_requests,
                "success_rate": self.stats.success_rate,
                "cache_hit_rate": self.stats.cache_hit_rate,
                "total_tokens_used": self.stats.total_tokens_used,
                "total_cost_usd": self.stats.total_cost_usd,
                "average_latency_ms": self.stats.average_latency_ms,
                "batch_efficiency": self.stats.batch_efficiency,
            },
            "cache_stats": cache_stats,
            "config": {
                "provider": self.provider,
                "model": self.model,
                "max_concurrent_requests": self.max_concurrent_requests,
                "rate_limit_rpm": self.rate_limiter.requests_per_minute,
                "rate_limit_tpm": self.rate_limiter.tokens_per_minute,
            },
        }

    def reset_stats(self):
        """Reset statistics."""
        self.stats = BatchStats()
        self.cache.clear()


# Convenience function for creating batch clients
def create_batch_llm_client(
    provider: str = "openai", model: str = "gpt-4", api_key: Optional[str] = None, **kwargs
) -> Optional[BatchLLMClient]:
    """Create a batch LLM client with optimal defaults."""
    try:
        return BatchLLMClient(provider=provider, model=model, api_key=api_key, **kwargs)
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not create batch LLM client: {e}")
        return None
