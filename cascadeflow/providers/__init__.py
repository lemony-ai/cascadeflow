"""Provider implementations for cascadeflow."""

import logging
from typing import Dict, Optional

from .anthropic import AnthropicProvider
from .base import PROVIDER_CAPABILITIES, BaseProvider, ModelResponse
from .groq import GroqProvider
from .huggingface import HuggingFaceProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .together import TogetherProvider
from .vllm import VLLMProvider

logger = logging.getLogger(__name__)


# Provider registry - simple dict mapping
PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "vllm": VLLMProvider,
    "huggingface": HuggingFaceProvider,
    "together": TogetherProvider,
}


# Optional convenience functions (can be removed if not needed)


def get_provider(provider_name: str) -> Optional[BaseProvider]:
    """
    Get initialized provider instance.

    Convenience function - handles initialization and errors gracefully.

    Args:
        provider_name: Name of provider (e.g., 'openai', 'anthropic')

    Returns:
        Provider instance or None if initialization fails
    """
    if provider_name not in PROVIDER_REGISTRY:
        logger.warning(f"Unknown provider: {provider_name}")
        return None

    try:
        provider_class = PROVIDER_REGISTRY[provider_name]
        provider = provider_class()
        logger.debug(f"Initialized {provider_name} provider")
        return provider
    except Exception as e:
        logger.debug(f"Could not initialize {provider_name}: {e}")
        return None


def get_available_providers() -> dict[str, BaseProvider]:
    """
    Get all providers that can be initialized (have API keys set).

    Useful for auto-discovery of available providers.

    Returns:
        Dict of provider_name -> provider_instance
    """
    providers = {}

    for provider_name in PROVIDER_REGISTRY.keys():
        provider = get_provider(provider_name)
        if provider is not None:
            providers[provider_name] = provider

    if providers:
        logger.info(f"Available providers: {', '.join(providers.keys())}")
    else:
        logger.warning("No providers available. Check API keys in .env")

    return providers


# Exports
__all__ = [
    "BaseProvider",
    "ModelResponse",
    "PROVIDER_CAPABILITIES",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GroqProvider",
    "VLLMProvider",
    "HuggingFaceProvider",
    "TogetherProvider",
    "PROVIDER_REGISTRY",
    "get_provider",
    "get_available_providers",
]
