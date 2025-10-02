"""Core CascadeAgent implementation."""

import logging
import time
import os
from typing import List, Optional, Dict, Any, Callable
import asyncio

from .config import ModelConfig, CascadeConfig, UserTier
from .result import CascadeResult
from .providers import PROVIDER_REGISTRY, BaseProvider, ModelResponse
from .exceptions import (
    CascadeFlowError,
    BudgetExceededError,
    ModelError,
    ProviderError,
    QualityThresholdError,
)
from .utils import setup_logging, format_cost, estimate_tokens

logger = logging.getLogger(__name__)


class CascadeAgent:
    """
    Main cascade agent for intelligent model routing.

    The CascadeAgent tries models in order (cheap → expensive) until
    the quality threshold is met or budget is exceeded.

    Example:
        >>> models = [
        ...     ModelConfig(name="llama3:8b", provider="ollama", cost=0.0),
        ...     ModelConfig(name="gpt-4", provider="openai", cost=0.03)
        ... ]
        >>> agent = CascadeAgent(models)
        >>> result = await agent.run("What is AI?")
    """

    def __init__(
            self,
            models: List[ModelConfig],
            config: Optional[CascadeConfig] = None,
            tiers: Optional[Dict[str, UserTier]] = None,
            verbose: bool = False
    ):
        """
        Initialize CascadeAgent.

        Args:
            models: List of models to cascade through (cheap → expensive)
            config: Cascade configuration (uses defaults if None)
            tiers: User tier definitions
            verbose: Enable verbose logging
        """
        self.models = models
        self.config = config or CascadeConfig()
        self.tiers = tiers or {}
        self.verbose = verbose

        # Setup logging
        if verbose:
            setup_logging("DEBUG")
        else:
            setup_logging(self.config.log_level)

        # Initialize providers
        self.providers: Dict[str, BaseProvider] = {}
        self._init_providers()

        # Statistics
        self.stats = {
            "total_queries": 0,
            "total_cost": 0.0,
            "total_cascades": 0,
            "model_usage": {},
        }

        logger.info(f"CascadeAgent initialized with {len(models)} models")
        if verbose:
            for model in models:
                logger.debug(f"  - {model.name} ({model.provider}): ${model.cost:.6f}")

    def _init_providers(self):
        """
        Initialize provider instances.

        Creates provider objects for each unique provider in model list.
        Reuses providers across multiple models.
        """
        provider_names = set(model.provider for model in self.models)

        for provider_name in provider_names:
            try:
                # Get provider class from registry
                if provider_name not in PROVIDER_REGISTRY:
                    logger.warning(f"Provider '{provider_name}' not in registry, skipping")
                    continue

                provider_class = PROVIDER_REGISTRY[provider_name]

                # Initialize provider
                # Provider will load API key from environment
                provider = provider_class()

                self.providers[provider_name] = provider
                logger.debug(f"Initialized provider: {provider_name}")

            except Exception as e:
                logger.warning(f"Failed to initialize provider '{provider_name}': {e}")
                # Continue with other providers

        if not self.providers:
            raise CascadeFlowError(
                "No providers could be initialized. Please check your API keys and configuration."
            )

        logger.info(f"Initialized {len(self.providers)} providers: {list(self.providers.keys())}")

    async def run(
            self,
            query: str,
            user_tier: Optional[str] = None,
            user_id: Optional[str] = None,
            max_budget: Optional[float] = None,
            quality_threshold: Optional[float] = None,
            domains: Optional[List[str]] = None,
            **kwargs
    ) -> CascadeResult:
        """
        Run cascade on a query.

        Tries models in order until quality threshold met or budget exceeded.

        Args:
            query: User query
            user_tier: User tier name (applies tier settings)
            user_id: User ID for tracking
            max_budget: Maximum budget for this query
            quality_threshold: Minimum confidence score required
            domains: Domain hints for routing (e.g., ["code"])
            **kwargs: Additional parameters

        Returns:
            CascadeResult with response and metadata

        Raises:
            BudgetExceededError: If budget exceeded
            QualityThresholdError: If no model meets threshold
        """
        start_time = time.time()

        # Apply user tier settings if provided
        if user_tier and user_tier in self.tiers:
            tier = self.tiers[user_tier]
            tier_config = tier.to_cascade_config()

            # Override with tier settings
            max_budget = max_budget or tier_config.get("max_budget")
            quality_threshold = quality_threshold or tier_config.get("quality_threshold")

            logger.info(f"Applied tier '{user_tier}': budget=${max_budget}, threshold={quality_threshold}")

        # Use config defaults if not specified
        max_budget = max_budget or self.config.max_budget
        quality_threshold = quality_threshold or self.config.quality_threshold

        # Track cascade state
        cascade_path = []
        cost_breakdown = {}
        token_breakdown = {}
        latency_breakdown = {}
        total_cost = 0.0
        total_tokens = 0
        attempts = 0
        last_response = None

        # Filter models by domain if specified
        available_models = self.models
        if domains:
            available_models = [
                m for m in self.models
                if not m.domains or any(d in m.domains for d in domains)
            ]
            if available_models:
                logger.info(f"Filtered to {len(available_models)} models for domains: {domains}")

        # Try each model in sequence
        for model_config in available_models:
            attempts += 1
            cascade_path.append(model_config.name)

            # Check if provider is available
            if model_config.provider not in self.providers:
                logger.warning(f"Provider '{model_config.provider}' not available, skipping {model_config.name}")
                continue

            # Check budget before trying
            if total_cost >= max_budget:
                logger.warning(f"Budget exceeded (${total_cost:.6f} >= ${max_budget:.6f})")
                raise BudgetExceededError(
                    f"Budget of ${max_budget:.6f} exceeded",
                    remaining=max_budget - total_cost
                )

            logger.info(f"Trying model {attempts}/{len(available_models)}: {model_config.name}")

            try:
                # Get provider
                provider = self.providers[model_config.provider]

                # Make API call
                model_start = time.time()
                response = await provider.complete(
                    prompt=query,
                    model=model_config.name,
                    max_tokens=model_config.max_tokens,
                    temperature=model_config.temperature,
                    system_prompt=model_config.system_prompt,
                )
                model_latency = (time.time() - model_start) * 1000

                # Track costs and metrics
                total_cost += response.cost
                total_tokens += response.tokens_used
                cost_breakdown[model_config.name] = response.cost
                token_breakdown[model_config.name] = response.tokens_used
                latency_breakdown[model_config.name] = model_latency
                last_response = response

                logger.info(
                    f"✓ {model_config.name}: "
                    f"confidence={response.confidence:.2f}, "
                    f"cost=${response.cost:.6f}, "
                    f"tokens={response.tokens_used}"
                )

                # Check if quality threshold met
                if response.confidence >= quality_threshold:
                    logger.info(f"✅ Quality threshold met ({response.confidence:.2f} >= {quality_threshold:.2f})")

                    # Update stats
                    self.stats["total_queries"] += 1
                    self.stats["total_cost"] += total_cost
                    if attempts > 1:
                        self.stats["total_cascades"] += 1
                    self.stats["model_usage"][model_config.name] = \
                        self.stats["model_usage"].get(model_config.name, 0) + 1

                    # Build result
                    total_latency = (time.time() - start_time) * 1000

                    return CascadeResult(
                        content=response.content,
                        model_used=model_config.name,
                        provider=model_config.provider,
                        total_cost=total_cost,
                        total_tokens=total_tokens,
                        confidence=response.confidence,
                        cost_breakdown=cost_breakdown,
                        token_breakdown=token_breakdown,
                        quality_threshold_met=True,
                        cascaded=(attempts > 1),
                        cascade_path=cascade_path,
                        attempts=attempts,
                        latency_ms=total_latency,
                        latency_breakdown=latency_breakdown,
                        user_id=user_id,
                        user_tier=user_tier,
                        user_credits_used=total_cost,
                        budget_remaining=max_budget - total_cost,
                    )

                else:
                    logger.info(
                        f"⚠️ Quality threshold not met "
                        f"({response.confidence:.2f} < {quality_threshold:.2f}), cascading..."
                    )
                    # Continue to next model

            except (ModelError, ProviderError) as e:
                logger.error(f"❌ Error with {model_config.name}: {e}")
                # Continue to next model
                continue

        # No model met threshold
        max_confidence = last_response.confidence if last_response else 0.0
        raise QualityThresholdError(
            f"No model met quality threshold of {quality_threshold:.2f}. "
            f"Tried {attempts} models with max confidence {max_confidence:.2f}"
        )

    @classmethod
    def smart_default(cls, tiers: Optional[Dict[str, UserTier]] = None) -> "CascadeAgent":
        """
        Create CascadeAgent with smart defaults.

        Auto-detects available providers and creates optimal cascade:
        1. Ollama (free local) if available
        2. vLLM (free self-hosted) if available
        3. Groq (free cloud) if available
        4. HuggingFace (free/cheap) if available
        5. Together.ai (cheap) if available
        6. OpenAI GPT-3.5 if available
        7. OpenAI GPT-4 if available
        8. Anthropic Claude if available

        Args:
            tiers: Optional user tier definitions

        Returns:
            CascadeAgent with detected providers
        """
        models = []

        # Check Ollama (local)
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if response.status_code == 200:
                models.append(ModelConfig(
                    name="llama3:8b",
                    provider="ollama",
                    cost=0.0,
                    keywords=["simple", "quick"]
                ))
                logger.info("✓ Detected Ollama (local)")
        except:
            logger.debug("Ollama not detected")

        # Check vLLM (self-hosted)
        try:
            import httpx
            response = httpx.get("http://localhost:8000/v1/models", timeout=2.0)
            if response.status_code == 200:
                models.append(ModelConfig(
                    name="meta-llama/Llama-3-70B-Instruct",
                    provider="vllm",
                    base_url="http://localhost:8000/v1",
                    cost=0.0,
                    keywords=["moderate", "detailed"]
                ))
                logger.info("✓ Detected vLLM (self-hosted)")
        except:
            logger.debug("vLLM not detected")

        # Check Groq
        if os.getenv("GROQ_API_KEY"):
            models.append(ModelConfig(
                name="llama-3.1-70b-versatile",
                provider="groq",
                cost=0.0,
                keywords=["moderate"]
            ))
            logger.info("✓ Detected Groq API key")

        # Check HuggingFace
        if os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN"):
            models.append(ModelConfig(
                name="codellama/CodeLlama-34b-Instruct-hf",
                provider="huggingface",
                cost=0.0,
                keywords=["code"],
                domains=["code"]
            ))
            logger.info("✓ Detected HuggingFace token")

        # Check Together.ai
        if os.getenv("TOGETHER_API_KEY"):
            models.append(ModelConfig(
                name="meta-llama/Llama-3-70b-chat-hf",
                provider="together",
                cost=0.0009,
                keywords=["moderate", "detailed"]
            ))
            logger.info("✓ Detected Together.ai API key")

        # Check OpenAI
        if os.getenv("OPENAI_API_KEY"):
            models.append(ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost=0.002,
                keywords=["moderate", "detailed"]
            ))
            models.append(ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                keywords=["complex", "expert"]
            ))
            logger.info("✓ Detected OpenAI API key")

        # Check Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(ModelConfig(
                name="claude-3-sonnet-20240229",
                provider="anthropic",
                cost=0.003,
                keywords=["complex"]
            ))
            logger.info("✓ Detected Anthropic API key")

        if not models:
            raise CascadeFlowError(
                "No providers detected. Please set at least one API key or run a local server:\n"
                "  - OPENAI_API_KEY for OpenAI\n"
                "  - GROQ_API_KEY for Groq (14k free requests/day)\n"
                "  - ANTHROPIC_API_KEY for Anthropic\n"
                "  - HF_TOKEN for HuggingFace (1000 free requests/day)\n"
                "  - TOGETHER_API_KEY for Together.ai ($25 free credits)\n"
                "  - Or install Ollama for local models\n"
                "  - Or run vLLM for high-performance self-hosted"
            )

        logger.info(f"Created smart cascade with {len(models)} models")

        return cls(models=models, tiers=tiers, verbose=True)

    def add_tier(self, name: str, tier: UserTier):
        """
        Add or update a user tier.

        Args:
            name: Tier name
            tier: UserTier configuration
        """
        self.tiers[name] = tier
        logger.info(f"Added tier '{name}': budget=${tier.max_budget}, threshold={tier.quality_threshold}")

    def get_tier(self, name: str) -> Optional[UserTier]:
        """Get tier by name."""
        return self.tiers.get(name)

    def list_tiers(self) -> List[str]:
        """List all tier names."""
        return list(self.tiers.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            **self.stats,
            "avg_cost": self.stats["total_cost"] / max(1, self.stats["total_queries"]),
            "cascade_rate": self.stats["total_cascades"] / max(1, self.stats["total_queries"]),
        }