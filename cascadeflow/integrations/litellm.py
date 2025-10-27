"""
LiteLLM integration for CascadeFlow.

Provides accurate cost tracking using LiteLLM's pricing database,
which is maintained and updated regularly by the LiteLLM team.

NEW in v0.2.0 (Phase 2, Milestone 2.1):
    - LiteLLMCostProvider: Accurate cost calculations using LiteLLM
    - SUPPORTED_PROVIDERS: Strategic provider selection with value props
    - Provider validation
    - Automatic fallback if LiteLLM not installed

Benefits over custom pricing:
    - ✓ Always up-to-date pricing (LiteLLM team maintains it)
    - ✓ Covers 100+ models across 10+ providers
    - ✓ Includes both input and output token pricing
    - ✓ Handles special pricing (batch, cached tokens, etc.)

Usage:
    >>> from cascadeflow.integrations.litellm import LiteLLMCostProvider
    >>>
    >>> # Create cost provider
    >>> cost_provider = LiteLLMCostProvider()
    >>>
    >>> # Calculate cost
    >>> cost = cost_provider.calculate_cost(
    ...     model="gpt-4",
    ...     input_tokens=100,
    ...     output_tokens=50
    ... )
    >>> print(f"Cost: ${cost:.6f}")

Installation:
    pip install litellm

    Optional for even more providers:
    pip install litellm[extra_providers]
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import LiteLLM (optional dependency)
try:
    import litellm
    from litellm import completion_cost, model_cost

    LITELLM_AVAILABLE = True
    logger.info("LiteLLM integration available")
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning(
        "LiteLLM not installed. Cost tracking will use fallback estimates. "
        "Install with: pip install litellm"
    )


# ============================================================================
# SUPPORTED PROVIDERS
# ============================================================================

@dataclass
class ProviderInfo:
    """Information about a supported provider."""

    name: str
    display_name: str
    value_prop: str  # Why use this provider?
    pricing_available: bool  # Does LiteLLM have pricing?
    requires_api_key: bool
    example_models: list[str]


# Strategic provider selection (10 providers as per plan)
# Each provider has a clear value proposition
SUPPORTED_PROVIDERS = {
    "openai": ProviderInfo(
        name="openai",
        display_name="OpenAI",
        value_prop="Industry-leading quality, most reliable, best for production",
        pricing_available=True,
        requires_api_key=True,
        example_models=["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    ),
    "anthropic": ProviderInfo(
        name="anthropic",
        display_name="Anthropic Claude",
        value_prop="Best for reasoning and analysis, strong safety features",
        pricing_available=True,
        requires_api_key=True,
        example_models=["claude-3-opus", "claude-3-5-sonnet", "claude-3-sonnet", "claude-3-haiku"],
    ),
    "groq": ProviderInfo(
        name="groq",
        display_name="Groq",
        value_prop="Fastest inference speed, ultra-low latency, free tier",
        pricing_available=True,
        requires_api_key=True,
        example_models=["llama-3.1-70b", "llama-3.1-8b", "mixtral-8x7b"],
    ),
    "together": ProviderInfo(
        name="together",
        display_name="Together AI",
        value_prop="Cost-effective, wide model selection, good for experimentation",
        pricing_available=True,
        requires_api_key=True,
        example_models=["together/llama-3-70b", "together/llama-3-8b", "together/qwen-2-72b"],
    ),
    "huggingface": ProviderInfo(
        name="huggingface",
        display_name="Hugging Face",
        value_prop="Open-source models, community-driven, flexible deployment",
        pricing_available=True,
        requires_api_key=True,
        example_models=["mistralai/Mistral-7B-Instruct-v0.2", "meta-llama/Llama-2-70b-chat"],
    ),
    "ollama": ProviderInfo(
        name="ollama",
        display_name="Ollama",
        value_prop="Local/on-prem deployment, zero cost, full privacy",
        pricing_available=False,  # Free, local
        requires_api_key=False,
        example_models=["llama3.1:8b", "llama3.1:70b", "mistral", "codellama"],
    ),
    "vllm": ProviderInfo(
        name="vllm",
        display_name="vLLM",
        value_prop="Self-hosted inference, high throughput, production-ready",
        pricing_available=False,  # Self-hosted
        requires_api_key=False,
        example_models=["meta-llama/Llama-3.1-70B", "meta-llama/Llama-3.1-8B"],
    ),
    "google": ProviderInfo(
        name="google",
        display_name="Google (Vertex AI)",
        value_prop="Enterprise integration, GCP ecosystem, Gemini models",
        pricing_available=True,
        requires_api_key=True,
        example_models=["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
    ),
    "azure": ProviderInfo(
        name="azure",
        display_name="Azure OpenAI",
        value_prop="Enterprise compliance, HIPAA/SOC2, Microsoft ecosystem",
        pricing_available=True,
        requires_api_key=True,
        example_models=["azure/gpt-4", "azure/gpt-4-turbo", "azure/gpt-3.5-turbo"],
    ),
    "deepseek": ProviderInfo(
        name="deepseek",
        display_name="DeepSeek",
        value_prop="Specialized code models, very cost-effective for coding tasks",
        pricing_available=True,
        requires_api_key=True,
        example_models=["deepseek-coder", "deepseek-chat"],
    ),
}


def validate_provider(provider: str) -> bool:
    """
    Validate if provider is supported.

    Args:
        provider: Provider name to validate

    Returns:
        True if supported, False otherwise

    Example:
        >>> validate_provider("openai")
        True
        >>> validate_provider("unknown_provider")
        False
    """
    supported = provider.lower() in SUPPORTED_PROVIDERS

    if not supported:
        available = ", ".join(SUPPORTED_PROVIDERS.keys())
        logger.warning(
            f"Provider '{provider}' not in supported list. "
            f"Available: {available}"
        )

    return supported


def get_provider_info(provider: str) -> Optional[ProviderInfo]:
    """
    Get information about a provider.

    Args:
        provider: Provider name

    Returns:
        ProviderInfo if found, None otherwise

    Example:
        >>> info = get_provider_info("groq")
        >>> print(info.value_prop)
        'Fastest inference speed, ultra-low latency, free tier'
    """
    return SUPPORTED_PROVIDERS.get(provider.lower())


# ============================================================================
# LITELLM COST PROVIDER
# ============================================================================


class LiteLLMCostProvider:
    """
    Cost calculation using LiteLLM's pricing database.

    This provides accurate, up-to-date pricing for 100+ models across
    10+ providers without maintaining custom pricing tables.

    Example:
        >>> cost_provider = LiteLLMCostProvider()
        >>>
        >>> # Calculate cost from token counts
        >>> cost = cost_provider.calculate_cost(
        ...     model="gpt-4",
        ...     input_tokens=100,
        ...     output_tokens=50
        ... )
        >>>
        >>> # Get model pricing info
        >>> pricing = cost_provider.get_model_cost("gpt-4")
        >>> print(f"Input: ${pricing['input_cost_per_token']:.8f}/token")
    """

    def __init__(self, fallback_enabled: bool = True):
        """
        Initialize LiteLLM cost provider.

        Args:
            fallback_enabled: Use fallback estimates if LiteLLM unavailable
        """
        self.fallback_enabled = fallback_enabled

        if not LITELLM_AVAILABLE:
            logger.warning(
                "LiteLLM not available. Cost calculations will use fallback estimates."
            )

    def calculate_cost(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        **kwargs,
    ) -> float:
        """
        Calculate cost using LiteLLM.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            **kwargs: Additional LiteLLM parameters (cache_tokens, etc.)

        Returns:
            Cost in USD

        Example:
            >>> cost = provider.calculate_cost("gpt-4", 100, 50)
            >>> print(f"${cost:.6f}")
            $0.004500
        """
        if not LITELLM_AVAILABLE:
            if self.fallback_enabled:
                return self._fallback_cost(model, input_tokens, output_tokens)
            else:
                raise RuntimeError(
                    "LiteLLM not installed and fallback disabled. "
                    "Install with: pip install litellm"
                )

        try:
            # Use LiteLLM's completion_cost function
            # This handles all pricing details automatically
            cost = completion_cost(
                model=model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                **kwargs,
            )

            logger.debug(
                f"LiteLLM cost for {model}: ${cost:.6f} "
                f"({input_tokens} in, {output_tokens} out)"
            )

            return cost

        except Exception as e:
            logger.warning(f"LiteLLM cost calculation failed for {model}: {e}")

            if self.fallback_enabled:
                return self._fallback_cost(model, input_tokens, output_tokens)
            else:
                raise

    def get_model_cost(self, model: str) -> dict:
        """
        Get pricing information for a model.

        Args:
            model: Model name

        Returns:
            Dict with pricing info:
                - input_cost_per_token: Cost per input token (USD)
                - output_cost_per_token: Cost per output token (USD)
                - max_tokens: Maximum context length
                - supports_streaming: Whether streaming is supported

        Example:
            >>> pricing = provider.get_model_cost("gpt-4")
            >>> print(f"Input: ${pricing['input_cost_per_token']:.8f}/token")
            Input: $0.00003000/token
        """
        if not LITELLM_AVAILABLE:
            logger.warning("LiteLLM not available, returning fallback pricing")
            return self._fallback_pricing(model)

        try:
            # Get pricing from LiteLLM's model_cost dict
            pricing = model_cost.get(model, {})

            if not pricing:
                logger.warning(f"No pricing found for {model} in LiteLLM")
                return self._fallback_pricing(model)

            return {
                "input_cost_per_token": pricing.get("input_cost_per_token", 0),
                "output_cost_per_token": pricing.get("output_cost_per_token", 0),
                "max_tokens": pricing.get("max_tokens", 4096),
                "supports_streaming": pricing.get("supports_streaming", True),
            }

        except Exception as e:
            logger.warning(f"Error getting pricing for {model}: {e}")
            return self._fallback_pricing(model)

    def _fallback_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Fallback cost estimation when LiteLLM unavailable.

        Uses rough estimates based on typical pricing.
        """
        # Rough pricing estimates (per 1M tokens)
        rough_pricing = {
            # OpenAI
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
            # Anthropic
            "claude-3-opus": {"input": 15.0, "output": 75.0},
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
            # Default
            "default": {"input": 1.0, "output": 2.0},
        }

        # Get pricing or use default
        pricing = rough_pricing.get(model, rough_pricing["default"])

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        total_cost = input_cost + output_cost

        logger.debug(
            f"Fallback cost for {model}: ${total_cost:.6f} "
            f"({input_tokens} in @ ${pricing['input']}/1M, "
            f"{output_tokens} out @ ${pricing['output']}/1M)"
        )

        return total_cost

    def _fallback_pricing(self, model: str) -> dict:
        """Fallback pricing info when LiteLLM unavailable."""
        return {
            "input_cost_per_token": 0.000001,  # $1/1M tokens
            "output_cost_per_token": 0.000002,  # $2/1M tokens
            "max_tokens": 4096,
            "supports_streaming": True,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def get_model_cost(model: str) -> dict:
    """
    Get pricing information for a model.

    Convenience function that creates a LiteLLMCostProvider and calls get_model_cost().

    Args:
        model: Model name

    Returns:
        Dict with pricing info

    Example:
        >>> pricing = get_model_cost("gpt-4")
        >>> print(f"Input: ${pricing['input_cost_per_token']:.8f}/token")
    """
    provider = LiteLLMCostProvider()
    return provider.get_model_cost(model)


def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    **kwargs,
) -> float:
    """
    Calculate cost for a model call.

    Convenience function that creates a LiteLLMCostProvider and calls calculate_cost().

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        **kwargs: Additional parameters

    Returns:
        Cost in USD

    Example:
        >>> cost = calculate_cost("gpt-4", input_tokens=100, output_tokens=50)
        >>> print(f"${cost:.6f}")
        $0.004500
    """
    provider = LiteLLMCostProvider()
    return provider.calculate_cost(model, input_tokens, output_tokens, **kwargs)


__all__ = [
    "SUPPORTED_PROVIDERS",
    "ProviderInfo",
    "LiteLLMCostProvider",
    "get_model_cost",
    "calculate_cost",
    "validate_provider",
    "get_provider_info",
]
