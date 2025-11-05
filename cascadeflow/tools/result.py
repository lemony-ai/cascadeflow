"""
Tool result formatting for cascadeflow.

Handles formatting tool execution results for different providers.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """
    Result from executing a tool.

    This is passed back to the model after tool execution.
    """

    call_id: str  # ID of the tool call
    name: str  # Tool name
    result: Any  # Tool output
    error: Optional[str] = None  # Error message if tool failed
    execution_time_ms: Optional[float] = None  # How long tool took

    @property
    def success(self) -> bool:
        """Whether tool execution succeeded."""
        return self.error is None

    def to_openai_message(self) -> dict[str, Any]:
        """
        Format as OpenAI tool result message.

        Used by: OpenAI, Groq, Together, vLLM

        Format:
        {
            "tool_call_id": "call_123",
            "role": "tool",
            "name": "get_weather",
            "content": "{'temp': 22, 'condition': 'sunny'}"
        }
        """
        content = str(self.result) if not self.error else f"Error: {self.error}"

        return {"tool_call_id": self.call_id, "role": "tool", "name": self.name, "content": content}

    def to_anthropic_message(self) -> dict[str, Any]:
        """
        Format as Anthropic tool result message.

        Key difference: Uses content blocks instead of role="tool"

        Format:
        {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "{'temp': 22, 'condition': 'sunny'}",
                "is_error": false
            }]
        }
        """
        content = str(self.result) if not self.error else f"Error: {self.error}"

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": self.call_id,
                    "content": content,
                    "is_error": self.error is not None,
                }
            ],
        }

    def to_ollama_message(self) -> dict[str, Any]:
        """Format as Ollama tool result (same as OpenAI)."""
        return self.to_openai_message()

    def to_vllm_message(self) -> dict[str, Any]:
        """Format as vLLM tool result (same as OpenAI)."""
        return self.to_openai_message()

    def to_provider_message(self, provider: str) -> dict[str, Any]:
        """
        Format as provider-specific message.

        Args:
            provider: Provider name

        Returns:
            Tool result in provider's expected format
        """
        provider_lower = provider.lower()

        if provider_lower in ("openai", "groq", "together", "huggingface"):
            return self.to_openai_message()
        elif provider_lower == "anthropic":
            return self.to_anthropic_message()
        elif provider_lower == "ollama":
            return self.to_ollama_message()
        elif provider_lower == "vllm":
            return self.to_vllm_message()
        else:
            # Default to OpenAI format
            logger.warning(f"Unknown provider '{provider}', using OpenAI format")
            return self.to_openai_message()
