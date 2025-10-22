"""
Visual Consumer for Streaming Events
====================================

Fixed to work with the agent.py StreamManager integration.

This module makes streaming "just work" - chunks print automatically
with optional visual indicators (🟢 → ⤴ → ✅).
"""

import asyncio
import sys
from typing import Any

from cascadeflow.streaming import StreamEventType


class VisualIndicator:
    """
    Terminal visual indicator for streaming status.

    Shows:
    - 🟢 Green dot: actively streaming
    - ⤴ Blue arrow: cascading to better model
    - ✅ Green check: complete
    - ❌ Red X: error
    """

    def __init__(self, enabled: bool = True):
        """Initialize visual indicator (auto-detects TTY)."""
        self.enabled = enabled and sys.stdout.isatty()

    def show_streaming(self):
        """Show streaming indicator (🟢)."""
        if not self.enabled:
            return
        sys.stdout.write("\r\033[32m●\033[0m ")
        sys.stdout.flush()

    def show_cascading(self):
        """Show cascade indicator (⤴)."""
        if not self.enabled:
            return
        sys.stdout.write("\r\033[34m⤴\033[0m ")
        sys.stdout.flush()

    def show_complete(self, success: bool = True):
        """Show completion indicator (✅ or ❌)."""
        if not self.enabled:
            return

        if success:
            sys.stdout.write("\r\033[32m✓\033[0m ")
        else:
            sys.stdout.write("\r\033[31m✗\033[0m ")
        sys.stdout.flush()

    def clear(self):
        """Clear indicator."""
        if not self.enabled:
            return
        sys.stdout.write("\r  ")
        sys.stdout.flush()


class TerminalVisualConsumer:
    """
    Consumes streaming events and displays them with visual feedback.

    This class handles all the complexity of:
    - Printing chunks as they arrive (with flush=True)
    - Showing visual indicators
    - Handling cascade switches
    - Collecting final result

    Works with agent.py's StreamManager.

    Example:
        >>> consumer = TerminalVisualConsumer(enable_visual=True)
        >>> result = await consumer.consume(
        ...     streaming_manager=agent.streaming_manager,
        ...     query="What is Python?",
        ...     max_tokens=100
        ... )
        >>> # Chunks were automatically printed!
    """

    def __init__(self, enable_visual: bool = True, verbose: bool = False):
        """
        Initialize consumer.

        Args:
            enable_visual: Show visual indicators (default: True)
            verbose: Show detailed messages (default: False)
        """
        self.visual = VisualIndicator(enabled=enable_visual)
        self.verbose = verbose

    async def consume(
        self,
        streaming_manager,  # StreamManager instance from agent
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Consume streaming events and display output.

        This method automatically:
        1. Prints chunks as they arrive (with flush=True)
        2. Shows visual indicators for status
        3. Handles cascade switches
        4. Collects and returns final result

        Args:
            streaming_manager: StreamManager instance from agent
            query: User query
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments

        Returns:
            Result dictionary with content and metadata

        Raises:
            Exception: If streaming fails
        """
        chunks = []
        result_data = None

        try:
            # Show initial streaming indicator
            self.visual.show_streaming()

            # Consume all events from StreamManager
            async for event in streaming_manager.stream(
                query=query, max_tokens=max_tokens, temperature=temperature, **kwargs
            ):

                if event.type == StreamEventType.CHUNK:
                    # CRITICAL: Print chunk immediately with flush=True
                    # This is why chunks appear in real-time!
                    print(event.content, end="", flush=True)
                    chunks.append(event.content)

                elif event.type == StreamEventType.SWITCH:
                    # Show cascade indicator
                    self.visual.show_cascading()

                    # Brief pause for visual effect
                    await asyncio.sleep(0.2)

                    # Show cascade message if verbose
                    if self.verbose:
                        print(f"\n\n⤴ {event.content}\n")

                    # Back to streaming indicator
                    self.visual.show_streaming()

                elif event.type == StreamEventType.COMPLETE:
                    # Show completion indicator
                    self.visual.show_complete(success=True)

                    # Get result from metadata
                    result_data = event.metadata.get("result")

                    # Brief pause before clearing
                    await asyncio.sleep(0.3)
                    self.visual.clear()

                elif event.type == StreamEventType.ERROR:
                    # Show error indicator
                    self.visual.show_complete(success=False)
                    await asyncio.sleep(0.3)
                    self.visual.clear()

                    # Raise the error
                    raise Exception(event.content)

            # Ensure we have a result
            if not result_data:
                # Construct result from chunks if no result in metadata
                result_data = {
                    "content": "".join(chunks),
                    "model_used": "unknown",
                    "total_cost": 0.0,
                    "latency_ms": 0.0,
                    "draft_accepted": False,
                }

            # Ensure result_data is a dict (might be an object)
            if not isinstance(result_data, dict):
                # Convert object to dict
                result_data = {
                    "content": getattr(result_data, "content", "".join(chunks)),
                    "model_used": getattr(result_data, "model_used", "unknown"),
                    "total_cost": getattr(result_data, "total_cost", 0.0),
                    "latency_ms": getattr(result_data, "latency_ms", 0.0),
                    "draft_accepted": getattr(result_data, "draft_accepted", False),
                    "draft_model": getattr(result_data, "drafter_model", None),
                    "verifier_model": getattr(result_data, "verifier_model", None),
                    "draft_confidence": getattr(result_data, "draft_confidence", None),
                    "verifier_confidence": getattr(result_data, "verifier_confidence", None),
                    "speedup": getattr(result_data, "speedup", 1.0),
                    "reason": getattr(result_data, "metadata", {}).get("reason", "cascade"),
                }

            return result_data

        except Exception:
            # Clean up on error
            self.visual.show_complete(success=False)
            await asyncio.sleep(0.3)
            self.visual.clear()
            raise

        finally:
            # Always clear indicator
            self.visual.clear()


class SilentConsumer:
    """
    Consumes streaming events without displaying them.

    Useful for testing or when you want to collect the result
    without printing to stdout.

    Example:
        >>> consumer = SilentConsumer()
        >>> result = await consumer.consume(
        ...     streaming_manager=agent.streaming_manager,
        ...     query="What is Python?"
        ... )
        >>> # No output was printed
        >>> print(result['content'])
    """

    def __init__(self, verbose: bool = False):
        """Initialize silent consumer."""
        self.verbose = verbose

    async def consume(
        self,
        streaming_manager,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Consume streaming events silently.

        Args:
            streaming_manager: StreamManager instance
            query: User query
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional arguments

        Returns:
            Result dictionary
        """
        chunks = []
        result_data = None

        async for event in streaming_manager.stream(
            query=query, max_tokens=max_tokens, temperature=temperature, **kwargs
        ):
            if event.type == StreamEventType.CHUNK:
                chunks.append(event.content)
            elif event.type == StreamEventType.COMPLETE:
                result_data = event.metadata.get("result")
            elif event.type == StreamEventType.ERROR:
                raise Exception(event.content)

        # Ensure we have a result
        if not result_data:
            result_data = {
                "content": "".join(chunks),
                "model_used": "unknown",
                "total_cost": 0.0,
                "latency_ms": 0.0,
                "draft_accepted": False,
            }

        # Convert object to dict if needed
        if not isinstance(result_data, dict):
            result_data = {
                "content": getattr(result_data, "content", "".join(chunks)),
                "model_used": getattr(result_data, "model_used", "unknown"),
                "total_cost": getattr(result_data, "total_cost", 0.0),
                "latency_ms": getattr(result_data, "latency_ms", 0.0),
                "draft_accepted": getattr(result_data, "draft_accepted", False),
                "draft_model": getattr(result_data, "drafter_model", None),
                "verifier_model": getattr(result_data, "verifier_model", None),
            }

        return result_data
