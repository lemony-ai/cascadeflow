"""
Smart presets for easy CascadeAgent setup.

Provides:
- Auto-detection of available providers
- Pre-configured tier setups
- Smart defaults
"""

import logging
import os

from ..schema.config import ModelConfig

logger = logging.getLogger(__name__)


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
