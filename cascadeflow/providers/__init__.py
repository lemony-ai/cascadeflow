"""Provider implementations for cascadeflow.

Provider classes are lazy-loaded on first access to keep
``import cascadeflow`` fast. ``BaseProvider``, ``ModelResponse``,
and ``PROVIDER_CAPABILITIES`` are always available eagerly.
"""

import logging
from typing import Optional

from .base import PROVIDER_CAPABILITIES, BaseProvider, ModelResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy provider class loading via PEP 562 __getattr__
# ---------------------------------------------------------------------------

_LAZY_PROVIDERS: dict[str, str] = {
    "AnthropicProvider": ".anthropic",
    "DeepSeekProvider": ".deepseek",
    "GroqProvider": ".groq",
    "HuggingFaceProvider": ".huggingface",
    "OllamaProvider": ".ollama",
    "OpenAIProvider": ".openai",
    "OpenRouterProvider": ".openrouter",
    "TogetherProvider": ".together",
    "VLLMProvider": ".vllm",
}


def __getattr__(name: str):
    if name in _LAZY_PROVIDERS:
        import importlib

        module = importlib.import_module(_LAZY_PROVIDERS[name], __package__)
        cls = getattr(module, name)
        globals()[name] = cls
        return cls

    if name == "PROVIDER_REGISTRY":
        registry = _build_provider_registry()
        globals()["PROVIDER_REGISTRY"] = registry
        return registry

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return list(__all__) + list(_LAZY_PROVIDERS)


def _build_provider_registry() -> dict:
    """Build the provider registry, importing each provider class lazily."""
    import importlib

    registry = {}
    _name_to_key = {
        "OpenAIProvider": "openai",
        "AnthropicProvider": "anthropic",
        "OllamaProvider": "ollama",
        "GroqProvider": "groq",
        "VLLMProvider": "vllm",
        "HuggingFaceProvider": "huggingface",
        "TogetherProvider": "together",
        "OpenRouterProvider": "openrouter",
        "DeepSeekProvider": "deepseek",
    }
    for cls_name, module_path in _LAZY_PROVIDERS.items():
        module = importlib.import_module(module_path, __package__)
        cls = getattr(module, cls_name)
        globals()[cls_name] = cls
        registry[_name_to_key[cls_name]] = cls
    return registry


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def get_provider(provider_name: str) -> Optional[BaseProvider]:
    """
    Get initialized provider instance.

    Convenience function - handles initialization and errors gracefully.

    Args:
        provider_name: Name of provider (e.g., 'openai', 'anthropic')

    Returns:
        Provider instance or None if initialization fails
    """
    registry = globals().get("PROVIDER_REGISTRY") or __getattr__("PROVIDER_REGISTRY")
    if provider_name not in registry:
        logger.warning(f"Unknown provider: {provider_name}")
        return None

    try:
        provider_class = registry[provider_name]
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
    registry = globals().get("PROVIDER_REGISTRY") or __getattr__("PROVIDER_REGISTRY")
    providers = {}

    for provider_name in registry.keys():
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
    "OpenRouterProvider",
    "DeepSeekProvider",
    "PROVIDER_REGISTRY",
    "get_provider",
    "get_available_providers",
]
