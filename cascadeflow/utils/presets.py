"""
Production-ready presets for cascadeflow.

Presets provide one-line initialization with optimized configurations for common use cases.
All presets are OPTIONAL - users can still configure everything manually.

Usage:
    >>> from cascadeflow.presets import get_cost_optimized_agent
    >>>
    >>> # One-line setup with automatic provider detection
    >>> agent = get_cost_optimized_agent()
    >>> result = await agent.run("What is 2+2?")
    >>>
    >>> # Or manually configure
    >>> from cascadeflow import CascadeAgent
    >>> agent = CascadeAgent(models=[...])

Available Presets:
    - cost_optimized: Minimize cost, accept slower responses
    - balanced: Balance cost, speed, and quality
    - speed_optimized: Minimize latency, higher cost acceptable
    - quality_optimized: Maximize quality, cost/speed secondary
    - development: Fast iteration, verbose logging, relaxed quality
"""

import logging
import os

logger = logging.getLogger(__name__)


# Check provider availability
def _has_openai() -> bool:
    """Check if OpenAI API key is available."""
    return bool(os.getenv("OPENAI_API_KEY"))


def _has_anthropic() -> bool:
    """Check if Anthropic API key is available."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _has_groq() -> bool:
    """Check if Groq API key is available."""
    return bool(os.getenv("GROQ_API_KEY"))


def _has_together() -> bool:
    """Check if Together API key is available."""
    return bool(os.getenv("TOGETHER_API_KEY"))


def _detect_available_providers() -> dict[str, bool]:
    """
    Detect which providers are available based on API keys.

    Returns:
        Dictionary of provider_name -> is_available
    """
    return {
        "openai": _has_openai(),
        "anthropic": _has_anthropic(),
        "groq": _has_groq(),
        "together": _has_together(),
    }


def get_cost_optimized_agent(
    verbose: bool = False,
    enable_cascade: bool = True,
):
    """
    Get cost-optimized agent configuration.

    Strategy:
    - Use cheapest available models
    - Groq (free) > OpenAI mini > Anthropic Haiku
    - Cascade enabled for maximum savings
    - Quality threshold: 0.70 (accept more drafts)

    Use Case:
    - High-volume applications
    - Cost-sensitive deployments
    - Non-critical queries

    Expected Savings: 85-95% vs using GPT-4 only

    Args:
        verbose: Enable verbose logging
        enable_cascade: Enable cascade system (recommended)

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = get_cost_optimized_agent()
        >>> result = await agent.run("Summarize this text")
        >>> print(f"Cost: ${result.total_cost:.6f}")  # Typically $0.00001-0.00005
    """
    from cascadeflow import CascadeAgent
    from cascadeflow.quality import QualityConfig
    from cascadeflow.schema.config import ModelConfig

    providers = _detect_available_providers()
    models = []

    # Priority: Groq (free) -> OpenAI Mini -> Together -> Anthropic Haiku
    if providers["groq"]:
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.00005,  # Nearly free
                speed_ms=300,
                quality_score=0.75,
                supports_tools=True,
            )
        )
        if verbose:
            logger.info("Using Groq (llama-3.1-8b-instant) as drafter - nearly free!")

    if providers["openai"]:
        models.append(
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.00015,  # Very cheap
                speed_ms=600,
                quality_score=0.85,
                supports_tools=True,
            )
        )
        if verbose:
            logger.info("Using OpenAI (gpt-4o-mini) as verifier - $0.00015/1K tokens")

    if providers["together"]:
        models.append(
            ModelConfig(
                name="meta-llama/Llama-3-8b-chat-hf",
                provider="together",
                cost=0.0002,
                speed_ms=400,
                quality_score=0.75,
                supports_tools=False,
            )
        )

    if providers["anthropic"]:
        models.append(
            ModelConfig(
                name="claude-3-haiku-20240307",
                provider="anthropic",
                cost=0.00025,
                speed_ms=700,
                quality_score=0.80,
                supports_tools=True,
            )
        )

    if not models:
        raise RuntimeError(
            "No API keys found. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY"
        )

    # Cost-optimized quality config (accept more drafts)
    quality_config = QualityConfig(
        confidence_thresholds={
            "trivial": 0.60,
            "simple": 0.65,
            "moderate": 0.70,
            "hard": 0.75,
            "expert": 0.80,
        },
        require_specifics_for_complex=False,  # More lenient
    )

    if verbose:
        logger.info(
            f"Cost-Optimized Preset:\n"
            f"  Models: {len(models)} ({[m.name for m in models]})\n"
            f"  Strategy: Use cheapest models, high cascade acceptance\n"
            f"  Expected savings: 85-95% vs GPT-4 only"
        )

    return CascadeAgent(
        models=models,
        quality_config=quality_config,
        enable_cascade=enable_cascade,
        verbose=verbose,
    )


def get_balanced_agent(
    verbose: bool = False,
    enable_cascade: bool = True,
):
    """
    Get balanced agent configuration.

    Strategy:
    - Mix of cheap and capable models
    - Balanced quality threshold (0.75)
    - Good cost/performance ratio

    Use Case:
    - Production applications
    - General purpose usage
    - Balance cost and quality

    Expected Savings: 70-85% vs using GPT-4 only

    Args:
        verbose: Enable verbose logging
        enable_cascade: Enable cascade system (recommended)

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = get_balanced_agent()
        >>> result = await agent.run("Explain quantum computing")
        >>> print(f"Quality: {result.quality_score:.2f}")  # Typically 0.80-0.90
    """
    from cascadeflow import CascadeAgent
    from cascadeflow.quality import QualityConfig
    from cascadeflow.schema.config import ModelConfig

    providers = _detect_available_providers()
    models = []

    # Balanced mix: cheap drafter, capable verifier
    if providers["groq"]:
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.00005,
                speed_ms=300,
                quality_score=0.75,
                supports_tools=True,
            )
        )

    if providers["openai"]:
        models.extend(
            [
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                    speed_ms=600,
                    quality_score=0.85,
                    supports_tools=True,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                    speed_ms=1200,
                    quality_score=0.95,
                    supports_tools=True,
                ),
            ]
        )

    if providers["anthropic"]:
        models.append(
            ModelConfig(
                name="claude-sonnet-4-5-20250929",
                provider="anthropic",
                cost=0.003,
                speed_ms=1000,
                quality_score=0.95,
                supports_tools=True,
            )
        )

    if not models:
        raise RuntimeError(
            "No API keys found. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY"
        )

    # Balanced quality config
    quality_config = QualityConfig.for_cascade()  # Default balanced config

    if verbose:
        logger.info(
            f"Balanced Preset:\n"
            f"  Models: {len(models)} ({[m.name for m in models]})\n"
            f"  Strategy: Balance cost, speed, and quality\n"
            f"  Expected savings: 70-85% vs GPT-4 only"
        )

    return CascadeAgent(
        models=models,
        quality_config=quality_config,
        enable_cascade=enable_cascade,
        verbose=verbose,
    )


def get_speed_optimized_agent(
    verbose: bool = False,
    enable_cascade: bool = True,
):
    """
    Get speed-optimized agent configuration.

    Strategy:
    - Use fastest available models
    - Groq (300ms) preferred
    - Lower quality threshold for faster acceptance

    Use Case:
    - Real-time applications
    - Interactive chatbots
    - Latency-critical systems

    Expected Latency: 300-800ms per query

    Args:
        verbose: Enable verbose logging
        enable_cascade: Enable cascade system (recommended)

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = get_speed_optimized_agent()
        >>> result = await agent.run("Quick fact check")
        >>> print(f"Latency: {result.latency_ms:.0f}ms")  # Typically 300-800ms
    """
    from cascadeflow import CascadeAgent
    from cascadeflow.quality import QualityConfig
    from cascadeflow.schema.config import ModelConfig

    providers = _detect_available_providers()
    models = []

    # Speed priority: Groq > Together > OpenAI mini
    if providers["groq"]:
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.00005,
                speed_ms=300,  # Fastest
                quality_score=0.75,
                supports_tools=True,
            )
        )

    if providers["together"]:
        models.append(
            ModelConfig(
                name="meta-llama/Llama-3-8b-chat-hf",
                provider="together",
                cost=0.0002,
                speed_ms=400,
                quality_score=0.75,
                supports_tools=False,
            )
        )

    if providers["openai"]:
        models.append(
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.00015,
                speed_ms=600,
                quality_score=0.85,
                supports_tools=True,
            )
        )

    if not models:
        raise RuntimeError(
            "No API keys found. Set at least one of: "
            "OPENAI_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY"
        )

    # Speed-optimized quality config (lower thresholds)
    quality_config = QualityConfig(
        confidence_thresholds={
            "trivial": 0.55,
            "simple": 0.60,
            "moderate": 0.65,
            "hard": 0.70,
            "expert": 0.75,
        },
        require_specifics_for_complex=False,
    )

    if verbose:
        logger.info(
            f"Speed-Optimized Preset:\n"
            f"  Models: {len(models)} ({[m.name for m in models]})\n"
            f"  Strategy: Minimize latency, accept lower quality threshold\n"
            f"  Expected latency: 300-800ms per query"
        )

    return CascadeAgent(
        models=models,
        quality_config=quality_config,
        enable_cascade=enable_cascade,
        verbose=verbose,
    )


def get_quality_optimized_agent(
    verbose: bool = False,
    enable_cascade: bool = True,
):
    """
    Get quality-optimized agent configuration.

    Strategy:
    - Use best available models
    - GPT-4o, Claude Sonnet preferred
    - High quality threshold (0.85)
    - Cost and speed secondary

    Use Case:
    - Critical applications
    - High-stakes decisions
    - Quality over cost/speed

    Expected Quality: 0.90-0.98 (very high)

    Args:
        verbose: Enable verbose logging
        enable_cascade: Enable cascade system (recommended)

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = get_quality_optimized_agent()
        >>> result = await agent.run("Analyze this legal contract")
        >>> print(f"Quality: {result.quality_score:.2f}")  # Typically 0.90+
    """
    from cascadeflow import CascadeAgent
    from cascadeflow.quality import QualityConfig
    from cascadeflow.schema.config import ModelConfig

    providers = _detect_available_providers()
    models = []

    # Quality priority: GPT-4o, Claude Sonnet, GPT-4o-mini as fallback
    if providers["openai"]:
        models.extend(
            [
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                    speed_ms=600,
                    quality_score=0.85,
                    supports_tools=True,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                    speed_ms=1200,
                    quality_score=0.95,
                    supports_tools=True,
                ),
            ]
        )

    if providers["anthropic"]:
        models.append(
            ModelConfig(
                name="claude-sonnet-4-5-20250929",
                provider="anthropic",
                cost=0.003,
                speed_ms=1000,
                quality_score=0.95,
                supports_tools=True,
            )
        )

    if not models:
        # Fallback to Groq if no premium providers
        if providers["groq"]:
            models.append(
                ModelConfig(
                    name="llama-3.1-70b-versatile",
                    provider="groq",
                    cost=0.00059,
                    speed_ms=500,
                    quality_score=0.88,
                    supports_tools=True,
                )
            )

    if not models:
        raise RuntimeError(
            "No API keys found. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY"
        )

    # Quality-optimized config (strict thresholds)
    quality_config = QualityConfig.for_production()  # Strict production config

    if verbose:
        logger.info(
            f"Quality-Optimized Preset:\n"
            f"  Models: {len(models)} ({[m.name for m in models]})\n"
            f"  Strategy: Maximize quality, use best models\n"
            f"  Expected quality: 0.90-0.98 (very high)"
        )

    return CascadeAgent(
        models=models,
        quality_config=quality_config,
        enable_cascade=enable_cascade,
        verbose=verbose,
    )


def get_development_agent(
    verbose: bool = True,  # Verbose by default in dev
    enable_cascade: bool = True,
):
    """
    Get development agent configuration.

    Strategy:
    - Use available free/cheap models
    - Verbose logging enabled
    - Relaxed quality thresholds
    - Fast iteration focus

    Use Case:
    - Local development
    - Testing and debugging
    - Rapid prototyping

    Args:
        verbose: Enable verbose logging (default: True)
        enable_cascade: Enable cascade system

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = get_development_agent()
        >>> result = await agent.run("Test query")
        >>> # Verbose output shows all routing decisions
    """
    from cascadeflow import CascadeAgent
    from cascadeflow.quality import QualityConfig
    from cascadeflow.schema.config import ModelConfig

    providers = _detect_available_providers()
    models = []

    # Dev priority: Whatever is available, prefer free/cheap
    if providers["groq"]:
        models.extend(
            [
                ModelConfig(
                    name="llama-3.1-8b-instant",
                    provider="groq",
                    cost=0.00005,
                    speed_ms=300,
                    quality_score=0.75,
                    supports_tools=True,
                ),
                ModelConfig(
                    name="llama-3.1-70b-versatile",
                    provider="groq",
                    cost=0.00059,
                    speed_ms=500,
                    quality_score=0.88,
                    supports_tools=True,
                ),
            ]
        )

    if providers["openai"]:
        models.append(
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.00015,
                speed_ms=600,
                quality_score=0.85,
                supports_tools=True,
            )
        )

    if not models:
        raise RuntimeError(
            "No API keys found for development. Set at least one of: "
            "GROQ_API_KEY (free), OPENAI_API_KEY, ANTHROPIC_API_KEY"
        )

    # Development config (relaxed, verbose)
    quality_config = QualityConfig.for_development()

    if verbose:
        logger.info(
            f"Development Preset:\n"
            f"  Models: {len(models)} ({[m.name for m in models]})\n"
            f"  Strategy: Fast iteration, verbose logging\n"
            f"  Mode: Development (relaxed thresholds)"
        )

    return CascadeAgent(
        models=models,
        quality_config=quality_config,
        enable_cascade=enable_cascade,
        verbose=verbose,
    )


# Convenience function
def auto_agent(
    preset: str = "balanced",
    verbose: bool = False,
    enable_cascade: bool = True,
):
    """
    Automatically create agent with specified preset.

    Args:
        preset: Preset name (cost_optimized, balanced, speed_optimized, quality_optimized, development)
        verbose: Enable verbose logging
        enable_cascade: Enable cascade system

    Returns:
        Configured CascadeAgent

    Example:
        >>> agent = auto_agent("cost_optimized")
        >>> agent = auto_agent("quality_optimized", verbose=True)
    """
    presets = {
        "cost_optimized": get_cost_optimized_agent,
        "balanced": get_balanced_agent,
        "speed_optimized": get_speed_optimized_agent,
        "quality_optimized": get_quality_optimized_agent,
        "development": get_development_agent,
    }

    if preset not in presets:
        raise ValueError(f"Unknown preset '{preset}'. Available: {list(presets.keys())}")

    return presets[preset](verbose=verbose, enable_cascade=enable_cascade)


__all__ = [
    "get_cost_optimized_agent",
    "get_balanced_agent",
    "get_speed_optimized_agent",
    "get_quality_optimized_agent",
    "get_development_agent",
    "auto_agent",
]
