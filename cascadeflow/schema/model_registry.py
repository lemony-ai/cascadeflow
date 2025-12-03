"""
Model Registry - Maps model names to configurations

The ModelRegistry provides a centralized way to resolve model names
(like "gpt-4o" or "deepseek-coder") to full ModelConfig objects with
provider, cost, and capability information.

Example:
    >>> from cascadeflow.schema.model_registry import ModelRegistry, get_model
    >>>
    >>> registry = ModelRegistry()
    >>>
    >>> # Get a built-in model
    >>> gpt4o = registry.get("gpt-4o")
    >>> print(gpt4o["provider"])  # 'openai'
    >>> print(gpt4o["cost"])  # 0.0025
    >>>
    >>> # Register a custom model
    >>> registry.register("my-model", {
    ...     "name": "my-fine-tuned-model",
    ...     "provider": "openai",
    ...     "cost": 0.005,
    ... })
    >>>
    >>> # Use convenience function
    >>> model = get_model("gpt-4o")
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class ModelRegistryEntry:
    """
    Model configuration with extended metadata.

    Attributes:
        name: Model name as used by the provider
        provider: Provider name (e.g., 'openai', 'anthropic')
        cost: Cost per 1K tokens (input cost)
        aliases: Alternative names for this model
        domains: Domains this model excels at
        context_window: Context window size in tokens
        supports_tools: Whether model supports function calling
        supports_streaming: Whether model supports streaming
        supports_vision: Whether model supports image inputs
        release_date: Model release date
        deprecated: Deprecation notice if being sunset
    """

    name: str
    provider: str
    cost: float

    # Optional metadata
    aliases: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    context_window: Optional[int] = None
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    release_date: Optional[str] = None
    deprecated: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "provider": self.provider,
            "cost": self.cost,
            "aliases": self.aliases,
            "domains": self.domains,
            "context_window": self.context_window,
            "supports_tools": self.supports_tools,
            "supports_streaming": self.supports_streaming,
            "supports_vision": self.supports_vision,
            "release_date": self.release_date,
            "deprecated": self.deprecated,
        }


# Built-in model definitions with current pricing (as of Nov 2024)
BUILTIN_MODELS: dict[str, ModelRegistryEntry] = {
    # ========================================================================
    # OpenAI Models
    # ========================================================================
    "gpt-4o": ModelRegistryEntry(
        name="gpt-4o",
        provider="openai",
        cost=0.0025,
        aliases=["gpt4o", "gpt-4-omni"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "gpt-4o-mini": ModelRegistryEntry(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        aliases=["gpt4o-mini", "gpt-4-mini"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "gpt-4": ModelRegistryEntry(
        name="gpt-4",
        provider="openai",
        cost=0.03,
        aliases=["gpt4"],
        context_window=8192,
        supports_tools=True,
        supports_streaming=True,
    ),
    "gpt-4-turbo": ModelRegistryEntry(
        name="gpt-4-turbo",
        provider="openai",
        cost=0.01,
        aliases=["gpt4-turbo"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "gpt-3.5-turbo": ModelRegistryEntry(
        name="gpt-3.5-turbo",
        provider="openai",
        cost=0.0005,
        aliases=["gpt35", "gpt-35-turbo"],
        context_window=16385,
        supports_tools=True,
        supports_streaming=True,
    ),
    "o1": ModelRegistryEntry(
        name="o1",
        provider="openai",
        cost=0.015,
        aliases=["openai-o1"],
        context_window=128000,
        supports_tools=False,
        supports_streaming=False,
    ),
    "o1-mini": ModelRegistryEntry(
        name="o1-mini",
        provider="openai",
        cost=0.003,
        aliases=["openai-o1-mini"],
        context_window=128000,
        supports_tools=False,
        supports_streaming=False,
    ),
    # ========================================================================
    # Anthropic Models
    # ========================================================================
    "claude-3-opus": ModelRegistryEntry(
        name="claude-3-opus-20240229",
        provider="anthropic",
        cost=0.015,
        aliases=["claude-opus", "claude-3-opus-20240229"],
        context_window=200000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "claude-3-sonnet": ModelRegistryEntry(
        name="claude-3-sonnet-20240229",
        provider="anthropic",
        cost=0.003,
        aliases=["claude-sonnet", "claude-3-sonnet-20240229"],
        context_window=200000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "claude-3.5-sonnet": ModelRegistryEntry(
        name="claude-3-5-sonnet-20241022",
        provider="anthropic",
        cost=0.003,
        aliases=["claude-35-sonnet", "claude-3-5-sonnet"],
        context_window=200000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    "claude-3-haiku": ModelRegistryEntry(
        name="claude-3-haiku-20240307",
        provider="anthropic",
        cost=0.00025,
        aliases=["claude-haiku", "claude-3-haiku-20240307"],
        context_window=200000,
        supports_tools=True,
        supports_streaming=True,
        supports_vision=True,
    ),
    # ========================================================================
    # Groq Models (Fast inference)
    # ========================================================================
    "groq/llama-3.1-70b": ModelRegistryEntry(
        name="llama-3.1-70b-versatile",
        provider="groq",
        cost=0.00059,
        aliases=["llama-3.1-70b", "llama-70b"],
        context_window=131072,
        supports_tools=True,
        supports_streaming=True,
    ),
    "groq/llama-3.1-8b": ModelRegistryEntry(
        name="llama-3.1-8b-instant",
        provider="groq",
        cost=0.00005,
        aliases=["llama-3.1-8b", "llama-8b"],
        context_window=131072,
        supports_tools=True,
        supports_streaming=True,
    ),
    "groq/mixtral-8x7b": ModelRegistryEntry(
        name="mixtral-8x7b-32768",
        provider="groq",
        cost=0.00024,
        aliases=["mixtral-8x7b", "mixtral"],
        context_window=32768,
        supports_tools=True,
        supports_streaming=True,
    ),
    # ========================================================================
    # DeepSeek Models (Code-optimized)
    # ========================================================================
    "deepseek-coder": ModelRegistryEntry(
        name="deepseek-coder",
        provider="deepseek",
        cost=0.00014,
        aliases=["deepseek-coder-v2"],
        domains=["code"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
    ),
    "deepseek-chat": ModelRegistryEntry(
        name="deepseek-chat",
        provider="deepseek",
        cost=0.00014,
        aliases=["deepseek"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
    ),
    # ========================================================================
    # Together AI Models
    # ========================================================================
    "together/llama-3.1-405b": ModelRegistryEntry(
        name="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        provider="together",
        cost=0.005,
        aliases=["llama-405b", "llama-3.1-405b"],
        context_window=130000,
        supports_tools=True,
        supports_streaming=True,
    ),
    "together/llama-3.1-70b": ModelRegistryEntry(
        name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        provider="together",
        cost=0.00088,
        aliases=["together-llama-70b"],
        context_window=130000,
        supports_tools=True,
        supports_streaming=True,
    ),
    "together/qwen-72b": ModelRegistryEntry(
        name="Qwen/Qwen2.5-72B-Instruct-Turbo",
        provider="together",
        cost=0.0012,
        aliases=["qwen-72b", "qwen2.5-72b"],
        context_window=32768,
        supports_tools=True,
        supports_streaming=True,
    ),
    # ========================================================================
    # Ollama Models (Local)
    # ========================================================================
    "ollama/llama3": ModelRegistryEntry(
        name="llama3",
        provider="ollama",
        cost=0,
        aliases=["llama3-local", "ollama-llama3"],
        context_window=8192,
        supports_tools=False,
        supports_streaming=True,
    ),
    "ollama/mistral": ModelRegistryEntry(
        name="mistral",
        provider="ollama",
        cost=0,
        aliases=["mistral-local", "ollama-mistral"],
        context_window=8192,
        supports_tools=False,
        supports_streaming=True,
    ),
    "ollama/codellama": ModelRegistryEntry(
        name="codellama",
        provider="ollama",
        cost=0,
        aliases=["codellama-local"],
        domains=["code"],
        context_window=16384,
        supports_tools=False,
        supports_streaming=True,
    ),
    # ========================================================================
    # OpenRouter (Multi-provider)
    # ========================================================================
    "openrouter/auto": ModelRegistryEntry(
        name="openrouter/auto",
        provider="openrouter",
        cost=0.001,
        aliases=["openrouter-auto"],
        context_window=128000,
        supports_tools=True,
        supports_streaming=True,
    ),
}


class ModelRegistry:
    """
    Registry for resolving model names to configurations.

    Provides:
    - Built-in models with current pricing
    - Custom model registration
    - Alias resolution
    - YAML/JSON config loading

    Example:
        >>> registry = ModelRegistry()
        >>> gpt4o = registry.get("gpt-4o")
        >>> print(gpt4o.provider)  # 'openai'
    """

    def __init__(self):
        """Initialize registry with built-in models."""
        self.models: dict[str, ModelRegistryEntry] = {}
        self.aliases: dict[str, str] = {}

        # Load built-in models
        for name, config in BUILTIN_MODELS.items():
            self._register_internal(name, config)

    def _register_internal(self, name: str, config: ModelRegistryEntry) -> None:
        """Register a model internally (with alias handling)."""
        normalized = name.lower()
        self.models[normalized] = config

        # Register aliases
        for alias in config.aliases:
            self.aliases[alias.lower()] = normalized

    def register(self, name: str, config: ModelRegistryEntry) -> None:
        """
        Register a custom model.

        Args:
            name: Model identifier
            config: Model configuration
        """
        self._register_internal(name, config)

    def get(self, name: str) -> ModelRegistryEntry:
        """
        Get a model by name or alias.

        Args:
            name: Model name or alias

        Returns:
            ModelRegistryEntry

        Raises:
            ValueError: If model not found
        """
        normalized = name.lower()

        # Check direct match
        if normalized in self.models:
            return self.models[normalized]

        # Check aliases
        if normalized in self.aliases:
            canonical = self.aliases[normalized]
            return self.models[canonical]

        available = ", ".join(list(self.models.keys())[:5])
        raise ValueError(
            f'Unknown model: "{name}". '
            f'Use registry.register("{name}", ...) to add it, '
            f"or use one of: {available}..."
        )

    def has(self, name: str) -> bool:
        """Check if a model exists in the registry."""
        normalized = name.lower()
        return normalized in self.models or normalized in self.aliases

    def get_or_none(self, name: str) -> Optional[ModelRegistryEntry]:
        """Get a model if it exists, otherwise return None."""
        try:
            return self.get(name)
        except ValueError:
            return None

    def list_models(self) -> list[str]:
        """List all registered model names."""
        return list(self.models.keys())

    def list_by_provider(self, provider: str) -> list[str]:
        """List models by provider."""
        return [name for name, config in self.models.items() if config.provider == provider]

    def list_by_domain(self, domain: str) -> list[str]:
        """List models that support a specific domain."""
        return [name for name, config in self.models.items() if domain in config.domains]

    def list_with_tool_support(self) -> list[str]:
        """List models that support function calling."""
        return [name for name, config in self.models.items() if config.supports_tools]

    def get_cheapest(
        self,
        max_cost: Optional[float] = None,
        supports_tools: Optional[bool] = None,
        supports_streaming: Optional[bool] = None,
        provider: Optional[str] = None,
    ) -> Optional[ModelRegistryEntry]:
        """
        Get the cheapest model that meets certain criteria.

        Args:
            max_cost: Maximum cost per 1K tokens
            supports_tools: Require tool support
            supports_streaming: Require streaming support
            provider: Specific provider

        Returns:
            ModelRegistryEntry or None if no match
        """
        candidates = list(self.models.values())

        if max_cost is not None:
            candidates = [m for m in candidates if m.cost <= max_cost]
        if supports_tools:
            candidates = [m for m in candidates if m.supports_tools]
        if supports_streaming:
            candidates = [m for m in candidates if m.supports_streaming]
        if provider:
            candidates = [m for m in candidates if m.provider == provider]

        if not candidates:
            return None

        return min(candidates, key=lambda m: m.cost)

    def resolve(self, name_or_config: Union[str, ModelRegistryEntry]) -> ModelRegistryEntry:
        """
        Convert a model name to a full ModelRegistryEntry.

        Args:
            name_or_config: Model name or existing config

        Returns:
            ModelRegistryEntry
        """
        if isinstance(name_or_config, str):
            return self.get(name_or_config)
        return name_or_config

    @classmethod
    def from_dict(cls, models: dict[str, dict[str, Any]]) -> "ModelRegistry":
        """Create a registry from a dictionary."""
        registry = cls()
        for name, config_dict in models.items():
            config = ModelRegistryEntry(**config_dict)
            registry.register(name, config)
        return registry

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Export registry to a dictionary."""
        return {name: config.to_dict() for name, config in self.models.items()}


# Global default registry instance
_default_registry: Optional[ModelRegistry] = None


def get_default_registry() -> ModelRegistry:
    """Get the global default model registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ModelRegistry()
    return _default_registry


def get_model(name: str) -> ModelRegistryEntry:
    """
    Get a model from the default registry.

    Args:
        name: Model name or alias

    Returns:
        ModelRegistryEntry
    """
    return get_default_registry().get(name)


def has_model(name: str) -> bool:
    """
    Check if a model exists in the default registry.

    Args:
        name: Model name or alias

    Returns:
        True if model exists
    """
    return get_default_registry().has(name)
