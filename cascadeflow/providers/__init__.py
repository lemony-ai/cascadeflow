"""Provider implementations for CascadeFlow."""

from .base import BaseProvider, ModelResponse
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .ollama import OllamaProvider
from .groq import GroqProvider

# Provider registry
PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
}

__all__ = [
    "BaseProvider",
    "ModelResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GroqProvider",
    "PROVIDER_REGISTRY",
]