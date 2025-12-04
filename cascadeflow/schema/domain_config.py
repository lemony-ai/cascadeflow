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
DOMAIN_MULTIMODAL = "multimodal"
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

    # Tool-specific model selection (optional, falls back to drafter/verifier)
    tool_drafter: Optional[Union[str, Any]] = None  # Tool-capable drafter
    tool_verifier: Optional[Union[str, Any]] = None  # Tool-capable verifier

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
    skip_on_simple: bool = True  # DEPRECATED: use cascade_complexities instead

    # Per-domain complexity handling
    # Specifies which complexity levels should use cascade (try drafter first)
    # If None, defaults to all complexities using cascade
    # Example: ["trivial", "simple", "moderate", "hard"] - EXPERT goes to verifier
    cascade_complexities: Optional[list[str]] = None

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
            raise ValueError(f"DomainConfig: max_tokens must be positive, got {self.max_tokens}")

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


# Built-in domain configurations (2025 optimized model pairings)
# Based on benchmarks: DeepSeek excels at math/code, Claude 4.5 at reasoning/code review
# See: https://binaryverseai.com/llm-math-benchmark-performance-2025/
#
# Claude Haiku Model Selection (2025):
# - Haiku 3.5: $0.80/$4.00 per 1M tokens - Best for high-volume, simple tasks
# - Haiku 4.5: $1.00/$5.00 per 1M tokens - 25% more expensive but:
#   * 73.3% SWE-bench (matches Sonnet 4)
#   * Extended thinking support
#   * Better tool orchestration for agentic workflows
#   * 64K output tokens (vs 8K for 3.5)
# Decision: Use Haiku 3.5 for general/conversation (cost-sensitive), Haiku 4.5 for creative
#
# GPT-5 Family (August 2025):
# - GPT-5 Nano: $0.05/$0.40 per 1M tokens - Ultra cheap, good for simple drafts
# - GPT-5 Mini: $0.25/$2.00 per 1M tokens - Better quality, still cheaper than GPT-4o-mini
# - GPT-5: $1.25/$10 per 1M tokens - 74.9% SWE-bench, best reasoning
#
# Note: DeepSeek V3 is optimal for code/math/data (97.3% MATH-500, $0.27/M)
# but requires DEEPSEEK_API_KEY. Using GPT-5 Mini/Nano as fallback.
BUILTIN_DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    DOMAIN_CODE: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good code, cheap ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Claude Opus 4.5 - best code review
        threshold=0.85,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.2,
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Code generation with GPT-5 Mini drafter and Opus 4.5 verifier",
    ),
    DOMAIN_MATH: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - strong math reasoning ($0.25/M)
        verifier="gpt-5",  # GPT-5 for strong math verification
        # GSM8K Full Benchmark Results (Dec 2025, 1319 queries, 8-shot CoT):
        # - threshold=0.5: 93.0% accuracy, 99.2% draft acceptance
        # - threshold=0.6: 93.6% accuracy, 98.2% draft acceptance (OPTIMAL)
        # Higher threshold=0.6 provides better accuracy (+0.6%) with minimal
        # reduction in draft acceptance (-1%). Recommended for production.
        threshold=0.6,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.1,
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Math reasoning with 8-shot CoT (GSM8K: 93.6% accuracy, 98.2% draft acceptance)",
    ),
    DOMAIN_MEDICAL: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - better accuracy ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Highest accuracy needed
        threshold=0.95,
        validation_method=DomainValidationMethod.FACT,
        temperature=0.1,
        require_verifier=True,  # Always verify medical content
        description="High-accuracy medical responses with mandatory Opus 4.5 verification",
    ),
    DOMAIN_LEGAL: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - better accuracy ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Best reasoning for legal
        threshold=0.90,
        validation_method=DomainValidationMethod.FACT,
        temperature=0.2,
        require_verifier=True,  # Legal requires high accuracy
        description="Legal domain with Opus 4.5 fact-checking",
    ),
    DOMAIN_FINANCIAL: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - strong at calculations ($0.25/M)
        verifier="gpt-5",  # GPT-5 for financial verification
        # Same reasoning as math domain - drafter handles calculations well
        # Lower threshold maximizes cost savings without accuracy loss
        threshold=0.5,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.2,
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Financial analysis with low threshold (similar to math domain)",
    ),
    DOMAIN_DATA: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good at SQL/analysis ($0.25/M)
        verifier="gpt-5",
        threshold=0.80,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.3,
        cascade_complexities=["trivial", "simple", "moderate", "hard"],
        description="Data analysis and SQL with GPT-5 Mini drafter",
    ),
    DOMAIN_STRUCTURED: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good at structured output ($0.25/M)
        verifier="gpt-5",
        threshold=0.75,
        validation_method=DomainValidationMethod.SYNTAX,
        temperature=0.2,
        cascade_complexities=["trivial", "simple", "moderate", "hard"],
        description="Structured data extraction (JSON/XML) with GPT-5 Mini",
    ),
    DOMAIN_CREATIVE: DomainConfig(
        drafter="claude-haiku-4-5-20251001",  # Haiku 4.5 - best value for creative ($1/$5 per 1M)
        verifier="claude-sonnet-4-5-20250929",  # Claude Sonnet 4.5 - excellent creative quality ($3/$15)
        # Research (Dec 2025): Claude models have "the most soul in writing" - vivid characters,
        # consistent narrative voice. Lower threshold since Haiku 4.5 excels at creative tasks.
        threshold=0.55,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.9,  # High temperature for creative variance
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Creative writing with Claude Haiku 4.5 ($1/$5) and Sonnet 4.5 verifier ($3/$15). Best for narrative, character, engaging voice.",
    ),
    DOMAIN_GENERAL: DomainConfig(
        drafter="claude-3-5-haiku-20241022",  # Fast, cheap, good quality
        verifier="claude-sonnet-4-5-20250929",  # Claude Sonnet 4.5
        threshold=0.70,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.7,
        cascade_complexities=["trivial", "simple", "moderate"],
        description="General queries with Claude Haiku and Sonnet 4.5 verifier",
    ),
    DOMAIN_CONVERSATION: DomainConfig(
        drafter="claude-3-5-haiku-20241022",
        verifier="gpt-5",
        threshold=0.65,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.8,
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Conversational responses with Claude Haiku and GPT-5 verifier",
    ),
    DOMAIN_SCIENCE: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good scientific reasoning ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Best reasoning
        threshold=0.85,
        validation_method=DomainValidationMethod.FACT,
        temperature=0.2,
        cascade_complexities=["trivial", "simple", "moderate", "hard"],
        description="Scientific reasoning with GPT-5 Mini drafter and Opus 4.5 verification",
    ),
    DOMAIN_TOOL: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good tool calling ($0.25/M)
        verifier="gpt-5",  # GPT-5 - excellent function calling
        threshold=0.75,
        validation_method=DomainValidationMethod.SYNTAX,  # Validate tool output format
        temperature=0.2,  # Low temp for precise tool calls
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Tool calling with GPT-5 Mini drafter and GPT-5 verifier",
    ),
    DOMAIN_RAG: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good context handling ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Best for context synthesis
        threshold=0.80,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.3,  # Balanced for retrieval augmented generation
        cascade_complexities=["trivial", "simple", "moderate", "hard"],
        description="RAG with GPT-5 Mini drafter and Opus 4.5 context verification",
    ),
    DOMAIN_SUMMARY: DomainConfig(
        drafter="claude-3-5-haiku-20241022",  # Claude Haiku - fast summarization
        verifier="claude-sonnet-4-5-20250929",  # Sonnet 4.5 for quality summaries
        threshold=0.70,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.5,  # Moderate temp for good summaries
        cascade_complexities=["trivial", "simple", "moderate", "hard"],
        description="Summarization with Claude Haiku drafter and Sonnet 4.5 verifier",
    ),
    DOMAIN_TRANSLATION: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - good multilingual ($0.25/M)
        verifier="gpt-5",  # GPT-5 - excellent translation
        threshold=0.80,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.3,  # Low temp for accurate translation
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Translation with GPT-5 Mini drafter and GPT-5 verifier",
    ),
    DOMAIN_MULTIMODAL: DomainConfig(
        drafter="gpt-5-mini",  # GPT-5 Mini - vision capable ($0.25/M)
        verifier="claude-opus-4-5-20251101",  # Opus 4.5 - best multimodal reasoning
        threshold=0.75,
        validation_method=DomainValidationMethod.QUALITY,
        temperature=0.4,
        cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        description="Multimodal with GPT-5 Mini drafter and Opus 4.5 verification",
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
    domain_str = domain.value if hasattr(domain, "value") else domain
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
