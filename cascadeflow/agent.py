"""
Enhanced CascadeAgent with full intelligence layer integration.

Integrates:
- Semantic routing (with graceful fallback)
- Complexity detection
- Domain detection and scoring
- Speculative cascades with flexible deferral
- Multi-factor optimization
- Callbacks, caching, streaming
- 20+ control parameters
"""

import asyncio
import time
import logging
import os
from typing import List, Optional, Dict, Any, Callable

from .config import (
    ModelConfig, CascadeConfig, UserTier, WorkflowProfile,
    DEFAULT_TIERS, OptimizationWeights
)
from .complexity import ComplexityDetector, QueryComplexity
from .execution import (
    LatencyAwareExecutionPlanner,
    ExecutionStrategy
)
from .speculative import (
    SpeculativeCascade,
    DeferralStrategy,
    FlexibleDeferralRule
)
from .callbacks import CallbackManager, CallbackEvent
from .caching import ResponseCache
from .streaming import StreamManager
from .routing import SemanticRouter  # ✅ NEW: Semantic routing
from .result import CascadeResult
from .providers import PROVIDER_REGISTRY
from .exceptions import (
    CascadeFlowError,
    BudgetExceededError,
    ModelError,
    ProviderError,
    QualityThresholdError,
)
from .utils import setup_logging

logger = logging.getLogger(__name__)


class CascadeAgent:
    """
    Enhanced CascadeAgent with full intelligent orchestration.

    Features:
    - Semantic routing with embedding-based similarity (default, optional)
    - Per-prompt domain detection and routing
    - 2.0x domain boost for specialists
    - 1.5x size boost for small models on simple tasks
    - Speculative cascades with 4 deferral strategies
    - Multi-factor optimization (cost/speed/quality)
    - Callbacks, caching, streaming support
    - 20+ control parameters per query

    Example:
        >>> from cascadeflow import CascadeAgent, CascadePresets
        >>>
        >>> # Auto-detect models
        >>> models = CascadePresets.auto_detect_models()
        >>>
        >>> # Create agent with semantic routing
        >>> agent = CascadeAgent(
        ...     models=models,
        ...     routing_strategy="semantic",  # default
        ...     enable_caching=True,
        ...     verbose=True
        ... )
        >>>
        >>> # Run query (per-prompt optimization!)
        >>> result = await agent.run(
        ...     query="Fix this Python bug",
        ...     user_tier="premium"
        ... )
        >>>
        >>> print(f"Used: {result.model_used}")
        >>> print(f"Cost: ${result.total_cost:.6f}")
        >>> print(f"Latency: {result.latency_ms:.0f}ms")
    """

    def __init__(
            self,
            models: List[ModelConfig],
            config: Optional[CascadeConfig] = None,
            tiers: Optional[Dict[str, UserTier]] = None,
            workflows: Optional[Dict[str, WorkflowProfile]] = None,
            routing_strategy: str = "semantic",  # ✅ NEW: Routing strategy
            enable_caching: bool = False,
            cache_size: int = 1000,
            enable_callbacks: bool = True,
            verbose: bool = False
    ):
        """
        Initialize CascadeAgent with intelligence layer.

        Args:
            models: List of available models
            config: Global cascade configuration
            tiers: User tier configurations (uses defaults if None)
            workflows: Workflow profiles (optional)
            routing_strategy: "semantic" (default), "keyword", or "hybrid"
            enable_caching: Enable response caching
            cache_size: Max cache entries
            enable_callbacks: Enable callback system
            verbose: Enable verbose logging
        """
        self.models = models
        self.config = config or CascadeConfig()
        self.tiers = tiers or DEFAULT_TIERS
        self.workflows = workflows or {}
        self.verbose = verbose

        # Setup logging
        if verbose:
            setup_logging("DEBUG")
        else:
            setup_logging(self.config.log_level)

        # Initialize intelligence layer
        self.complexity_detector = ComplexityDetector()
        self.execution_planner = LatencyAwareExecutionPlanner()

        # ✅ NEW: Semantic routing with graceful fallback
        self.routing_strategy = routing_strategy
        self.semantic_router = None

        if routing_strategy in ["semantic", "hybrid"]:
            try:
                self.semantic_router = SemanticRouter()
                if self.semantic_router.is_available():
                    # Precompute embeddings for all models
                    self.semantic_router.precompute_model_embeddings(models)
                    logger.info(f"✓ Semantic routing enabled (strategy: {routing_strategy})")
                else:
                    logger.info("⚠️ Semantic routing unavailable, using keyword routing")
                    self.routing_strategy = "keyword"
            except Exception as e:
                logger.warning(f"Failed to initialize semantic routing: {e}")
                logger.info("Falling back to keyword routing")
                self.routing_strategy = "keyword"
                self.semantic_router = None
        else:
            logger.info(f"Using {routing_strategy} routing")

        # Initialize supporting features
        self.callback_manager = CallbackManager() if enable_callbacks else None
        self.cache = ResponseCache(max_size=cache_size) if enable_caching else None
        self.stream_manager = StreamManager()

        # Initialize providers
        self.providers = self._init_providers()

        # Initialize speculative cascades (if we have 2+ models)
        self.speculative_cascades: Dict[str, SpeculativeCascade] = {}
        if len(models) >= 2:
            self._init_speculative_cascades()

        # Statistics
        self.stats = {
            "total_queries": 0,
            "total_cost": 0.0,
            "total_cascades": 0,
            "model_usage": {},
            "routing_strategy": self.routing_strategy,  # ✅ NEW: Track routing strategy
        }

        logger.info(
            f"CascadeAgent initialized with {len(models)} models, "
            f"routing={self.routing_strategy}, "
            f"caching={'enabled' if enable_caching else 'disabled'}"
        )

    def _init_providers(self) -> Dict[str, Any]:
        """Initialize all providers."""
        providers = {}
        provider_types = set(model.provider for model in self.models)

        for provider_type in provider_types:
            if provider_type in PROVIDER_REGISTRY:
                try:
                    providers[provider_type] = PROVIDER_REGISTRY[provider_type]()
                    logger.debug(f"Initialized provider: {provider_type}")
                except Exception as e:
                    logger.warning(f"Failed to initialize provider '{provider_type}': {e}")

        if not providers:
            raise CascadeFlowError(
                "No providers could be initialized. Please check your API keys and configuration."
            )

        return providers

    def _init_speculative_cascades(self):
        """Initialize speculative cascades for model pairs."""
        # Sort models by cost (cheap to expensive)
        sorted_models = sorted(self.models, key=lambda m: (m.cost, m.speed_ms))

        # Create cascades: each cheap model as drafter, expensive as verifier
        for i, drafter in enumerate(sorted_models[:-1]):
            for verifier in sorted_models[i+1:]:
                if verifier.cost > drafter.cost or verifier.quality_score > drafter.quality_score:
                    key = f"{drafter.name}->{verifier.name}"
                    self.speculative_cascades[key] = SpeculativeCascade(
                        drafter=drafter,
                        verifier=verifier,
                        providers=self.providers,
                        verbose=self.verbose
                    )

                    if self.verbose:
                        logger.debug(f"Created speculative cascade: {key}")

    async def run(
            self,
            query: str,

            # ===== USER CONTEXT =====
            user_tier: Optional[str] = None,
            user_id: Optional[str] = None,

            # ===== WORKFLOW =====
            workflow: Optional[str] = None,

            # ===== MODEL CONTROL (Highest Priority) =====
            force_models: Optional[List[str]] = None,
            exclude_models: Optional[List[str]] = None,
            preferred_models: Optional[List[str]] = None,

            # ===== DOMAIN (Auto-detected if not provided) =====
            query_domains: Optional[List[str]] = None,

            # ===== COMPLEXITY =====
            complexity_hint: Optional[QueryComplexity] = None,

            # ===== BUDGET CONTROL =====
            max_budget: Optional[float] = None,
            preferred_budget: Optional[float] = None,

            # ===== QUALITY CONTROL =====
            quality_threshold: Optional[float] = None,
            target_quality: Optional[float] = None,

            # ===== PERFORMANCE =====
            max_latency_ms: Optional[int] = None,
            timeout: Optional[int] = None,

            # ===== OPTIMIZATION =====
            cost_weight: Optional[float] = None,
            speed_weight: Optional[float] = None,
            quality_weight: Optional[float] = None,

            # ===== SPECULATIVE CONTROL =====
            enable_speculative: Optional[bool] = None,
            deferral_strategy: Optional[DeferralStrategy] = None,
            confidence_threshold: Optional[float] = None,

            # ===== FEATURES =====
            streaming: bool = False,
            enable_caching: Optional[bool] = None,

            # ===== CALLBACKS =====
            on_cascade: Optional[Callable] = None,
            on_complete: Optional[Callable] = None,
            on_error: Optional[Callable] = None,

            # ===== METADATA =====
            metadata: Optional[Dict[str, Any]] = None,

            **kwargs
    ) -> CascadeResult:
        """
        Run cascade with full intelligence and control.

        **EVERY PROMPT IS INDIVIDUALLY ANALYZED**

        For EACH query:
        1. Semantic routing (if enabled) + keyword fallback
        2. Detects domains (code? math? general?)
        3. Detects complexity (trivial? expert?)
        4. Scores ALL models with domain boost
        5. Selects optimal execution strategy
        6. Respects all constraints

        Args:
            query: User query/prompt

            User Context:
                user_tier: Apply tier settings (e.g., "free", "premium")
                user_id: Track user for analytics

            Workflow:
                workflow: Apply workflow profile (e.g., "code_review")

            Model Control (Highest Priority):
                force_models: Only use these models (overrides everything)
                exclude_models: Never use these models
                preferred_models: Try these first if suitable

            Domain:
                query_domains: Domain hints (e.g., ["code", "math"])
                               Auto-detected if not provided

            Complexity:
                complexity_hint: Override complexity detection

            Budget Control:
                max_budget: Hard limit on cost
                preferred_budget: Try to stay under this

            Quality Control:
                quality_threshold: Minimum acceptable confidence
                target_quality: Desired quality level

            Performance:
                max_latency_ms: Maximum acceptable latency
                timeout: Timeout per model call (seconds)

            Optimization:
                cost_weight: Weight for cost in scoring (0-1)
                speed_weight: Weight for speed in scoring (0-1)
                quality_weight: Weight for quality in scoring (0-1)

            Speculative Control:
                enable_speculative: Use speculative cascades
                deferral_strategy: Which deferral strategy to use
                confidence_threshold: Confidence threshold for deferral

            Features:
                streaming: Stream response chunks
                enable_caching: Use response cache

            Callbacks:
                on_cascade: Called when cascading to next model
                on_complete: Called when query completes
                on_error: Called on error

            Metadata:
                metadata: Custom metadata for tracking

        Returns:
            CascadeResult with response, cost, latency, model used, etc.
        """
        start_time = time.time()

        # Trigger start callback
        if self.callback_manager:
            self.callback_manager.trigger(
                CallbackEvent.QUERY_START,
                query=query,
                data={"user_tier": user_tier, "workflow": workflow},
                user_tier=user_tier,
                workflow=workflow
            )

        # Register user callbacks
        if on_cascade and self.callback_manager:
            self.callback_manager.register(CallbackEvent.CASCADE_DECISION, on_cascade)
        if on_complete and self.callback_manager:
            self.callback_manager.register(CallbackEvent.QUERY_COMPLETE, on_complete)
        if on_error and self.callback_manager:
            self.callback_manager.register(CallbackEvent.QUERY_ERROR, on_error)

        try:
            # 1. Get tier and workflow
            tier = self.tiers.get(user_tier) if user_tier else None
            workflow_profile = self.workflows.get(workflow) if workflow else None

            # 2. Check cache
            use_cache = (
                enable_caching if enable_caching is not None
                else (tier.enable_caching if tier else False)
            )

            if use_cache and self.cache:
                cached = self.cache.get(query, params=metadata)
                if cached:
                    if self.callback_manager:
                        self.callback_manager.trigger(
                            CallbackEvent.CACHE_HIT,
                            query=query,
                            data={"cached": True},
                            user_tier=user_tier,
                            workflow=workflow
                        )
                    logger.info("✓ Cache hit")
                    return CascadeResult(**cached)
                else:
                    if self.callback_manager:
                        self.callback_manager.trigger(
                            CallbackEvent.CACHE_MISS,
                            query=query,
                            data={"cached": False},
                            user_tier=user_tier,
                            workflow=workflow
                        )

            # 3. Detect complexity
            if complexity_hint:
                complexity = complexity_hint
            else:
                complexity, confidence = self.complexity_detector.detect(
                    query,
                    context={"tier": user_tier, "domain": query_domains}
                )

            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.COMPLEXITY_DETECTED,
                    query=query,
                    data={"complexity": complexity.value},
                    user_tier=user_tier,
                    workflow=workflow
                )

            if self.verbose:
                logger.info(f"🧠 Complexity: {complexity.value}")

            # 4. Filter models
            available_models = self._filter_models(
                self.models,
                tier,
                workflow_profile,
                exclude_models,
                force_models
            )

            # ✅ NEW: 4.5. Get semantic routing hints (if available)
            semantic_hints = None
            if self.semantic_router and self.semantic_router.is_available():
                try:
                    semantic_matches = self.semantic_router.route(
                        query=query,
                        models=available_models,
                        top_k=3,
                        similarity_threshold=0.3
                    )
                    if semantic_matches:
                        semantic_hints = {
                            model.name: similarity
                            for model, similarity in semantic_matches
                        }
                        if self.verbose:
                            top_match = semantic_matches[0]
                            logger.info(
                                f"🎯 Semantic routing: {top_match[0].name} "
                                f"(similarity: {top_match[1]:.3f})"
                            )
                except Exception as e:
                    logger.debug(f"Semantic routing failed: {e}")

            # 5. Create execution plan
            plan = await self.execution_planner.create_plan(
                query=query,
                complexity=complexity,
                available_models=available_models,
                tier=tier,
                workflow=workflow_profile,
                force_models=force_models,
                max_latency_ms=max_latency_ms,
                max_budget=max_budget,
                quality_threshold=quality_threshold,
                query_domains=query_domains,
                semantic_hints=semantic_hints  # ✅ NEW: Pass semantic hints
            )

            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.STRATEGY_SELECTED,
                    query=query,
                    data={
                        "strategy": plan.strategy.value,
                        "primary_model": plan.primary_model.name if plan.primary_model else None,
                        "reasoning": plan.reasoning
                    },
                    user_tier=user_tier,
                    workflow=workflow
                )

            if self.verbose:
                logger.info(f"📋 Strategy: {plan.strategy.value}")
                logger.info(f"💡 Reasoning: {plan.reasoning}")

            # 6. Execute plan
            result = await self._execute_plan(
                query=query,
                plan=plan,
                streaming=streaming,
                tier=tier,
                enable_speculative=enable_speculative,
                deferral_strategy=deferral_strategy,
                confidence_threshold=confidence_threshold,
                user_tier=user_tier,
                workflow=workflow,
                **kwargs
            )

            # 7. Store in cache
            if use_cache and self.cache:
                cache_ttl = tier.cache_ttl if tier else 3600
                self.cache.set(
                    query,
                    result.to_dict(),
                    ttl=cache_ttl,
                    params=metadata
                )

            # 8. Update statistics
            self.stats["total_queries"] += 1
            self.stats["total_cost"] += result.total_cost
            if result.cascaded:
                self.stats["total_cascades"] += 1
            self.stats["model_usage"][result.model_used] = \
                self.stats["model_usage"].get(result.model_used, 0) + 1

            # 9. Trigger complete callback
            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.QUERY_COMPLETE,
                    query=query,
                    data={
                        "success": True,
                        "cost": result.total_cost,
                        "latency_ms": result.latency_ms,
                        "model": result.model_used
                    },
                    user_tier=user_tier,
                    workflow=workflow
                )

            return result

        except Exception as e:
            logger.error(f"Error in cascade: {e}", exc_info=True)

            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.QUERY_ERROR,
                    query=query,
                    data={"error": str(e)},
                    user_tier=user_tier,
                    workflow=workflow
                )

            raise

        finally:
            # Cleanup callbacks
            if on_cascade and self.callback_manager:
                self.callback_manager.unregister(CallbackEvent.CASCADE_DECISION, on_cascade)
            if on_complete and self.callback_manager:
                self.callback_manager.unregister(CallbackEvent.QUERY_COMPLETE, on_complete)
            if on_error and self.callback_manager:
                self.callback_manager.unregister(CallbackEvent.QUERY_ERROR, on_error)

    def _filter_models(
            self,
            models: List[ModelConfig],
            tier: Optional[UserTier],
            workflow: Optional[WorkflowProfile],
            exclude: Optional[List[str]],
            force: Optional[List[str]]
    ) -> List[ModelConfig]:
        """Filter models based on constraints."""
        filtered = models.copy()

        # Force models (highest priority)
        if force:
            return [m for m in filtered if m.name in force]

        # Workflow exclusions
        if workflow and workflow.exclude_models:
            filtered = [m for m in filtered if m.name not in workflow.exclude_models]

        # Per-query exclusions
        if exclude:
            filtered = [m for m in filtered if m.name not in exclude]

        # Tier exclusions
        if tier and tier.exclude_models:
            filtered = [m for m in filtered if m.name not in tier.exclude_models]

        # Tier allowed list
        if tier and "*" not in tier.allowed_models:
            filtered = [m for m in filtered if m.name in tier.allowed_models]

        return filtered

    async def _execute_plan(
            self,
            query: str,
            plan: Any,
            streaming: bool,
            tier: Optional[UserTier],
            enable_speculative: Optional[bool],
            deferral_strategy: Optional[DeferralStrategy],
            confidence_threshold: Optional[float],
            user_tier: Optional[str],
            workflow: Optional[str],
            **kwargs
    ) -> CascadeResult:
        """Execute the execution plan."""
        start_time = time.time()

        if plan.strategy == ExecutionStrategy.DIRECT_CHEAP:
            result = await self._execute_direct(
                query, plan.primary_model, **kwargs
            )

        elif plan.strategy == ExecutionStrategy.DIRECT_BEST:
            result = await self._execute_direct(
                query, plan.primary_model, **kwargs
            )

        elif plan.strategy == ExecutionStrategy.DIRECT_SMART:
            result = await self._execute_direct(
                query, plan.primary_model, **kwargs
            )

        elif plan.strategy == ExecutionStrategy.SPECULATIVE:
            # Check if speculative is enabled
            use_speculative = (
                enable_speculative if enable_speculative is not None
                else (tier.enable_speculative if tier else True)
            )

            if use_speculative and plan.drafter and plan.verifier:
                result = await self._execute_speculative(
                    query,
                    plan.drafter,
                    plan.verifier,
                    deferral_strategy,
                    confidence_threshold,
                    **kwargs
                )
            else:
                # Fallback to direct
                result = await self._execute_direct(
                    query, plan.drafter, **kwargs
                )

        elif plan.strategy == ExecutionStrategy.PARALLEL_RACE:
            result = await self._execute_parallel_race(
                query, plan.race_models, **kwargs
            )

        else:
            result = await self._execute_direct(
                query, plan.primary_model, **kwargs
            )

        return result

    async def _execute_direct(
            self,
            query: str,
            model: ModelConfig,
            **kwargs
    ) -> CascadeResult:
        """Execute direct model call (no cascade)."""
        start_time = time.time()

        provider = self.providers[model.provider]

        if self.callback_manager:
            self.callback_manager.trigger(
                CallbackEvent.MODEL_CALL_START,
                query=query,
                data={"model": model.name, "provider": model.provider},
                user_tier=None,
                workflow=None
            )

        try:
            response = await provider.complete(
                model=model.name,
                prompt=query,
                **kwargs
            )

            latency = (time.time() - start_time) * 1000

            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.MODEL_CALL_COMPLETE,
                    query=query,
                    data={
                        "model": model.name,
                        "latency_ms": latency,
                        "cost": model.cost
                    },
                    user_tier=None,
                    workflow=None
                )

            return CascadeResult(
                content=response.get('content', ''),
                model_used=model.name,
                provider=model.provider,
                total_cost=model.cost,
                total_tokens=response.get('tokens_used', len(response.get('content', '').split())),
                confidence=response.get('confidence', 0.0),
                latency_ms=latency,
                strategy="direct",
                metadata={
                    "tokens": len(response.get('content', '').split())
                }
            )

        except Exception as e:
            if self.callback_manager:
                self.callback_manager.trigger(
                    CallbackEvent.MODEL_CALL_ERROR,
                    query=query,
                    data={"model": model.name, "error": str(e)},
                    user_tier=None,
                    workflow=None
                )
            raise

    async def _execute_speculative(
            self,
            query: str,
            drafter: ModelConfig,
            verifier: ModelConfig,
            deferral_strategy: Optional[DeferralStrategy],
            confidence_threshold: Optional[float],
            **kwargs
    ) -> CascadeResult:
        """Execute speculative cascade."""
        cascade_key = f"{drafter.name}->{verifier.name}"

        if cascade_key not in self.speculative_cascades:
            # Create on-demand
            cascade = SpeculativeCascade(
                drafter=drafter,
                verifier=verifier,
                providers=self.providers,
                verbose=self.verbose
            )
        else:
            cascade = self.speculative_cascades[cascade_key]

        # Override deferral rule if specified
        if deferral_strategy or confidence_threshold:
            cascade.deferral_rule = FlexibleDeferralRule(
                strategy=deferral_strategy or DeferralStrategy.COMPARATIVE,
                confidence_threshold=confidence_threshold or 0.7
            )

        spec_result = await cascade.execute(query, **kwargs)

        if self.callback_manager and not spec_result.draft_accepted:
            self.callback_manager.trigger(
                CallbackEvent.CASCADE_DECISION,
                query=query,
                data={
                    "from": drafter.name,
                    "to": verifier.name,
                    "reason": spec_result.metadata.get("reason", "unknown")
                },
                user_tier=None,
                workflow=None
            )

        return CascadeResult(
            content=spec_result.content,
            model_used=spec_result.model_used,
            provider=verifier.provider,
            total_cost=spec_result.total_cost,
            total_tokens=spec_result.tokens_drafted + spec_result.tokens_verified,
            confidence=spec_result.draft_confidence if spec_result.draft_accepted else spec_result.verifier_confidence,
            latency_ms=spec_result.latency_ms,
            strategy="speculative",
            metadata={
                "draft_accepted": spec_result.draft_accepted,
                "drafter": spec_result.drafter_model,
                "verifier": spec_result.verifier_model,
                "speedup": spec_result.speedup,
                "deferral_strategy": spec_result.deferral_strategy
            }
        )

    async def _execute_parallel_race(
            self,
            query: str,
            models: List[ModelConfig],
            **kwargs
    ) -> CascadeResult:
        """Execute parallel race (first to finish wins)."""
        start_time = time.time()

        tasks = [
            self._execute_direct(query, model, **kwargs)
            for model in models
        ]

        # Race them
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining
        for task in pending:
            task.cancel()

        # Get winner
        winner = list(done)[0].result()

        if self.verbose:
            logger.info(
                f"🏁 Parallel race won by {winner.model_used} "
                f"in {winner.latency_ms:.0f}ms"
            )

        return winner

    @classmethod
    def smart_default(cls, tiers: Optional[Dict[str, UserTier]] = None, **kwargs) -> "CascadeAgent":
        """
        Create CascadeAgent with smart defaults.

        Auto-detects available providers and creates optimal cascade.

        Args:
            tiers: Optional custom tiers
            **kwargs: Additional arguments for CascadeAgent (e.g., routing_strategy)
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
                    domains=["general"]
                ))
                logger.info("✓ Detected Ollama (local)")
        except:
            logger.debug("Ollama not detected")

        # Check vLLM (self-hosted)
        try:
            import httpx
            response = httpx.get("http://localhost:8000/v1/models", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    vllm_model = data["data"][0]["id"]
                    models.append(ModelConfig(
                        name=vllm_model,
                        provider="vllm",
                        base_url="http://localhost:8000/v1",
                        cost=0.0,
                        domains=["general"]
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
                domains=["general"]
            ))
            logger.info("✓ Detected Groq API key")

        # Check HuggingFace
        if os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN"):
            models.append(ModelConfig(
                name="codellama/CodeLlama-34b-Instruct-hf",
                provider="huggingface",
                cost=0.0,
                domains=["code"]
            ))
            logger.info("✓ Detected HuggingFace token")

        # Check Together.ai
        if os.getenv("TOGETHER_API_KEY"):
            models.append(ModelConfig(
                name="meta-llama/Llama-3-70b-chat-hf",
                provider="together",
                cost=0.0009,
                domains=["general"]
            ))
            logger.info("✓ Detected Together.ai API key")

        # Check OpenAI
        if os.getenv("OPENAI_API_KEY"):
            models.append(ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost=0.002,
                domains=["general"]
            ))
            models.append(ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                domains=["general"]
            ))
            logger.info("✓ Detected OpenAI API key")

        # Check Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(ModelConfig(
                name="claude-3-sonnet-20240229",
                provider="anthropic",
                cost=0.003,
                domains=["general"]
            ))
            logger.info("✓ Detected Anthropic API key")

        if not models:
            raise CascadeFlowError(
                "No providers detected. Please set at least one API key or run a local server."
            )

        logger.info(f"Created smart cascade with {len(models)} models")

        return cls(
            models=models,
            tiers=tiers,
            verbose=True,
            enable_caching=True,
            **kwargs  # ✅ NEW: Pass through additional kwargs
        )

    def add_tier(self, name: str, tier: UserTier):
        """Add or update a user tier."""
        self.tiers[name] = tier
        logger.info(f"Added tier '{name}'")

    def get_tier(self, name: str) -> Optional[UserTier]:
        """Get tier by name."""
        return self.tiers.get(name)

    def list_tiers(self) -> List[str]:
        """List all tier names."""
        return list(self.tiers.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        stats = {
            "models": len(self.models),
            "tiers": list(self.tiers.keys()),
            "workflows": list(self.workflows.keys()),
            **self.stats,
            "avg_cost": self.stats["total_cost"] / max(1, self.stats["total_queries"]),
            "cascade_rate": self.stats["total_cascades"] / max(1, self.stats["total_queries"]),
        }

        if self.complexity_detector:
            stats["complexity"] = self.complexity_detector.get_stats()

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        if self.callback_manager:
            stats["callbacks"] = self.callback_manager.get_stats()

        if self.speculative_cascades:
            stats["speculative"] = {
                key: cascade.get_stats()
                for key, cascade in self.speculative_cascades.items()
            }

        # ✅ NEW: Add semantic routing stats
        if self.semantic_router:
            stats["semantic_routing"] = self.semantic_router.get_stats()

        return stats