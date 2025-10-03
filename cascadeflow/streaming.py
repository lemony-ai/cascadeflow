"""
Streaming response support.

Provides:
- Async streaming for responses
- Chunk-by-chunk delivery
- Integration with providers
"""

from typing import AsyncGenerator, Optional, Dict, Any
import logging
import asyncio

logger = logging.getLogger(__name__)


class StreamingResponse:
    """
    Async streaming response wrapper.

    Example:
        >>> async for chunk in stream:
        ...     print(chunk, end="", flush=True)
    """

    def __init__(
            self,
            model: str,
            provider: str,
            metadata: Optional[Dict[str, Any]] = None
    ):
        self.model = model
        self.provider = provider
        self.metadata = metadata or {}
        self.full_text = ""
        self.chunks: list = []

    async def __aiter__(self) -> AsyncGenerator[str, None]:
        """Async iterator for streaming chunks."""
        raise NotImplementedError("Subclass must implement __aiter__")


class StreamManager:
    """
    Manages streaming for cascade operations.

    Handles:
    - Streaming from primary model
    - Switching streams during cascade
    - Buffering for speculative cascades
    """

    def __init__(self):
        self.active_streams: Dict[str, StreamingResponse] = {}
        self.stats = {
            "total_streams": 0,
            "active_streams": 0,
            "completed_streams": 0,
            "failed_streams": 0
        }

    async def stream_from_model(
            self,
            model: str,
            provider: Any,
            query: str,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Start streaming from a model.

        Args:
            model: Model name
            provider: Provider instance
            query: User query
            **kwargs: Additional parameters

        Yields:
            Response chunks as they arrive
        """
        self.stats["total_streams"] += 1
        self.stats["active_streams"] += 1

        stream_id = f"{model}_{id(query)}"

        try:
            logger.debug(f"Starting stream from {model}")

            # Provider-specific streaming implementation
            if hasattr(provider, 'stream'):
                async for chunk in provider.stream(model, query, **kwargs):
                    yield chunk
            else:
                # Fallback: complete then yield
                result = await provider.complete(model, query, **kwargs)
                yield result.get('content', '')

            self.stats["completed_streams"] += 1
            logger.debug(f"Stream from {model} completed")

        except Exception as e:
            self.stats["failed_streams"] += 1
            logger.error(f"Stream error from {model}: {e}")
            raise

        finally:
            self.stats["active_streams"] -= 1
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]

    async def stream_with_fallback(
            self,
            primary_model: str,
            primary_provider: Any,
            fallback_model: Optional[str],
            fallback_provider: Optional[Any],
            query: str,
            quality_checker: Optional[callable] = None,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream with quality checking and potential fallback.

        For speculative cascading:
        - Stream from drafter
        - Check quality in background
        - Switch to verifier if needed

        Args:
            primary_model: Primary model to stream from
            primary_provider: Primary provider instance
            fallback_model: Fallback model (optional)
            fallback_provider: Fallback provider (optional)
            query: User query
            quality_checker: Function to check quality (optional)
            **kwargs: Additional parameters

        Yields:
            Response chunks
        """
        buffer = []
        should_fallback = False

        logger.debug(f"Starting stream with fallback: {primary_model}")

        async for chunk in self.stream_from_model(
                primary_model,
                primary_provider,
                query,
                **kwargs
        ):
            buffer.append(chunk)
            yield chunk

            # Periodic quality check
            if quality_checker and len(buffer) % 10 == 0:
                full_text = "".join(buffer)
                quality = quality_checker(full_text)

                if quality < 0.7 and fallback_model:
                    logger.info(
                        f"Quality low ({quality:.2f}), "
                        f"switching to {fallback_model}"
                    )
                    should_fallback = True
                    break

        # If fallback needed, stream from fallback
        if should_fallback and fallback_model and fallback_provider:
            logger.info(f"Streaming from fallback: {fallback_model}")
            async for chunk in self.stream_from_model(
                    fallback_model,
                    fallback_provider,
                    query,
                    **kwargs
            ):
                yield chunk

    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        return self.stats.copy()