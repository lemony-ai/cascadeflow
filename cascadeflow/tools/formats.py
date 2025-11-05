"""
Provider format conversion utilities for cascadeflow tools.

Handles conversion between different provider tool formats.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToolCallFormat(Enum):
    """Tool call format by provider."""

    OPENAI = "openai"  # OpenAI, Groq, Together
    ANTHROPIC = "anthropic"  # Claude
    OLLAMA = "ollama"  # Ollama
    VLLM = "vllm"  # vLLM
    HUGGINGFACE = "huggingface"  # Via Inference Providers


def to_openai_format(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """
    Convert to OpenAI tool format.

    Used by: OpenAI, Groq, Together, vLLM
    """
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


def to_anthropic_format(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """
    Convert to Anthropic tool format.

    Key difference: Uses 'input_schema' instead of 'parameters'
    """
    return {
        "name": name,
        "description": description,
        "input_schema": parameters,  # Anthropic uses input_schema
    }


def to_ollama_format(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Convert to Ollama tool format (same as OpenAI)."""
    return to_openai_format(name, description, parameters)


def to_provider_format(
    provider: str, name: str, description: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    """
    Convert to provider-specific format.

    Args:
        provider: Provider name (openai, anthropic, ollama, groq, together, vllm)
        name: Tool name
        description: Tool description
        parameters: Tool parameters (JSON schema)

    Returns:
        Tool schema in provider's expected format
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "groq", "together", "vllm", "huggingface"):
        return to_openai_format(name, description, parameters)
    elif provider_lower == "anthropic":
        return to_anthropic_format(name, description, parameters)
    elif provider_lower == "ollama":
        return to_ollama_format(name, description, parameters)
    else:
        # Default to OpenAI format (most common)
        logger.warning(f"Unknown provider '{provider}', using OpenAI format")
        return to_openai_format(name, description, parameters)


def get_provider_format_type(provider: str) -> ToolCallFormat:
    """
    Get the format type for a provider.

    Args:
        provider: Provider name

    Returns:
        ToolCallFormat enum value
    """
    provider_lower = provider.lower()

    if provider_lower in ("openai", "groq", "together", "vllm", "huggingface"):
        return ToolCallFormat.OPENAI
    elif provider_lower == "anthropic":
        return ToolCallFormat.ANTHROPIC
    elif provider_lower == "ollama":
        return ToolCallFormat.OLLAMA
    else:
        return ToolCallFormat.OPENAI  # Default
