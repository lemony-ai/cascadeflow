"""
Domain-Specific Cascade Configuration

This module provides the DomainConfig class for configuring domain-specific
cascade behavior. Each domain (CODE, MEDICAL, GENERAL, etc.) can have its own
drafter/verifier models, quality thresholds, and generation parameters.

Example:
    >>> from cascadeflow import CascadeAgent, DomainConfig
    >>>
    >>> code_config = DomainConfig(
    ...     drafter="deepseek-coder",
    ...     verifier="gpt-4o",
    ...     threshold=0.85,
    ...     temperature=0.2,
    ...     validation_method="syntax",
    ... )
    >>>
    >>> agent = CascadeAgent(
    ...     domain_configs={
    ...         "code": code_config,  # Use string keys
    ...     },
    ... )

Note:
    This module uses string domain identifiers to avoid circular imports.
    Domain strings match the Domain enum values in cascadeflow.routing.domain.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

# Domain string constants (matches routing.domain.Domain values)
# Using strings avoids circular imports with routing module
DOMAIN_CODE = "code"
DOMAIN_DATA = "data"
DOMAIN_STRUCTURED = "structured"
DOMAIN_RAG = "rag"
DOMAIN_CONVERSATION = "conversation"
DOMAIN_TOOL = "tool"
DOMAIN_CREATIVE = "creative"
DOMAIN_SUMMARY = "summary"
DOMAIN_TRANSLATION = "translation"
DOMAIN_MATH = "math"
DOMAIN_SCIENCE = "science"
DOMAIN_MEDICAL = "medical"
DOMAIN_LEGAL = "legal"
DOMAIN_FINANCIAL = "financial"
DOMAIN_GENERAL = "general"


class DomainValidationMethod(str, Enum):
    """Validation methods for domain-specific validation."""

    NONE = "none"
    SYNTAX = "syntax"  # Code/JSON syntax validation
    FACT = "fact"  # Fact-checking (medical, legal)
    SAFETY = "safety"  # Safety/toxicity checking
    QUALITY = "quality"  # General quality validation
    SEMANTIC = "semantic"  # ML-based semantic similarity
    CUSTOM = "custom"  # Custom validation function


@dataclass
class DomainConfig:
    """
    Domain-specific cascade configuration.

    Allows fine-grained control over how cascading works for each domain:
    - Model selection (drafter/verifier)
    - Quality thresholds
    - Generation parameters
    - Fallback behavior

    Attributes:
        drafter: Drafter model name or ModelConfig (cheaper, faster model)
        verifier: Verifier model name or ModelConfig (more capable model)
        threshold: Quality threshold (0-1) for accepting drafter responses
        validation_method: Validation method for this domain
        temperature: Temperature for generation (0-2)
        max_tokens: Maximum tokens to generate
        fallback_models: Fallback models to try if both fail
        require_verifier: Always use verifier, even if drafter passes
        adaptive_threshold: Enable adaptive threshold learning
        skip_on_simple: Skip verifier for trivial/simple queries
        enabled: Whether this domain config is enabled
        description: Human-readable description
        metadata: Additional metadata for custom use cases

    Example:
        >>> config = DomainConfig(
        ...     drafter="gpt-4o-mini",
        ...     verifier="gpt-4o",
        ...     threshold=0.85,
        ...     temperature=0.3,
        ... )
    """

    # Required: Model selection
    drafter: Union[str, Any]  # str or ModelConfig
    verifier: Union[str, Any]  # str or ModelConfig

    # Quality control
    threshold: float = 0.70
    validation_method: Union[str, DomainValidationMethod] = DomainValidationMethod.QUALITY

    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 1000

    # Fallback chain
    fallback_models: list[str] = field(default_factory=list)

    # Behavior flags
    require_verifier: bool = False
    adaptive_threshold: bool = True
    skip_on_simple: bool = True

    # Metadata
    enabled: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        if not self.drafter:
            raise ValueError("DomainConfig: drafter is required")
        if not self.verifier:
            raise ValueError("DomainConfig: verifier is required")

        if not 0 <= self.threshold <= 1:
            raise ValueError(
                f"DomainConfig: threshold must be between 0 and 1, got {self.threshold}"
            )

        if not 0 <= self.temperature <= 2:
            raise ValueError(
                f"DomainConfig: temperature must be between 0 and 2, got {self.temperature}"
            )

        if self.max_tokens <= 0:
            raise ValueError(
                f"DomainConfig: max_tokens must be positive, got {self.max_tokens}"
            )

        # Convert string validation method to enum
        if isinstance(self.validation_method, str):
            self.validation_method = DomainValidationMethod(self.validation_method)

    def resolve_models(self, registry: "ModelRegistry") -> tuple[Any, Any]:
        """
        Resolve model names to ModelConfig objects.

        Args:
            registry: ModelRegistry instance

        Returns:
            Tuple of (drafter_config, verifier_config)
        """
        drafter = registry.get(self.drafter) if isinstance(self.drafter, str) else self.drafter
        verifier = registry.get(self.verifier) if isinstance(self.verifier, str) else self.verifier
        return drafter, verifier


# Built-in domain configurations (using string keys to avoid circular imports)
BUILTIN_DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    DOMAIN_CODE: DomainConfig(
        drafter="deepseek-coder",
        verifier="gpt-4o",
        threshold=0.85,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.2,
        description="Optimized for code generation with syntax validation",
    ),
    DOMAIN_MEDICAL: DomainConfig(
        drafter="gpt-4o-mini",
        verifier="gpt-4",
        threshold=0.95,
        validation_method=DomainValidationMethod.FACT,
        temperature=0.1,
        require_verifier=True,
        description="High-accuracy medical responses with mandatory verification",
    ),
    DOMAIN_LEGAL: DomainConfig(
        drafter="gpt-4o-mini",
        verifier="gpt-4o",
        threshold=0.90,
        validation_method=DomainValidationMethod.FACT,
        temperature=0.2,
        description="Legal domain with fact-checking",
    ),
    DOMAIN_DATA: DomainConfig(
        drafter="gpt-4o-mini",
        verifier="gpt-4o",
        threshold=0.80,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.3,
        description="Data analysis and SQL with syntax validation",
    ),
    DOMAIN_MATH: DomainConfig(
        drafter="gpt-4o-mini",
        verifier="gpt-4o",
        threshold=0.90,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.1,
        description="Mathematical reasoning with high precision",
    ),
    DOMAIN_STRUCTURED: DomainConfig(
        drafter="gpt-4o-mini",
        verifier="gpt-4o",
        threshold=0.75,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.2,
        description="Structured data extraction (JSON/XML)",
    ),
    DOMAIN_GENERAL: DomainConfig(
        drafter="groq/llama-3.1-70b",
        verifier="gpt-4o",
        threshold=0.70,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.7,
        description="Fast general-purpose queries",
    ),
}


def get_builtin_domain_config(domain: str) -> Optional[DomainConfig]:
    """
    Get a built-in domain configuration.

    Args:
        domain: Domain string (e.g., "code", "medical", "general")
                Can also be a Domain enum value (will use .value)

    Returns:
        DomainConfig if available, None otherwise

    Example:
        >>> config = get_builtin_domain_config("code")
        >>> print(config.drafter)  # "deepseek-coder"
    """
    # Handle both string and Domain enum
    domain_str = domain.value if hasattr(domain, 'value') else domain
    return BUILTIN_DOMAIN_CONFIGS.get(domain_str)


def create_domain_config(
    drafter: str,
    verifier: str,
    threshold: float = 0.70,
    validation_method: str = "quality",
    temperature: float = 0.7,
    **kwargs,
) -> DomainConfig:
    """
    Create a DomainConfig with convenience syntax.

    Args:
        drafter: Drafter model name
        verifier: Verifier model name
        threshold: Quality threshold (0-1)
        validation_method: Validation method name
        temperature: Generation temperature
        **kwargs: Additional DomainConfig parameters

    Returns:
        Configured DomainConfig instance

    Example:
        >>> config = create_domain_config(
        ...     drafter="gpt-4o-mini",
        ...     verifier="gpt-4o",
        ...     threshold=0.85,
        ... )
    """
    return DomainConfig(
        drafter=drafter,
        verifier=verifier,
        threshold=threshold,
        validation_method=validation_method,
        temperature=temperature,
        **kwargs,
    )
