"""
CascadeFlow - Smart AI model cascading for cost optimization.

Route queries intelligently across multiple AI models from tiny SLMs
to frontier LLMs based on complexity, domain, and budget.

Features:
- 🚀 Speculative cascades (2-3x faster)
- 💰 60-95% cost savings
- 🎯 User tier system
- 🔍 Semantic routing
- 🆓 Free tier (Ollama + Groq)
- ⚡ 3 lines of code

Example:
    >>> from cascadeflow import CascadeAgent, ModelConfig
    >>>
    >>> models = [
    ...     ModelConfig("llama3:8b", provider="ollama", cost=0.0),
    ...     ModelConfig("gpt-4", provider="openai", cost=0.03)
    ... ]
    >>>
    >>> agent = CascadeAgent(models)
    >>> result = await agent.run("Explain AI")
    >>> print(result.content)
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__license__ = "MIT"

# Core configuration classes
from .config import ModelConfig, CascadeConfig, UserTier

# Provider interfaces
from .providers import ModelResponse, BaseProvider, PROVIDER_REGISTRY

# Main agent and result
from .agent import CascadeAgent
from .result import CascadeResult

# Utilities
from .utils import setup_logging, format_cost, estimate_tokens

# Exceptions
from .exceptions import (
    CascadeFlowError,
    ConfigError,
    ProviderError,
    ModelError,
    BudgetExceededError,
    RateLimitError,
    QualityThresholdError,
    RoutingError,
    ValidationError,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",

    # Configuration
    "ModelConfig",
    "CascadeConfig",
    "UserTier",

    # Main agent and result
    "CascadeAgent",
    "CascadeResult",

    # Providers
    "ModelResponse",
    "BaseProvider",
    "PROVIDER_REGISTRY",

    # Utilities
    "setup_logging",
    "format_cost",
    "estimate_tokens",

    # Exceptions
    "CascadeFlowError",
    "ConfigError",
    "ProviderError",
    "ModelError",
    "BudgetExceededError",
    "RateLimitError",
    "QualityThresholdError",
    "RoutingError",
    "ValidationError",
]