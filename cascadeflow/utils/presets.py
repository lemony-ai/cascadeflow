"""
Smart presets for easy CascadeAgent setup.

Provides:
- Ready-to-use preset configurations
- Auto-detection of available providers
- Pre-configured tier setups
- Smart defaults

Example:
    >>> from cascadeflow import PRESET_BEST_OVERALL, PRESET_ULTRA_FAST
    >>> from cascadeflow import CascadeAgent
    >>>
    >>> # Use ready-to-use preset
    >>> agent = CascadeAgent(PRESET_BEST_OVERALL)
    >>>
    >>> # Or ultra-fast with Groq
    >>> agent = CascadeAgent(PRESET_ULTRA_FAST)
"""

import logging
import os
from typing import Literal

from ..schema.config import ModelConfig

logger = logging.getLogger(__name__)

# Type definitions
QualityMode = Literal["cost-optimized", "balanced", "strict"]
PerformanceMode = Literal["fast", "balanced", "reliable"]


class CascadePresets:
    """
    Smart presets for CascadeAgent initialization.

    Usage:
        >>> # Auto-detect everything
        >>> models = CascadePresets.auto_detect_models()
        >>>
        >>> # Or get specific preset
        >>> models = CascadePresets.cost_optimized_models()
    """

    @staticmethod
    def auto_detect_models() -> list[ModelConfig]:
        """
        Auto-detect available models from all providers.

        Checks in order:
        1. Ollama (local)
        2. OpenAI (if API key set)
        3. Anthropic (if API key set)
        4. Groq (if API key set)

        Returns:
            List of available ModelConfig instances
        """
        models = []

        # Check Ollama
        ollama_models = CascadePresets._detect_ollama()
        if ollama_models:
            models.extend(ollama_models)
            logger.info(f"✓ Detected {len(ollama_models)} Ollama models")

        # Check OpenAI
        if os.getenv("OPENAI_API_KEY"):
            models.extend(
                [
                    ModelConfig(
                        name="gpt-3.5-turbo",
                        provider="openai",
                        cost=0.002,
                        speed_ms=800,
                        quality_score=0.80,
                        domains=["general"],
                    ),
                    ModelConfig(
                        name="gpt-4",
                        provider="openai",
                        cost=0.03,
                        speed_ms=1500,
                        quality_score=0.95,
                        domains=["general", "expert"],
                    ),
                ]
            )
            logger.info("✓ Detected OpenAI")

        # Check Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            models.extend(
                [
                    ModelConfig(
                        name="claude-3-haiku",
                        provider="anthropic",
                        cost=0.00025,
                        speed_ms=600,
                        quality_score=0.75,
                        domains=["general"],
                    ),
                    ModelConfig(
                        name="claude-3-sonnet",
                        provider="anthropic",
                        cost=0.003,
                        speed_ms=1000,
                        quality_score=0.85,
                        domains=["general"],
                    ),
                ]
            )
            logger.info("✓ Detected Anthropic")

        # Check Groq
        if os.getenv("GROQ_API_KEY"):
            models.extend(
                [
                    ModelConfig(
                        name="llama-3.1-70b-versatile",
                        provider="groq",
                        cost=0.0,
                        speed_ms=300,
                        quality_score=0.82,
                        domains=["general"],
                    )
                ]
            )
            logger.info("✓ Detected Groq")

        if not models:
            raise ValueError(
                "No providers detected! Please:\n"
                "1. Start Ollama and pull a model, OR\n"
                "2. Set OPENAI_API_KEY, OR\n"
                "3. Set ANTHROPIC_API_KEY, OR\n"
                "4. Set GROQ_API_KEY\n"
                "Or provide models explicitly"
            )

        logger.info(f"Total detected models: {len(models)}")
        return models

    @staticmethod
    def _detect_ollama() -> list[ModelConfig]:
        """Detect Ollama models."""
        try:
            import httpx

            response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)

            if response.status_code == 200:
                data = response.json()
                models = []

                for model_info in data.get("models", [])[:5]:  # Top 5
                    name = model_info.get("name", "")

                    # Estimate quality based on model name
                    quality = 0.65
                    domains = ["general"]

                    if "code" in name.lower():
                        domains = ["code"]
                        quality = 0.70
                    elif any(x in name.lower() for x in ["70b", "large"]):
                        quality = 0.80

                    models.append(
                        ModelConfig(
                            name=name,
                            provider="ollama",
                            cost=0.0,
                            speed_ms=500,
                            quality_score=quality,
                            domains=domains,
                        )
                    )

                return models
        except Exception as e:
            logger.debug(f"Ollama not detected: {e}")

        return []

    @staticmethod
    def cost_optimized_models() -> list[ModelConfig]:
        """Get cost-optimized model list."""
        models = []

        # Prioritize free models
        ollama = CascadePresets._detect_ollama()
        if ollama:
            models.extend(ollama)

        if os.getenv("GROQ_API_KEY"):
            models.append(
                ModelConfig(
                    name="llama-3.1-70b-versatile",
                    provider="groq",
                    cost=0.0,
                    speed_ms=300,
                    quality_score=0.82,
                    domains=["general"],
                )
            )

        # Add one paid model as fallback
        if os.getenv("OPENAI_API_KEY"):
            models.append(
                ModelConfig(
                    name="gpt-3.5-turbo",
                    provider="openai",
                    cost=0.002,
                    speed_ms=800,
                    quality_score=0.80,
                    domains=["general"],
                )
            )

        return models

    @staticmethod
    def quality_optimized_models() -> list[ModelConfig]:
        """Get quality-optimized model list."""
        models = []

        if os.getenv("OPENAI_API_KEY"):
            models.append(
                ModelConfig(
                    name="gpt-4",
                    provider="openai",
                    cost=0.03,
                    speed_ms=1500,
                    quality_score=0.95,
                    domains=["general", "expert"],
                )
            )

        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(
                ModelConfig(
                    name="claude-3-opus",
                    provider="anthropic",
                    cost=0.015,
                    speed_ms=2000,
                    quality_score=0.92,
                    domains=["general", "expert"],
                )
            )

        # Add cheaper options as drafters
        if os.getenv("GROQ_API_KEY"):
            models.append(
                ModelConfig(
                    name="llama-3.1-70b-versatile",
                    provider="groq",
                    cost=0.0,
                    speed_ms=300,
                    quality_score=0.82,
                    domains=["general"],
                )
            )

        return models

    @staticmethod
    def balanced_models() -> list[ModelConfig]:
        """Get balanced model list (default)."""
        return CascadePresets.auto_detect_models()


# ==================== READY-TO-USE PRESETS ====================

# PRESET: Best Overall
#
# Recommended for most use cases. Uses Claude Haiku (fast, high quality)
# with GPT-4o-mini as backup. Requires Anthropic and OpenAI API keys.
#
# Cost: ~$0.0008/query avg
# Speed: Fast (~2-3s)
# Quality: Excellent
PRESET_BEST_OVERALL: list[ModelConfig] = [
    ModelConfig(
        name="claude-3-5-haiku-20241022",
        provider="anthropic",
        cost=0.0008,
        speed_ms=2000,
        quality_score=0.85,
        domains=["general"],
    ),
    ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        speed_ms=2500,
        quality_score=0.80,
        domains=["general"],
    ),
]

# PRESET: Ultra Fast
#
# Maximum speed with Groq's ultra-fast inference. Best for real-time
# applications where latency is critical. Requires Groq API key.
#
# Cost: ~$0.00005/query avg
# Speed: Ultra-fast (~1-2s)
# Quality: Good
PRESET_ULTRA_FAST: list[ModelConfig] = [
    ModelConfig(
        name="llama-3.1-8b-instant",
        provider="groq",
        cost=0.00005,
        speed_ms=1000,
        quality_score=0.75,
        domains=["general"],
    ),
    ModelConfig(
        name="llama-3.3-70b-versatile",
        provider="groq",
        cost=0.00069,
        speed_ms=1500,
        quality_score=0.82,
        domains=["general"],
    ),
]

# PRESET: Ultra Cheap
#
# Minimum cost with Groq + OpenAI. Best for high-volume, cost-sensitive
# applications. Requires Groq and OpenAI API keys.
#
# Cost: ~$0.00008/query avg
# Speed: Very fast (~1-3s)
# Quality: Good
PRESET_ULTRA_CHEAP: list[ModelConfig] = [
    ModelConfig(
        name="llama-3.1-8b-instant",
        provider="groq",
        cost=0.00005,
        speed_ms=1000,
        quality_score=0.75,
        domains=["general"],
    ),
    ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        speed_ms=2500,
        quality_score=0.80,
        domains=["general"],
    ),
]

# PRESET: OpenAI Only
#
# Uses only OpenAI models. Best when you want to stay within one provider
# or don't have other API keys. Requires OpenAI API key.
#
# Cost: ~$0.0005/query avg
# Speed: Fast (~2-4s)
# Quality: Excellent
PRESET_OPENAI_ONLY: list[ModelConfig] = [
    ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        speed_ms=2500,
        quality_score=0.80,
        domains=["general"],
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.0025,
        speed_ms=3500,
        quality_score=0.95,
        domains=["general", "expert"],
    ),
]

# PRESET: Anthropic Only
#
# Uses only Anthropic Claude models. Best for Claude enthusiasts or
# when you prefer Anthropic's approach. Requires Anthropic API key.
#
# Cost: ~$0.002/query avg
# Speed: Fast (~2-3s)
# Quality: Excellent
PRESET_ANTHROPIC_ONLY: list[ModelConfig] = [
    ModelConfig(
        name="claude-3-5-haiku-20241022",
        provider="anthropic",
        cost=0.0008,
        speed_ms=2000,
        quality_score=0.85,
        domains=["general"],
    ),
    ModelConfig(
        name="claude-sonnet-4-5-20250929",
        provider="anthropic",
        cost=0.009,
        speed_ms=3000,
        quality_score=0.95,
        domains=["general", "expert"],
    ),
]

# PRESET: Free (Local)
#
# Uses Ollama for free, local inference. No API keys needed, but requires
# Ollama installation and models downloaded locally. Best for privacy or
# when offline.
#
# Cost: $0 (free, local)
# Speed: Moderate (~3-5s, depends on hardware)
# Quality: Good
#
# Requires: ollama pull llama3.1:8b && ollama pull llama3.1:70b
PRESET_FREE_LOCAL: list[ModelConfig] = [
    ModelConfig(
        name="llama3.1:8b",
        provider="ollama",
        cost=0.0,
        speed_ms=3000,
        quality_score=0.75,
        domains=["general"],
    ),
    ModelConfig(
        name="llama3.1:70b",
        provider="ollama",
        cost=0.0,
        speed_ms=5000,
        quality_score=0.82,
        domains=["general"],
    ),
]

# Quality threshold presets
QUALITY_THRESHOLDS = {
    "cost-optimized": 0.6,  # Accept more drafts for cost savings
    "balanced": 0.7,  # Default balanced threshold
    "strict": 0.8,  # Higher quality, more escalations
}


def create_preset(
    quality: QualityMode = "balanced",
    performance: PerformanceMode = "balanced",
    include_premium: bool = False,
) -> list[ModelConfig]:
    """
    Create a custom preset with specified quality and performance modes.

    Args:
        quality: Quality mode ('cost-optimized', 'balanced', 'strict')
        performance: Performance mode ('fast', 'balanced', 'reliable')
        include_premium: Whether to include a premium tier (gpt-4o)

    Returns:
        List of ModelConfig objects configured for the preset

    Example:
        >>> from cascadeflow import create_preset
        >>> models = create_preset(
        ...     quality='strict',
        ...     performance='fast',
        ...     include_premium=True
        ... )
    """
    models = []

    # Select models based on performance mode
    if performance == "fast":
        # Groq for maximum speed
        models.extend(
            [
                ModelConfig(
                    name="llama-3.1-8b-instant",
                    provider="groq",
                    cost=0.00005,
                    speed_ms=1000,
                    quality_score=0.75,
                    domains=["general"],
                ),
                ModelConfig(
                    name="llama-3.3-70b-versatile",
                    provider="groq",
                    cost=0.00069,
                    speed_ms=1500,
                    quality_score=0.82,
                    domains=["general"],
                ),
            ]
        )
    elif performance == "reliable":
        # OpenAI/Anthropic for reliability
        models.extend(
            [
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                    speed_ms=2500,
                    quality_score=0.80,
                    domains=["general"],
                ),
                ModelConfig(
                    name="claude-3-5-haiku-20241022",
                    provider="anthropic",
                    cost=0.0008,
                    speed_ms=2000,
                    quality_score=0.85,
                    domains=["general"],
                ),
            ]
        )
    else:
        # Balanced - mix of speed and reliability
        models.extend(
            [
                ModelConfig(
                    name="claude-3-5-haiku-20241022",
                    provider="anthropic",
                    cost=0.0008,
                    speed_ms=2000,
                    quality_score=0.85,
                    domains=["general"],
                ),
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                    speed_ms=2500,
                    quality_score=0.80,
                    domains=["general"],
                ),
            ]
        )

    # Add premium tier if requested
    if include_premium:
        models.append(
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.0025,
                speed_ms=3500,
                quality_score=0.95,
                domains=["general", "expert"],
            )
        )

    return models


# All available presets
PRESETS = {
    "BEST_OVERALL": PRESET_BEST_OVERALL,
    "ULTRA_FAST": PRESET_ULTRA_FAST,
    "ULTRA_CHEAP": PRESET_ULTRA_CHEAP,
    "OPENAI_ONLY": PRESET_OPENAI_ONLY,
    "ANTHROPIC_ONLY": PRESET_ANTHROPIC_ONLY,
    "FREE_LOCAL": PRESET_FREE_LOCAL,
}
