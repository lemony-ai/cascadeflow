"""
cascadeflow Streaming Module
=============================

Provides real-time streaming for both text and tool-calling cascades.

Modules:
    - base: Text streaming (StreamManager, StreamEvent)
    - tools: Tool streaming (ToolStreamManager, ToolStreamEvent)
    - utils: Shared utilities (ProgressiveJSONParser, etc.)

Usage:
    # Text streaming
    from cascadeflow.streaming import StreamManager, StreamEvent, StreamEventType

    manager = StreamManager(cascade)
    async for event in manager.stream(query):
        if event.type == StreamEventType.CHUNK:
            print(event.content, end='')

    # Tool streaming
    from cascadeflow.streaming import ToolStreamManager, ToolStreamEvent

    tool_manager = ToolStreamManager(cascade)
    async for event in tool_manager.stream(query, tools=tools):
        if event.type == ToolStreamEventType.TOOL_CALL_START:
            print(f"[Calling: {event.tool_call['name']}]")
"""

# Text streaming
from .base import (
    StreamEvent,
    StreamEventType,
    StreamManager,
)

# Tool streaming
from .tools import (
    ToolStreamEvent,
    ToolStreamEventType,
    ToolStreamManager,
)

# Utilities
from .utils import (
    JSONParseState,
    ProgressiveJSONParser,
)

__all__ = [
    # Text streaming
    "StreamEventType",
    "StreamEvent",
    "StreamManager",
    # Tool streaming
    "ToolStreamEventType",
    "ToolStreamEvent",
    "ToolStreamManager",
    # Utilities
    "ProgressiveJSONParser",
    "JSONParseState",
]

__version__ = "2.0.0"
