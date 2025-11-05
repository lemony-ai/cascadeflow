"""
cascadeflow tool calling system.

This is an OPTIONAL feature - existing cascadeflow code works unchanged.

Quick Start:
    from cascadeflow.tools import tool, ToolExecutor

    @tool
    def get_weather(city: str) -> dict:
        '''Get weather for a city.'''
        return {"temp": 22, "condition": "sunny"}

    executor = ToolExecutor([get_weather])
    result = await executor.execute(tool_call)
"""

from .call import ToolCall, ToolCallFormat
from .config import ToolConfig, create_tool_from_function, tool
from .examples import example_calculator, example_get_weather
from .executor import ToolExecutor
from .result import ToolResult

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "ToolConfig",
    "ToolCall",
    "ToolResult",
    "ToolExecutor",
    # Enums
    "ToolCallFormat",
    # Utilities
    "tool",
    "create_tool_from_function",
    # Examples
    "example_calculator",
    "example_get_weather",
]
