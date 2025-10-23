"""
Test Retry Logic for OpenAI Provider
====================================

Comprehensive tests to verify retry behavior before rolling out to other providers.

FIXED: Added missing test_streaming_with_retry function.
FIXED: Proper async mocking to avoid coroutine issues.

Run with:
    python tests/test_retry_logic.py
"""

import asyncio
import os

# Ensure we're testing the local code
import sys
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cascadeflow.exceptions import ProviderError

from cascadeflow.providers.base import RetryConfig
from cascadeflow.providers.openai import OpenAIProvider

# ============================================================================
# TEST 1: Normal Operation (No Retries Needed)
# ============================================================================


async def test_normal_operation():
    """Test that normal operations work without retries."""
    print("\n" + "=" * 70)
    print("TEST 1: Normal Operation (No Retries)")
    print("=" * 70)

    # Mock successful response
    mock_response_data = {
        "choices": [
            {
                "message": {"content": "Hello! I'm working correctly."},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }

    provider = OpenAIProvider(api_key="test-key")

    # Create a proper mock response
    mock_response = Mock()
    mock_response.json = Mock(return_value=mock_response_data)
    mock_response.raise_for_status = Mock()

    # Mock the post method to return our response
    with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
        # Make the post method async
        mock_post.return_value = mock_response

        # Make call
        result = await provider.complete(prompt="Hello", model="gpt-4o-mini", max_tokens=20)

        # Verify
        assert result.content == "Hello! I'm working correctly."
        assert mock_post.call_count == 1  # Only called once

        # Check retry metrics
        metrics = provider.get_retry_metrics()
        print(f"✅ Response: {result.content}")
        print(f"✅ API calls: {mock_post.call_count} (expected: 1)")
        print(f"✅ Retry metrics: {metrics}")
        assert metrics["total_attempts"] == 1
        assert metrics["successful"] == 1
        assert metrics["failed"] == 0

        print("✅ PASSED: Normal operation works without retries")


# ============================================================================
# TEST 2: Rate Limit Retry (429 Error)
# ============================================================================


async def test_rate_limit_retry():
    """Test that rate limits trigger retry with backoff."""
    print("\n" + "=" * 70)
    print("TEST 2: Rate Limit Retry (429)")
    print("=" * 70)

    # Mock successful response (after retries)
    success_response_data = {
        "choices": [
            {
                "message": {"content": "Success after retry!"},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
    }

    # Custom retry config with shorter delays for testing
    retry_config = RetryConfig(
        max_attempts=3,
        initial_delay=0.1,  # 100ms for faster testing
        rate_limit_backoff=0.3,  # 300ms for testing
    )

    provider = OpenAIProvider(api_key="test-key", retry_config=retry_config)

    call_count = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count <= 2:
            # First 2 calls: rate limit
            mock_resp = Mock()
            mock_resp.status_code = 429
            mock_resp.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError(
                    "429 Rate Limit", request=Mock(), response=mock_resp
                )
            )
            return mock_resp
        else:
            # Third call: success
            mock_resp = Mock()
            mock_resp.json = Mock(return_value=success_response_data)
            mock_resp.raise_for_status = Mock()
            return mock_resp

    with patch.object(provider.client, "post", side_effect=mock_post_side_effect):
        # Make call (should retry)
        import time

        start_time = time.time()
        result = await provider.complete(
            prompt="Test rate limit", model="gpt-4o-mini", max_tokens=20
        )
        elapsed = time.time() - start_time

        # Verify
        assert result.content == "Success after retry!"
        assert call_count == 3  # Called 3 times (2 failures + 1 success)
        assert elapsed >= 0.6  # Should have waited 2x300ms = 600ms

        # Check retry metrics
        metrics = provider.get_retry_metrics()
        print(f"✅ Response: {result.content}")
        print(f"✅ API calls: {call_count} (expected: 3)")
        print(f"✅ Elapsed time: {elapsed:.2f}s (should be ~0.6s with backoff)")
        print(f"✅ Retry metrics: {metrics}")
        assert metrics["total_attempts"] == 3
        assert metrics["successful"] == 1
        assert metrics["failed"] == 2
        assert "rate_limit" in metrics["retries_by_error"]

        print("✅ PASSED: Rate limit retry works correctly")


# ============================================================================
# TEST 3: Transient Error Recovery (500)
# ============================================================================


async def test_server_error_retry():
    """Test that server errors trigger retry."""
    print("\n" + "=" * 70)
    print("TEST 3: Server Error Retry (500)")
    print("=" * 70)

    success_response_data = {
        "choices": [
            {
                "message": {"content": "Recovered from server error"},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    # Fast retry for testing
    retry_config = RetryConfig(max_attempts=3, initial_delay=0.1, exponential_base=2.0)

    provider = OpenAIProvider(api_key="test-key", retry_config=retry_config)

    call_count = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: 500 error
            mock_resp = Mock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError(
                    "500 Internal Server Error", request=Mock(), response=mock_resp
                )
            )
            return mock_resp
        else:
            # Second call: success
            mock_resp = Mock()
            mock_resp.json = Mock(return_value=success_response_data)
            mock_resp.raise_for_status = Mock()
            return mock_resp

    with patch.object(provider.client, "post", side_effect=mock_post_side_effect):
        # Make call
        result = await provider.complete(
            prompt="Test server error", model="gpt-4o-mini", max_tokens=20
        )

        # Verify
        assert result.content == "Recovered from server error"
        assert call_count == 2  # Failed once, then succeeded

        metrics = provider.get_retry_metrics()
        print(f"✅ Response: {result.content}")
        print(f"✅ API calls: {call_count} (expected: 2)")
        print(f"✅ Retry metrics: {metrics}")
        assert metrics["successful"] == 1
        assert "server_error" in metrics["retries_by_error"]

        print("✅ PASSED: Server error retry works correctly")


# ============================================================================
# TEST 4: Non-Retryable Error (401 Auth)
# ============================================================================


async def test_non_retryable_error():
    """Test that auth errors don't retry."""
    print("\n" + "=" * 70)
    print("TEST 4: Non-Retryable Error (401)")
    print("=" * 70)

    retry_config = RetryConfig(max_attempts=3)
    provider = OpenAIProvider(api_key="bad-key", retry_config=retry_config)

    call_count = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized", request=Mock(), response=mock_resp
            )
        )
        return mock_resp

    with patch.object(provider.client, "post", side_effect=mock_post_side_effect):
        # Make call (should fail immediately)
        try:
            await provider.complete(prompt="Test auth error", model="gpt-4o-mini", max_tokens=20)
            raise AssertionError("Should have raised ProviderError")
        except ProviderError as e:
            assert "Invalid OpenAI API key" in str(e)
            assert call_count == 1  # Only called once, no retries!

            metrics = provider.get_retry_metrics()
            print(f"✅ Error raised: {e}")
            print(f"✅ API calls: {call_count} (expected: 1, no retries)")
            print(f"✅ Retry metrics: {metrics}")
            assert metrics["total_attempts"] == 1
            assert metrics["successful"] == 0
            assert metrics["failed"] == 1

            print("✅ PASSED: Non-retryable errors fail immediately")


# ============================================================================
# TEST 5: Exhausted Retries (All Attempts Fail)
# ============================================================================


async def test_exhausted_retries():
    """Test that all retries fail eventually."""
    print("\n" + "=" * 70)
    print("TEST 5: Exhausted Retries")
    print("=" * 70)

    retry_config = RetryConfig(max_attempts=3, initial_delay=0.05)  # Fast for testing
    provider = OpenAIProvider(api_key="test-key", retry_config=retry_config)

    call_count = 0

    def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        mock_resp = Mock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "503 Service Unavailable", request=Mock(), response=mock_resp
            )
        )
        return mock_resp

    with patch.object(provider.client, "post", side_effect=mock_post_side_effect):
        try:
            await provider.complete(
                prompt="Test exhausted retries", model="gpt-4o-mini", max_tokens=20
            )
            raise AssertionError("Should have raised ProviderError")
        except ProviderError:
            assert call_count == 3  # Tried 3 times (max_attempts)

            metrics = provider.get_retry_metrics()
            print(f"✅ API calls: {call_count} (expected: 3)")
            print(f"✅ Retry metrics: {metrics}")
            assert metrics["total_attempts"] == 3
            assert metrics["successful"] == 0
            assert metrics["failed"] == 3

            print("✅ PASSED: Exhausted retries fail correctly after max attempts")


# ============================================================================
# TEST 6: Streaming (No Retry)
# ============================================================================


async def test_streaming_no_retry():
    """Test that streaming works (but doesn't retry)."""
    print("\n" + "=" * 70)
    print("TEST 6: Streaming (No Retry)")
    print("=" * 70)

    provider = OpenAIProvider(api_key="test-key")

    # Mock streaming response data
    stream_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]

    class MockAsyncContextManager:
        def __init__(self, lines):
            self.lines = lines

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in self.lines:
                yield line

    def mock_stream_side_effect(*args, **kwargs):
        return MockAsyncContextManager(stream_lines)

    with patch.object(provider.client, "stream", side_effect=mock_stream_side_effect):
        # Collect streamed chunks
        chunks = []
        async for chunk in provider.stream(
            prompt="Test streaming", model="gpt-4o-mini", max_tokens=20
        ):
            chunks.append(chunk)

        # Verify
        result = "".join(chunks)
        assert result == "Hello world"

        print(f"✅ Streamed result: {result}")
        print("✅ Note: Streaming does NOT use retry (by design)")
        print("   Reason: Can't 'undo' already-yielded chunks")
        print("   Solution: Use complete() for automatic retry")

        print("✅ PASSED: Streaming works (retry handled externally if needed)")


# ============================================================================
# TEST 6.5: Streaming with Retry (Connection-Level Only)
# ============================================================================


async def test_streaming_with_retry():
    """
    Test that streaming retry works for INITIAL connection failures.

    IMPORTANT: Retry only helps with initial connection errors.
    Once streaming starts, we can't "undo" already-yielded chunks,
    so mid-stream failures cannot be retried.

    This test demonstrates:
    1. ✅ Initial connection retry WORKS (e.g., 503 on first attempt)
    2. ⚠️  Mid-stream failures CANNOT be retried (by design)
    """
    print("\n" + "=" * 70)
    print("TEST 6.5: Streaming with Connection Retry")
    print("=" * 70)

    # Fast retry for testing
    retry_config = RetryConfig(max_attempts=3, initial_delay=0.1)

    provider = OpenAIProvider(api_key="test-key", retry_config=retry_config)

    call_count = 0
    stream_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]

    class MockAsyncContextManager:
        def __init__(self, lines, will_succeed):
            self.lines = lines
            self.will_succeed = will_succeed

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def raise_for_status(self):
            if not self.will_succeed:
                # Simulate 503 error on first attempt
                mock_resp = Mock()
                mock_resp.status_code = 503
                raise httpx.HTTPStatusError(
                    "503 Service Unavailable", request=Mock(), response=mock_resp
                )

        async def aiter_lines(self):
            for line in self.lines:
                yield line

    def mock_stream_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First attempt: connection fails
            return MockAsyncContextManager(stream_lines, will_succeed=False)
        else:
            # Second attempt: succeeds
            return MockAsyncContextManager(stream_lines, will_succeed=True)

    with patch.object(provider.client, "stream", side_effect=mock_stream_side_effect):
        # Collect streamed chunks (should retry connection and succeed)
        chunks = []
        async for chunk in provider.stream(
            prompt="Test streaming retry", model="gpt-4o-mini", max_tokens=20
        ):
            chunks.append(chunk)

        # Verify
        result = "".join(chunks)
        assert result == "Hello world"
        assert call_count == 2  # Failed once, then succeeded

        # Check retry metrics
        metrics = provider.get_retry_metrics()
        print(f"✅ Streamed result: {result}")
        print(f"✅ Connection attempts: {call_count} (expected: 2)")
        print(f"✅ Retry metrics: {metrics}")
        assert metrics["total_attempts"] == 2
        assert metrics["successful"] == 1

        print("\n📝 Note: Retry only helps with INITIAL connection failures.")
        print("   Once streaming starts, chunks are already sent to caller,")
        print("   so mid-stream failures cannot be retried (by design).")
        print("   For guaranteed delivery, use complete() instead of stream().")

        print("\n✅ PASSED: Streaming connection retry works correctly")


# ============================================================================
# TEST 7: Custom Retry Configuration
# ============================================================================


async def test_custom_retry_config():
    """Test custom retry configuration."""
    print("\n" + "=" * 70)
    print("TEST 7: Custom Retry Configuration")
    print("=" * 70)

    # Very aggressive retry
    custom_retry = RetryConfig(
        max_attempts=5,
        initial_delay=0.05,
        max_delay=1.0,
        exponential_base=3.0,
        rate_limit_backoff=0.5,
    )

    provider = OpenAIProvider(api_key="test-key", retry_config=custom_retry)

    print(f"✅ Max attempts: {provider.retry_config.max_attempts}")
    print(f"✅ Initial delay: {provider.retry_config.initial_delay}s")
    print(f"✅ Exponential base: {provider.retry_config.exponential_base}")
    print(f"✅ Rate limit backoff: {provider.retry_config.rate_limit_backoff}s")

    assert provider.retry_config.max_attempts == 5
    assert provider.retry_config.exponential_base == 3.0

    print("✅ PASSED: Custom retry config applied correctly")


# ============================================================================
# RUN ALL TESTS
# ============================================================================


async def run_all_tests():
    """Run all test cases."""
    print("\n" + "=" * 70)
    print("RETRY LOGIC TEST SUITE")
    print("=" * 70)
    print("Testing OpenAI Provider with Retry Logic")
    print("=" * 70)

    tests = [
        ("Normal Operation", test_normal_operation),
        ("Rate Limit Retry", test_rate_limit_retry),
        ("Server Error Retry", test_server_error_retry),
        ("Non-Retryable Error", test_non_retryable_error),
        ("Exhausted Retries", test_exhausted_retries),
        ("Streaming (No Retry)", test_streaming_no_retry),
        ("Streaming with Retry", test_streaming_with_retry),
        ("Custom Retry Config", test_custom_retry_config),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
            import traceback

            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"❌ ERROR in {name}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Ready to roll out to other providers.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Fix issues before rolling out.")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
