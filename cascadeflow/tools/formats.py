"""
Provider format conversion utilities for cascadeflow tools.

Handles conversion between different provider tool formats.
"""

import logging
from enum import Enum
from typing import Any, Optional

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


def normalize_tools(
    tools: Optional[list[dict[str, Any]]],
) -> Optional[list[dict[str, Any]]]:
    """
    Normalize tool schemas to universal format.

    Supports:
    - Universal format: {"name","description","parameters"}
    - OpenAI format: {"type":"function","function":{...}}
    - Anthropic format: {"name","description","input_schema"}
    """
    if not tools:
        return tools

    normalized: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            logger.warning("Skipping non-dict tool schema: %s", tool)
            continue

        if "name" in tool and "parameters" in tool:
            normalized.append(tool)
            continue

        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            func = tool["function"]
            name = func.get("name") or tool.get("name")
            if not name:
                logger.warning("Skipping tool without name in OpenAI format: %s", tool)
                continue
            normalized.append(
                {
                    "name": name,
                    "description": func.get("description") or tool.get("description") or "",
                    "parameters": func.get("parameters") or func.get("input_schema") or {},
                }
            )
            continue

        if "input_schema" in tool:
            name = tool.get("name")
            if not name:
                logger.warning("Skipping tool without name in Anthropic format: %s", tool)
                continue
            normalized.append(
                {
                    "name": name,
                    "description": tool.get("description") or "",
                    "parameters": tool.get("input_schema") or {},
                }
            )
            continue

        logger.warning("Unrecognized tool schema format, keeping as-is: %s", tool)
        normalized.append(tool)

    return normalized


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
