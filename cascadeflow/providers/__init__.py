"""Provider implementations for CascadeFlow."""

from .base import BaseProvider, ModelResponse
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .groq import GroqProvider
from .ollama import OllamaProvider
from .vllm import VLLMProvider
from .huggingface import HuggingFaceProvider
from .together import TogetherProvider  # NEW

# Provider registry
PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "vllm": VLLMProvider,
    "huggingface": HuggingFaceProvider,
    "together": TogetherProvider,  # NEW
}

__all__ = [
    "BaseProvider",
    "ModelResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GroqProvider",
    "VLLMProvider",
    "HuggingFaceProvider",
    "TogetherProvider",  # NEW
    "PROVIDER_REGISTRY",
]