
import pytest
import anyio
from unittest.mock import MagicMock, AsyncMock, patch
from src.infrastructure.llm.batch_client import BatchLLMClient, BatchRequest, BatchResponse

class TestBatchLLMClient:
    
    @pytest.fixture
    def anyio_backend(self):
        return 'asyncio'

    @pytest.mark.anyio
    async def test_batch_deduplication(self):
        """Test that identical requests are deduplicated."""
        with patch('src.infrastructure.llm.batch_client.OPENAI_AVAILABLE', True), \
             patch('src.infrastructure.llm.batch_client.openai', MagicMock()):
            
            real_client = BatchLLMClient(provider="openai", api_key="test")
            
            requests = [
                BatchRequest(request_id="1", prompt="test", context={}),
                BatchRequest(request_id="2", prompt="test", context={}), # Duplicate
                BatchRequest(request_id="3", prompt="other", context={})
            ]
            
            unique_requests, duplicate_map = real_client._deduplicate_requests(requests)
            
            assert len(unique_requests) == 2
            assert len(duplicate_map) == 2

    @pytest.mark.anyio
    async def test_batch_processing_mocked(self):
        """Test the end-to-end batch processing flow with mocked API calls."""
        with patch('src.infrastructure.llm.batch_client.OPENAI_AVAILABLE', True), \
             patch('src.infrastructure.llm.batch_client.openai', MagicMock()):
            
            client = BatchLLMClient(provider="openai", api_key="test")
            
            mock_response = BatchResponse(
                request_id="placeholder",
                success=True,
                content="mocked response",
                tokens_used=10
            )
            client._make_api_request = AsyncMock(return_value=mock_response)
            
            requests = [
                BatchRequest(request_id="req1", prompt="p1", context={}),
                BatchRequest(request_id="req2", prompt="p2", context={})
            ]
            
            responses = await client.process_batch(requests)
            
            assert len(responses) == 2
            assert responses[0].content == "mocked response"

    @pytest.mark.anyio
    async def test_response_caching(self):
        """Test that responses are cached and reused."""
        with patch('src.infrastructure.llm.batch_client.OPENAI_AVAILABLE', True), \
             patch('src.infrastructure.llm.batch_client.openai', MagicMock()):
            
            client = BatchLLMClient(provider="openai", api_key="test")
            
            mock_response = BatchResponse(
                request_id="req1",
                success=True,
                content="result",
                tokens_used=10
            )
            client._make_api_request = AsyncMock(return_value=mock_response)
            
            req = BatchRequest(request_id="req1", prompt="prompt", context={})
            await client.process_batch([req])
            assert client._make_api_request.call_count == 1
            
            req2 = BatchRequest(request_id="req2", prompt="prompt", context={})
            responses = await client.process_batch([req2])
            
            assert responses[0].cached is True
            assert client._make_api_request.call_count == 1

    @pytest.mark.anyio
    async def test_rate_limiting(self):
        """Test that rate limiter is engaged."""
        with patch('src.infrastructure.llm.batch_client.OPENAI_AVAILABLE', True), \
             patch('src.infrastructure.llm.batch_client.openai', MagicMock()):
            
            client = BatchLLMClient(provider="openai", api_key="test", rate_limit_rpm=1000)
            client._make_api_request = AsyncMock(return_value=BatchResponse("id", True, "ok"))
            
            # This just verifies it doesn't crash and completes
            reqs = [BatchRequest("r1", "p1", {})]
            responses = await client.process_batch(reqs)
            assert len(responses) == 1
