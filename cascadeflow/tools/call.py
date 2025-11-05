"""
Tool call parsing for cascadeflow.

Handles parsing tool calls from different provider formats.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from .formats import ToolCallFormat

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """
    Represents a tool call request from the model.

    This is returned by the model when it wants to use a tool.
    """

    id: str  # Unique call ID (for tracking)
    name: str  # Tool name
    arguments: dict[str, Any]  # Tool arguments
    provider_format: ToolCallFormat  # Original format from provider

    @classmethod
    def from_openai(cls, tool_call: dict[str, Any]) -> "ToolCall":
        """
        Parse OpenAI tool call format.

        Format:
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "Paris"}'
            }
        }
        """
        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse OpenAI tool call arguments: {e}")
            arguments = {}

        return cls(
            id=tool_call["id"],
            name=tool_call["function"]["name"],
            arguments=arguments,
            provider_format=ToolCallFormat.OPENAI,
        )

    @classmethod
    def from_anthropic(cls, tool_use: dict[str, Any]) -> "ToolCall":
        """
        Parse Anthropic tool use format.

        Format:
        {
            "type": "tool_use",
            "id": "toolu_123",
            "name": "get_weather",
            "input": {
                "location": "Paris"
            }
        }
        """
        return cls(
            id=tool_use["id"],
            name=tool_use["name"],
            arguments=tool_use.get("input", {}),
            provider_format=ToolCallFormat.ANTHROPIC,
        )

    @classmethod
    def from_ollama(cls, tool_call: dict[str, Any]) -> "ToolCall":
        """Parse Ollama tool call format (same as OpenAI)."""
        return cls.from_openai(tool_call)

    @classmethod
    def from_vllm(cls, tool_call: dict[str, Any]) -> "ToolCall":
        """Parse vLLM tool call format (same as OpenAI)."""
        return cls.from_openai(tool_call)

    @classmethod
    def from_provider(cls, provider: str, tool_call: dict[str, Any]) -> "ToolCall":
        """
        Parse tool call from any provider format.

        Args:
            provider: Provider name
            tool_call: Raw tool call from provider response

        Returns:
            Standardized ToolCall object
        """
        provider_lower = provider.lower()

        if provider_lower in ("openai", "groq", "together", "huggingface"):
            return cls.from_openai(tool_call)
        elif provider_lower == "anthropic":
            return cls.from_anthropic(tool_call)
        elif provider_lower == "ollama":
            return cls.from_ollama(tool_call)
        elif provider_lower == "vllm":
            return cls.from_vllm(tool_call)
        else:
            # Try OpenAI format as default
            try:
                return cls.from_openai(tool_call)
            except Exception as e:
                logger.error(f"Failed to parse tool call from {provider}: {e}")
                raise ValueError(f"Unsupported tool call format from provider '{provider}'")
