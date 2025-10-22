"""Test suite for streaming support."""

import pytest

from cascadeflow.streaming import StreamManager


class MockProvider:
    """Mock provider for testing."""

    def __init__(self, chunks=None, should_fail=False):
        self.chunks = chunks or ["Hello", " ", "world", "!"]
        self.should_fail = should_fail

    async def stream(self, model, query, **kwargs):
        """Mock streaming."""
        if self.should_fail:
            raise ValueError("Stream error")

        for chunk in self.chunks:
            yield chunk

    async def complete(self, model, query, **kwargs):
        """Mock complete (fallback)."""
        return {"content": "".join(self.chunks)}


class TestStreamManager:
    """Test stream manager."""

    @pytest.mark.asyncio
    async def test_basic_streaming(self):
        manager = StreamManager()
        provider = MockProvider()

        chunks = []
        async for chunk in manager.stream_from_model("test-model", provider, "test query"):
            chunks.append(chunk)

        assert chunks == ["Hello", " ", "world", "!"]
        assert manager.stats["completed_streams"] == 1

    @pytest.mark.asyncio
    async def test_stream_stats(self):
        manager = StreamManager()
        provider = MockProvider()

        # Stream 1
        async for _ in manager.stream_from_model("test-model", provider, "query1"):
            pass

        # Stream 2
        async for _ in manager.stream_from_model("test-model", provider, "query2"):
            pass

        stats = manager.get_stats()
        assert stats["total_streams"] == 2
        assert stats["completed_streams"] == 2
        assert stats["active_streams"] == 0

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        manager = StreamManager()
        provider = MockProvider(should_fail=True)

        with pytest.raises(ValueError, match="Stream error"):
            async for _ in manager.stream_from_model("test-model", provider, "test query"):
                pass

        stats = manager.get_stats()
        assert stats["failed_streams"] == 1

    @pytest.mark.asyncio
    async def test_stream_with_fallback_no_quality_check(self):
        manager = StreamManager()
        primary = MockProvider(chunks=["Primary", " ", "response"])
        fallback = MockProvider(chunks=["Fallback", " ", "response"])

        chunks = []
        async for chunk in manager.stream_with_fallback(
            "primary-model", primary, "fallback-model", fallback, "test query"
        ):
            chunks.append(chunk)

        # Should use primary (no quality check)
        assert chunks == ["Primary", " ", "response"]

    @pytest.mark.asyncio
    async def test_stream_with_fallback_quality_check(self):
        manager = StreamManager()
        primary = MockProvider(chunks=["Bad"] * 20)
        fallback = MockProvider(chunks=["Good", " ", "response"])

        def quality_checker(text):
            # Return low quality for "Bad"
            return 0.5 if "Bad" in text else 0.9

        chunks = []
        async for chunk in manager.stream_with_fallback(
            "primary-model",
            primary,
            "fallback-model",
            fallback,
            "test query",
            quality_checker=quality_checker,
        ):
            chunks.append(chunk)

        # Should include both primary start + fallback
        assert "Bad" in chunks
        assert "Good" in chunks

    @pytest.mark.asyncio
    async def test_provider_without_stream_method(self):
        """Test fallback to complete() when stream() not available."""
        manager = StreamManager()

        class NoStreamProvider:
            async def complete(self, model, query, **kwargs):
                return {"content": "Complete response"}

        provider = NoStreamProvider()

        chunks = []
        async for chunk in manager.stream_from_model("test-model", provider, "test query"):
            chunks.append(chunk)

        assert chunks == ["Complete response"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
