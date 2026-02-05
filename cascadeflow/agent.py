"""
cascadeflow Agent v2.5 - FIXED: Cost Calculation with Telemetry Integration
===========================================================================

✅ Phase 2A: PreRouter for complexity-based routing (routing/)
✅ Phase 2B: MetricsCollector for statistics tracking (telemetry/)
✅ Phase 2C: TerminalVisualConsumer for UI feedback (interface/)
✅ Phase 3: Tool Calling Support via ToolRouter (routing/)
✅ v2.4: Intelligent streaming module routing (tools vs text)
🆕 v2.5: CostCalculator integration - FIXES cost aggregation bug (Oct 20, 2025)

NEW in v2.5: Proper Cost Calculation
    - CostCalculator: Single source of truth for cost calculations
    - Fixes bug where cascaded queries only showed draft cost
    - Now correctly aggregates draft + verifier costs
    - Clean separation: agent orchestrates, calculator computes

Cost Calculation Flow:
    1. Agent executes query (cascade or direct)
    2. CostCalculator.calculate(spec_result) extracts costs
    3. Returns CostBreakdown with:
       - draft_cost: Individual model costs
       - verifier_cost: Verifier model cost (if called)
       - total_cost: Properly aggregated (draft + verifier)
       - cost_saved: Savings vs big-only approach
    4. Agent uses breakdown to build CascadeResult

Architecture Overview:
    1. PreRouter decides complexity-based routing (routing/)
    2. ToolRouter filters tool-capable models (routing/)
    3. Agent detects tools parameter
    4. IF tools → ToolStreamManager (streaming/tools.py)
       ELSE → StreamManager (streaming/base.py)
    5. CostCalculator computes costs from results (telemetry/) 🆕
    6. MetricsCollector tracks ALL statistics (telemetry/)
    7. TerminalVisualConsumer provides UI feedback (interface/)

Key Features:
    - Automatic streaming module selection (text vs tools)
    - Tool usage tracking in telemetry
    - Accurate cost calculation and aggregation 🆕
    - Full backward compatibility
    - Clean separation of concerns

Example:
    >>> agent = CascadeAgent(models=[cheap, expensive])
    >>> result = await agent.run("What is 2+2?")
    >>>
    >>> # Now shows correct costs!
    >>> print(f"Total: ${result.total_cost:.6f}")      # $0.001542 ✅
    >>> print(f"Draft: ${result.draft_cost:.6f}")       # $0.000042 ✅
    >>> print(f"Verifier: ${result.verifier_cost:.6f}") # $0.001500 ✅
"""

import logging
import sys
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Optional

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

if TYPE_CHECKING:
    from .core.batch import BatchResult
    from .core.batch_config import BatchConfig
    from .profiles import UserProfile

from .core.cascade import WholeResponseCascade

# Phase 2C: Interface module imports
from .interface import TerminalVisualConsumer
from .providers import PROVIDER_REGISTRY, get_available_providers
from .quality import QualityConfig

# Phase 3: Tool routing
# Phase 2A: Routing module imports
# Phase 3.2: Domain detection (NEW)
# Phase 4: Tool complexity routing (NEW - v19)
from .rules import RuleContext, RuleEngine
from .routing import (
    ComplexityRouter,
    DomainDetector,
    PreRouter,
    SemanticDomainDetector,
    ToolComplexityAnalyzer,
    ToolRouter,
    ToolRoutingDecision,
)
from .schema.config import CascadeConfig, ModelConfig, UserTier, WorkflowProfile
from .schema.domain_config import DomainConfig, get_builtin_domain_config
from .schema.exceptions import cascadeflowError
from .schema.result import CascadeResult
from .utils.messages import get_last_user_message, messages_to_prompt, normalize_messages

# Streaming imports - BOTH managers (v2.4 FIX)
from .streaming import StreamEvent, StreamEventType, StreamManager

# Phase 2B + v2.5: Telemetry module imports (with CostCalculator)
from .telemetry import CallbackManager, CostCalculator, MetricsCollector

logger = logging.getLogger(__name__)

# 🚀 NEW: Import ToolStreamManager for tool calling
try:
    from .streaming.tools import ToolStreamManager

    TOOL_STREAMING_AVAILABLE = True
except ImportError:
    TOOL_STREAMING_AVAILABLE = False
    logger.warning("ToolStreamManager not available - tool streaming disabled")


# ============================================================================
# AGENT v2.5 - WITH COST CALCULATOR INTEGRATION
# ============================================================================


class CascadeAgent:
    """
    Cascade agent with intelligent streaming module routing and proper cost calculation.

    🆕 v2.5 ENHANCEMENT: CostCalculator Integration

    Cost calculation is now delegated to the telemetry module:
    1. Agent executes query → gets SpeculativeResult
    2. CostCalculator.calculate() → extracts/computes costs
    3. Returns CostBreakdown with accurate aggregation
    4. Agent builds CascadeResult with correct costs

    This fixes the bug where cascaded queries only showed draft cost.

    🚀 v2.4 ARCHITECTURE: Smart Streaming Module Selection

    The agent intelligently routes to the correct streaming module:

    1. PreRouter decides complexity-based routing (routing/)
    2. ToolRouter filters tool-capable models (routing/)
    3. **Agent detects tools parameter**
    4. **IF tools → ToolStreamManager (streaming/tools.py)**
       **ELSE → StreamManager (streaming/base.py)**
    5. **CostCalculator computes costs (telemetry/)** 🆕
    6. MetricsCollector tracks statistics (telemetry/)
    7. TerminalVisualConsumer provides UI feedback (interface/)

    Module Integration:
        - routing.PreRouter: Complexity-based routing decisions
        - routing.ToolRouter: Tool capability filtering
        - telemetry.CostCalculator: Cost calculation (NEW) 🆕
        - telemetry.MetricsCollector: Comprehensive metrics tracking
        - interface.TerminalVisualConsumer: Terminal visual feedback
        - streaming.StreamManager: Text-only streaming wrapper
        - streaming.tools.ToolStreamManager: Tool call streaming wrapper

    THREE APIs for different use cases (all support tools):
    1. run() - Simple, returns result with full diagnostics
    2. run_streaming() - Streaming with visuals, auto-selects correct manager
    3. stream_events() - Async iterator, yields events (for custom UIs)
    """

    def __init__(
        self,
        models: list[ModelConfig],
        quality_config: Optional[QualityConfig] = None,
        quality: Optional[dict[str, Any]] = None,
        enable_cascade: bool = True,
        verbose: bool = False,
        # ========================================================================
        # 🆕 v2.6: Domain-Aware Routing
        # ========================================================================
        domain_configs: Optional[dict[str, DomainConfig]] = None,  # Per-domain cascade config
        enable_domain_detection: bool = False,  # Auto-detect query domain
        use_semantic_domains: bool = True,  # 🆕 Use ML-based semantic detection (hybrid)
        # ========================================================================
        # 🆕 v19: Tool Complexity Routing (Phase 1)
        # ========================================================================
        enable_tool_complexity_routing: bool = True,  # 🆕 v19: Route tool calls by complexity
        # ========================================================================
        # 🆕 v2.7: Factual-Risk Routing (Opt-in safety mode)
        # ========================================================================
        enable_factual_risk_routing: bool = False,
        # ========================================================================
        # 🆕 v2.8: Rule Engine (tiers, KPIs, domain routing)
        # ========================================================================
        rule_engine: Optional["RuleEngine"] = None,
        tenant_rules: Optional[dict[str, Any]] = None,
        channel_models: Optional[dict[str, list[str]]] = None,
        channel_failover: Optional[dict[str, str]] = None,
        # ========================================================================
        # 🔄 BACKWARDS COMPATIBILITY: v0.1.x parameters (DEPRECATED)
        # ========================================================================
        config: Optional[CascadeConfig] = None,  # DEPRECATED - use quality_config
        tiers: Optional[
            dict[str, UserTier]
        ] = None,  # DEPRECATED - tier system being re-implemented
        workflows: Optional[dict[str, WorkflowProfile]] = None,  # DEPRECATED - workflow system
        enable_caching: bool = False,  # DEPRECATED - caching system being re-implemented
        cache_size: int = 1000,  # DEPRECATED - caching system being re-implemented
        enable_callbacks: bool = True,  # DEPRECATED - callbacks now always enabled
    ):
        """
        Initialize cascade agent with dual streaming managers and cost calculator.

        Args:
            models: List of models (will be sorted by cost)
            quality_config: Quality validation config
            quality: Backwards-compatible quality config dict (e.g., {"threshold": 0.7})
            enable_cascade: Enable cascade system
            verbose: Enable verbose logging
            domain_configs: Optional dict mapping domain strings to DomainConfig
                           (e.g., {"code": DomainConfig(...), "medical": DomainConfig(...)})
            enable_domain_detection: Enable automatic domain detection for queries
            use_semantic_domains: Use ML-based semantic domain detection (hybrid mode).
                                 Leverages same embedding model as quality system.
            enable_factual_risk_routing: Route factual-risk prompts directly to verifier (opt-in)
            rule_engine: Optional RuleEngine instance for routing rules
            tenant_rules: Optional per-tenant routing overrides
            channel_models: Optional per-channel model allowlists
            channel_failover: Optional channel->failover mapping

        Deprecated Args (v0.1.x compatibility):
            config: Old CascadeConfig (use quality_config instead)
            tiers: User tier definitions (tier system being re-implemented)
            workflows: Workflow profiles (workflow system being re-implemented)
            enable_caching: Enable response caching (being re-implemented)
            cache_size: Cache size (being re-implemented)
            enable_callbacks: Enable callbacks (now always enabled)
        """
        if not models:
            raise cascadeflowError("At least one model is required")

        if quality_config is None and quality is not None:
            if isinstance(quality, QualityConfig):
                quality_config = quality
            elif isinstance(quality, dict):
                quality_config = QualityConfig.for_cascade()
                thresholds = quality.get("confidence_thresholds")
                threshold_value = quality.get("threshold")
                if isinstance(thresholds, dict):
                    quality_config.confidence_thresholds = thresholds
                elif threshold_value is not None:
                    quality_config.confidence_thresholds = {
                        key: float(threshold_value)
                        for key in quality_config.confidence_thresholds.keys()
                    }

        if len(models) < 2 and enable_cascade:
            logger.warning(
                f"Cascade requires 2+ models but got {len(models)}. " f"Disabling cascade."
            )
            enable_cascade = False

        # ========================================================================
        # 🔄 BACKWARDS COMPATIBILITY LAYER (v0.1.x → v2.5)
        # ========================================================================

        # Handle old 'config' parameter → quality_config mapping
        if config is not None and quality_config is None:
            logger.warning(
                "⚠️  DEPRECATION WARNING: Parameter 'config' (CascadeConfig) is deprecated.\n"
                "   Use 'quality_config' (QualityConfig) instead.\n"
                "   This parameter will be removed in v0.3.0.\n"
                "   Converting config to quality_config automatically..."
            )
            # Convert CascadeConfig to QualityConfig
            # QualityConfig takes confidence_thresholds (dict), not single value
            quality_config = QualityConfig.for_cascade()  # Use default cascade config
            # Note: CascadeConfig quality_threshold ignored - uses complexity-aware

        # Handle old 'tiers' parameter
        if tiers is not None:
            logger.warning(
                "⚠️  DEPRECATION WARNING: Parameter 'tiers' is deprecated.\n"
                "   The tier system is being re-implemented with TierAwareRouter.\n"
                "   This parameter will be removed in v0.3.0.\n"
                "   Tiers are now functional via TierAwareRouter."
            )
            self._legacy_tiers = tiers
            # Initialize TierAwareRouter (OPTIONAL - only if tiers provided)
            from .routing import TierAwareRouter

            self.tier_router = TierAwareRouter(
                tiers=tiers,
                models=sorted(models, key=lambda m: m.cost),  # Use models before self.models is set
                verbose=verbose,
            )
        else:
            self._legacy_tiers = None
            self.tier_router = None  # No tiers = no tier router

        # Handle old 'workflows' parameter
        if workflows is not None:
            logger.warning(
                "⚠️  DEPRECATION WARNING: Parameter 'workflows' is deprecated.\n"
                "   The workflow system is being replaced with domain strategies.\n"
                "   This parameter will be removed in v0.3.0.\n"
                "   For now, workflow definitions are stored but not actively used."
            )
            self._legacy_workflows = workflows
            # TODO: Convert to DomainCascadeStrategy when implemented
        else:
            self._legacy_workflows = None

        # Handle old 'enable_caching' parameter
        if enable_caching:
            logger.warning(
                "⚠️  DEPRECATION WARNING: Parameter 'enable_caching' is deprecated.\n"
                "   Caching support is being re-implemented in v0.2.1.\n"
                "   For now, caching is disabled."
            )
            # TODO: Re-implement ResponseCache in v0.2.1
            self._cache_enabled = False
            self._cache_size = cache_size
        else:
            self._cache_enabled = False
            self._cache_size = cache_size

        # Handle 'enable_callbacks' parameter - callbacks are now always enabled
        if not enable_callbacks:
            logger.warning(
                "⚠️  DEPRECATION WARNING: Callbacks are now always enabled in v2.5.\n"
                "   Parameter 'enable_callbacks=False' is ignored.\n"
                "   Use callback_manager.clear() to disable specific events."
            )

        # Sort models by cost (cheap → expensive)
        self.models = sorted(models, key=lambda m: m.cost)
        self.enable_cascade = enable_cascade
        self.verbose = verbose

        # Setup logging
        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

        # Use cascade-optimized config by default
        self.quality_config = quality_config or QualityConfig.for_cascade()

        # 🆕 v2.5: Always initialize CallbackManager (backwards compatibility)
        self.callback_manager = CallbackManager(verbose=verbose)

        # Initialize routers
        self.complexity_detector = ComplexityDetector()
        self.router = PreRouter(
            enable_cascade=enable_cascade,
            complexity_detector=self.complexity_detector,
            enable_factual_risk_routing=enable_factual_risk_routing,
            verbose=verbose,
        )

        # Initialize tool router
        self.tool_router = ToolRouter(models=self.models, verbose=verbose)

        # 🆕 v19: Initialize tool complexity router for intelligent tool call routing
        self.enable_tool_complexity_routing = enable_tool_complexity_routing
        if enable_tool_complexity_routing:
            self.tool_complexity_analyzer = ToolComplexityAnalyzer()
            self.tool_complexity_router = ComplexityRouter(
                analyzer=self.tool_complexity_analyzer,
                small_model=self.models[0].name,
                large_model=self.models[-1].name,
                verbose=verbose,
            )
            logger.info("Tool complexity routing: ENABLED (v19)")
        else:
            self.tool_complexity_analyzer = None
            self.tool_complexity_router = None

        # 🆕 v2.6: Initialize domain detection
        self.enable_domain_detection = enable_domain_detection
        self.use_semantic_domains = use_semantic_domains
        self.domain_configs = domain_configs or {}

        # 🆕 v2.6: Semantic domain detection with hybrid mode
        # Uses same embedding service as quality system for efficiency
        if enable_domain_detection:
            if use_semantic_domains:
                self.domain_detector = SemanticDomainDetector(
                    use_hybrid=True,  # Combines ML + rule-based for best accuracy
                    confidence_threshold=0.5,  # Lower threshold for hybrid mode
                )
                if self.domain_detector.is_available:
                    logger.info("Domain detection: SEMANTIC (hybrid ML + rules)")
                else:
                    logger.warning("Semantic domains unavailable, falling back to rule-based")
                    self.domain_detector = DomainDetector()
            else:
                self.domain_detector = DomainDetector()
                logger.info("Domain detection: RULE-BASED (keyword matching)")
        else:
            self.domain_detector = None

        # 🆕 v2.8: Rule engine for routing decisions (domain + tiers + KPIs)
        self.rule_engine = rule_engine or RuleEngine(
            enable_domain_routing=enable_domain_detection,
            tiers=self._legacy_tiers,
            workflows=self._legacy_workflows,
            tenant_rules=tenant_rules,
            channel_models=channel_models,
            channel_failover=channel_failover,
            verbose=verbose,
        )

        # Initialize telemetry collector
        self.telemetry = MetricsCollector(max_recent_results=100, verbose=verbose)

        # 🆕 v2.5: Initialize cost calculator
        self.cost_calculator = CostCalculator(
            drafter=self.models[0], verifier=self.models[-1], verbose=verbose
        )

        # Connect cost calculator to telemetry (optional)
        if hasattr(self.telemetry, "set_cost_calculator"):
            self.telemetry.set_cost_calculator(self.cost_calculator)

        # Initialize providers
        self.providers = self._init_providers()

        # Initialize cascade system with BOTH streaming managers
        if self.enable_cascade:
            self.cascade = WholeResponseCascade(
                drafter=self.models[0],
                verifier=self.models[-1],
                providers=self.providers,
                model_providers=self.model_providers,  # Pass model-specific providers
                quality_config=self.quality_config,
                verbose=verbose,
            )

            # 🚀 v2.4 FIX: Initialize BOTH streaming managers
            # Text-only streaming manager (base.py)
            self.text_streaming_manager = StreamManager(cascade=self.cascade, verbose=verbose)

            # Tool streaming manager (tools.py) if available
            if TOOL_STREAMING_AVAILABLE:
                self.tool_streaming_manager = ToolStreamManager(
                    cascade=self.cascade, verbose=verbose
                )
            else:
                self.tool_streaming_manager = None
                logger.warning("Tool streaming not available - tool calls will not stream")

            # Backward compatibility: default streaming_manager points to text
            self.streaming_manager = self.text_streaming_manager

            # Visual consumer from interface module
            self.visual_consumer = TerminalVisualConsumer(enable_visual=True, verbose=verbose)
        else:
            self.cascade = None
            self.text_streaming_manager = None
            self.tool_streaming_manager = None
            self.streaming_manager = None
            self.visual_consumer = None

        # Count tool-capable models
        tool_capable_count = sum(1 for m in self.models if getattr(m, "supports_tools", False))

        # Build compatibility status message
        compat_notes = []
        if self._legacy_tiers:
            compat_notes.append(f"tiers={len(self._legacy_tiers)} (stored, not yet active)")
        if self._legacy_workflows:
            compat_notes.append(f"workflows={len(self._legacy_workflows)} (stored, not yet active)")
        if self._cache_enabled:
            compat_notes.append("caching=requested (not yet implemented)")

        compat_status = f"\n  Legacy v0.1.x: {', '.join(compat_notes)}" if compat_notes else ""

        logger.info(
            f"CascadeAgent v2.5 initialized (Cost Calculator + Backwards Compatibility):\n"
            f"  Models: {len(models)} ({tool_capable_count} tool-capable)\n"
            f"  Drafter: {self.models[0].name} (${self.models[0].cost:.6f})\n"
            f"  Verifier: {self.models[-1].name} (${self.models[-1].cost:.6f})\n"
            f"  Quality: {self.quality_config.__class__.__name__}\n"
            f"  Cascade: {'enabled' if enable_cascade else 'disabled'}\n"
            f"  Router: PreRouter (complexity-based)\n"
            f"  ToolRouter: {'enabled' if tool_capable_count > 0 else 'no tool-capable models'}\n"
            f"  CostCalculator: enabled (telemetry/)\n"  # 🆕
            f"  CallbackManager: enabled (telemetry/)\n"  # 🆕 v2.5
            f"  Telemetry: MetricsCollector\n"
            f"  Interface: TerminalVisualConsumer\n"
            f"  Text Streaming: {'enabled' if self.text_streaming_manager else 'disabled'}\n"
            f"  Tool Streaming: {'enabled' if self.tool_streaming_manager else 'disabled'}"
            f"{compat_status}"
        )

    # ========================================================================
    # 🚀 v2.4: INTELLIGENT STREAMING MANAGER SELECTOR
    # ========================================================================

    def _get_streaming_manager(self, tools: Optional[list[dict]] = None):
        """
        Select correct streaming manager based on whether tools are present.

        This is the KEY FIX in v2.4:
        - IF tools present → Use ToolStreamManager (streaming/tools.py)
        - ELSE → Use StreamManager (streaming/base.py)

        Args:
            tools: List of tool definitions (if any)

        Returns:
            Appropriate streaming manager for the request

        Raises:
            cascadeflowError: If tools requested but ToolStreamManager unavailable
        """
        if tools:
            # Tools present - need ToolStreamManager
            if not self.tool_streaming_manager:
                raise cascadeflowError(
                    "Tool streaming requested but ToolStreamManager not available. "
                    "Check that streaming/tools.py exists and is properly configured."
                )

            if self.verbose:
                logger.info("Using ToolStreamManager for tool call streaming")

            return self.tool_streaming_manager
        else:
            # No tools - use text streaming manager
            if self.verbose:
                logger.info("Using StreamManager for text-only streaming")

            return self.text_streaming_manager

    def _apply_rule_model_constraints(
        self,
        available_models: list[ModelConfig],
        rule_decision: Optional["RuleDecision"],
    ) -> list[ModelConfig]:
        """
        Apply rule-driven model constraints (tier/workflow/KPI).

        Returns a filtered list while preserving original order.
        """
        if not rule_decision or not available_models:
            return available_models

        filtered = list(available_models)
        forced = rule_decision.forced_models or []
        allowed = rule_decision.allowed_models or []
        excluded = rule_decision.excluded_models or []

        if forced:
            filtered = [m for m in filtered if m.name in forced]
        elif allowed and "*" not in allowed:
            filtered = [m for m in filtered if m.name in allowed]

        if excluded:
            filtered = [m for m in filtered if m.name not in excluded]

        if not filtered:
            if self.verbose:
                logger.warning(
                    "Rule constraints filtered out all models; falling back to cheapest available."
                )
            # Fallback to cheapest model from original list
            return [sorted(available_models, key=lambda m: m.cost)[0]]

        if self.verbose and filtered != available_models:
            logger.info(
                f"Rule model constraints: {len(available_models)} → {len(filtered)} models. "
                f"Allowed: {[m.name for m in filtered]}"
            )

        return filtered

    # ========================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # ========================================================================

    @property
    def stats(self) -> dict[str, Any]:
        """Backward-compatible stats access."""
        return self.telemetry.stats

    @stats.setter
    def stats(self, value: dict[str, Any]):
        """Allow setting stats for testing purposes."""
        self.telemetry.stats = value

    @property
    def streaming_cascade(self):
        """Backward compatibility property."""
        return self.streaming_manager

    # ========================================================================
    # 🆕 v2.6: RUNTIME CONFIGURATION UPDATES
    # ========================================================================

    def update_quality_threshold(self, threshold: float) -> None:
        """
        Update quality threshold at runtime.

        Args:
            threshold: New quality threshold (0.0-1.0)

        Example:
            >>> agent.update_quality_threshold(0.85)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be 0.0-1.0, got {threshold}")

        if self.cascade:
            self.cascade.confidence_threshold = threshold
            logger.info(f"Updated quality threshold to {threshold}")

    def update_models(self, models: list[ModelConfig]) -> None:
        """
        Update model configuration at runtime.

        Args:
            models: New list of model configurations

        Example:
            >>> agent.update_models([
            ...     ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
            ...     ModelConfig(name='gpt-4o', provider='openai', cost=0.003),
            ... ])
        """
        if not models:
            raise ValueError("At least one model required")

        # Sort by cost
        self.models = sorted(models, key=lambda m: m.cost)

        # Reinitialize cascade if enabled
        if self.enable_cascade and len(self.models) >= 2:
            self._reinit_cascade()
            logger.info(f"Updated models: {[m.name for m in self.models]}")

    def update_domain_config(
        self,
        domain: str,
        config: "DomainConfig",
    ) -> None:
        """
        Update or add domain configuration at runtime.

        Args:
            domain: Domain name (e.g., "code", "medical")
            config: New DomainConfig for the domain

        Example:
            >>> agent.update_domain_config("code", DomainConfig(
            ...     drafter="gpt-4o-mini",
            ...     verifier="gpt-4o",
            ...     threshold=0.90,
            ...     temperature=0.1,
            ... ))
        """
        self.domain_configs[domain] = config
        logger.info(f"Updated domain config for '{domain}'")

    def enable_domain_routing(self, use_semantic: bool = True) -> None:
        """
        Enable domain detection at runtime.

        Args:
            use_semantic: Use ML-based semantic detection (default: True)
        """
        self.enable_domain_detection = True
        self.use_semantic_domains = use_semantic

        if use_semantic:
            self.domain_detector = SemanticDomainDetector(
                use_hybrid=True,
                confidence_threshold=0.5,
            )
            if not self.domain_detector.is_available:
                self.domain_detector = DomainDetector()
        else:
            self.domain_detector = DomainDetector()

        logger.info(f"Domain routing enabled (semantic={use_semantic})")

    def disable_domain_routing(self) -> None:
        """Disable domain detection at runtime."""
        self.enable_domain_detection = False
        self.domain_detector = None
        logger.info("Domain routing disabled")

    def get_config_snapshot(self) -> dict[str, Any]:
        """
        Get snapshot of current configuration.

        Returns:
            Dict with current configuration state
        """
        return {
            "models": [
                {"name": m.name, "provider": m.provider, "cost": m.cost} for m in self.models
            ],
            "enable_cascade": self.enable_cascade,
            "enable_domain_detection": self.enable_domain_detection,
            "use_semantic_domains": getattr(self, "use_semantic_domains", False),
            "domain_configs": {
                domain: {
                    "drafter": cfg.drafter,
                    "verifier": cfg.verifier,
                    "threshold": cfg.threshold,
                    "temperature": cfg.temperature,
                }
                for domain, cfg in self.domain_configs.items()
            },
            "quality_threshold": (self.cascade.confidence_threshold if self.cascade else None),
            "verbose": self.verbose,
        }

    def _reinit_cascade(self) -> None:
        """Reinitialize cascade with current configuration."""
        if len(self.models) < 2:
            self.cascade = None
            return

        drafter = self.models[0]
        verifier = self.models[-1]

        self.cascade = WholeResponseCascade(
            drafter=drafter,
            verifier=verifier,
            providers=self.providers,
            quality_config=self.quality_config,
            verbose=self.verbose,
            cost_calculator=self.cost_calculator,
        )

    def _init_providers(self) -> dict[str, Any]:
        """
        Initialize providers for all models.

        For multi-instance setups, creates separate provider instances for each model
        with model-specific base_url and api_key. For backwards compatibility, also
        maintains provider-type keys.
        """
        providers = {}
        model_providers = {}  # Model name -> provider instance

        # Create provider instance for each model with its specific config
        for model in self.models:
            if model.provider not in PROVIDER_REGISTRY:
                logger.warning(f"Unknown provider: {model.provider}")
                continue

            try:
                provider_class = PROVIDER_REGISTRY[model.provider]

                # Pass model-specific configuration to provider
                provider_kwargs = {}
                if model.api_key:
                    provider_kwargs["api_key"] = model.api_key
                if model.base_url:
                    provider_kwargs["base_url"] = model.base_url

                provider_instance = provider_class(**provider_kwargs)
                model_providers[model.name] = provider_instance

                # For backwards compatibility, also store by provider type
                # (use first instance of each provider type)
                if model.provider not in providers:
                    providers[model.provider] = provider_instance

                logger.debug(
                    f"Initialized {model.provider} provider for model {model.name}"
                    + (f" with base_url={model.base_url}" if model.base_url else "")
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize provider '{model.provider}' "
                    f"for model '{model.name}': {e}"
                )

        if not providers:
            raise cascadeflowError("No providers could be initialized. Check your API keys.")

        # Store model-to-provider mapping for multi-instance lookups
        self.model_providers = model_providers

        return providers

    def _get_provider(self, model: ModelConfig):
        """
        Get provider instance for a model.

        For multi-instance setups, returns the model-specific provider instance.
        Falls back to provider-type lookup for backwards compatibility.
        """
        # First try model-specific provider (for multi-instance setups)
        if hasattr(self, "model_providers") and model.name in self.model_providers:
            return self.model_providers[model.name]

        # Fallback to provider-type lookup (backwards compatibility)
        return self.providers[model.provider]

    def _normalize_messages(
        self, query: str, messages: Optional[list[dict[str, Any]]]
    ) -> tuple[str, Optional[list[dict[str, Any]]]]:
        if messages:
            normalized = normalize_messages(messages)
            query_text = messages_to_prompt(normalized)
            return query_text, normalized
        return query, None

    # ========================================================================
    # API 1: NON-STREAMING - WITH TOOL SUPPORT
    # ========================================================================

    async def run(
        self,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        complexity_hint: Optional[str] = None,
        force_direct: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        user_tier: Optional[str] = None,  # 🔄 OPTIONAL: v0.1.x backwards compatibility
        workflow: Optional[str] = None,
        kpi_flags: Optional[dict[str, Any]] = None,
        domain_hint: Optional[str] = None,
        domain_confidence_hint: Optional[float] = None,
        tenant_id: Optional[str] = None,
        channel: Optional[str] = None,
        **kwargs,
    ) -> CascadeResult:
        """
        Run query (NON-STREAMING) with comprehensive diagnostics and tool support.

        Args:
            query: User query
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            complexity_hint: Override complexity detection
            force_direct: Force direct routing
            tools: List of tools in universal format
            tool_choice: Control tool calling behavior
            messages: Optional multi-turn messages (role/content)
            user_tier: OPTIONAL - User tier for tier-based routing (v0.1.x compat)
            workflow: OPTIONAL - Workflow profile name (legacy)
            kpi_flags: OPTIONAL - KPI routing flags (risk/compliance, etc.)
            domain_hint: OPTIONAL - Override detected domain (OpenClaw pre-router)
            domain_confidence_hint: OPTIONAL - Confidence for domain_hint (0-1)
            tenant_id: OPTIONAL - Tenant identifier for routing overrides
            channel: OPTIONAL - Logical channel for model routing/failover
            **kwargs: Additional provider parameters

        Returns:
            CascadeResult with content, cost, latency, tool_calls, and full diagnostics
        """
        overall_start = time.time()
        timing_breakdown = {}
        query_text, normalized_messages = self._normalize_messages(query, messages)

        # Detect complexity
        complexity_start = time.time()

        complexity_metadata = {}

        if complexity_hint:
            try:
                complexity = QueryComplexity(complexity_hint.lower())
                complexity_confidence = 1.0
            except ValueError:
                complexity, complexity_confidence, complexity_metadata = (
                    self.complexity_detector.detect(query_text, return_metadata=True)
                )
        else:
            complexity, complexity_confidence, complexity_metadata = (
                self.complexity_detector.detect(query_text, return_metadata=True)
            )

        timing_breakdown["complexity_detection"] = (time.time() - complexity_start) * 1000

        if self.verbose:
            print(f"[Complexity: {complexity.value} (confidence: {complexity_confidence:.2f})]")
            print(f"[Detection time: {timing_breakdown['complexity_detection']:.1f}ms]")

        logger.info(
            f"Query complexity: {complexity.value} (confidence: {complexity_confidence:.2f})"
        )

        # 🆕 v2.6: Detect domain and get domain-specific config
        detected_domain: Optional[str] = None
        domain_confidence: float = 0.0
        domain_config: Optional[DomainConfig] = None

        if domain_hint:
            detected_domain = domain_hint
            domain_confidence = domain_confidence_hint if domain_confidence_hint is not None else 1.0
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )
            timing_breakdown["domain_detection"] = 0.0
        elif self.domain_detector and self.enable_domain_detection:
            domain_start = time.time()
            domain_result = self.domain_detector.detect_with_scores(query_text)
            detected_domain = domain_result.domain.value
            domain_confidence = domain_result.confidence
            timing_breakdown["domain_detection"] = (time.time() - domain_start) * 1000

            # Get domain-specific config (user-provided or builtin)
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )

            if self.verbose:
                print(f"[Domain: {detected_domain} (confidence: {domain_confidence:.2f})]")
                if domain_config:
                    print(
                        f"[Domain Config: drafter={domain_config.drafter}, "
                        f"verifier={domain_config.verifier}, threshold={domain_config.threshold}]"
                    )

            logger.info(f"Query domain: {detected_domain} (confidence: {domain_confidence:.2f})")

        # Resolve tier/workflow configs for rule engine
        tier_config = None
        if user_tier and self.tier_router:
            tier_config = self.tier_router.get_tier(user_tier)
            if tier_config is None:
                logger.warning(
                    f"Tier '{user_tier}' not found. "
                    f"Available tiers: {list(self._legacy_tiers.keys()) if self._legacy_tiers else []}. "
                    f"Ignoring tier parameter."
                )
        elif user_tier and not self.tier_router:
            logger.warning(
                f"user_tier='{user_tier}' specified but no tiers configured. "
                f"Ignoring tier parameter. To use tiers, initialize agent with: "
                f"CascadeAgent(models=[...], tiers=DEFAULT_TIERS)"
            )

        workflow_profile = None
        if workflow and self._legacy_workflows:
            workflow_profile = self._legacy_workflows.get(workflow)
            if workflow_profile is None:
                logger.warning(
                    f"workflow='{workflow}' specified but not found. "
                    f"Available workflows: {list(self._legacy_workflows.keys())}"
                )

        # Filter models by tool capability
        available_models = self.models
        tool_drafter = None
        tool_verifier = None

        if tools:
            tool_filter_result = self.tool_router.filter_tool_capable_models(
                tools=tools, available_models=self.models
            )
            available_models = tool_filter_result["models"]

            if self.verbose:
                n_avail = len(available_models)
                n_total = len(self.models)
                print(f"[Tool Filtering: {n_avail}/{n_total} models support tools]")

            logger.info(
                f"Tool filtering: {len(available_models)}/{len(self.models)} models capable. "
                f"Models: {[m.name for m in available_models]}"
            )

            # 🆕 Phase 5: Domain-aware tool routing
            if domain_config:
                tool_drafter, tool_verifier = self.tool_router.get_domain_tool_models(
                    domain_config=domain_config, available_models=available_models
                )
                if tool_drafter or tool_verifier:
                    d_name = tool_drafter.name if tool_drafter else "default"
                    v_name = tool_verifier.name if tool_verifier else "default"
                    logger.info(f"Domain tool models: drafter={d_name}, verifier={v_name}")

        # 🆕 v19: Tool Complexity Routing - Analyze tool call complexity
        tool_complexity_strategy = None
        tool_complexity_decision = None
        if tools and self.enable_tool_complexity_routing and self.tool_complexity_router:
            # Analyze tool call complexity on the latest user turn to avoid inflating
            # complexity from earlier context.
            tool_query_text = query_text
            if normalized_messages:
                last_user_message = get_last_user_message(normalized_messages)
                if last_user_message:
                    tool_query_text = last_user_message

            tool_complexity_strategy = self.tool_complexity_router.route_tool_call(
                query=tool_query_text,
                tools=tools,
                context=(
                    {"messages": normalized_messages, "has_domain": bool(domain_config)}
                    if normalized_messages
                    else None
                ),
            )

            # Store the routing decision
            tool_complexity_decision = tool_complexity_strategy.decision

            if self.verbose:
                print(
                    f"[Tool Complexity: {tool_complexity_strategy.complexity_level.value} "
                    f"(score: {tool_complexity_strategy.analysis.score:.1f})]"
                )
                route = "CASCADE" if tool_complexity_strategy.use_cascade else "DIRECT"
                decision_val = tool_complexity_strategy.decision.value
                print(f"[Tool Routing: {route} ({decision_val})]")

            logger.info(
                f"Tool complexity routing: {tool_complexity_strategy.complexity_level.value} → "
                f"{'CASCADE' if tool_complexity_strategy.use_cascade else 'DIRECT'}"
            )

        # Rule engine decision (domain/tiers/KPIs)
        has_multi_turn = bool(normalized_messages and len(normalized_messages) > 1)
        rule_decision = None
        if self.rule_engine:
            rule_context = RuleContext(
                query=query_text,
                complexity=complexity,
                complexity_confidence=complexity_confidence,
                detected_domain=detected_domain,
                domain_confidence=domain_confidence,
                domain_config=domain_config,
                has_tools=bool(tools),
                has_multi_turn=has_multi_turn,
                has_code=complexity_metadata.get("has_code", False),
                user_tier=user_tier,
                tier_config=tier_config,
                workflow_name=workflow,
                workflow_profile=workflow_profile,
                kpi_flags=kpi_flags,
                tenant_id=tenant_id,
                channel=channel,
            )
            rule_decision = self.rule_engine.decide(rule_context)

        if rule_decision:
            available_models = self._apply_rule_model_constraints(available_models, rule_decision)
            if self.verbose:
                logger.info(
                    "Rule decision (stream_events): %s (strategy=%s, confidence=%.2f)",
                    rule_decision.reason or "rule_engine",
                    rule_decision.routing_strategy.value
                    if rule_decision.routing_strategy
                    else "none",
                    rule_decision.confidence,
                )
            if self.verbose:
                logger.info(
                    "Rule decision (streaming): %s (strategy=%s, confidence=%.2f)",
                    rule_decision.reason or "rule_engine",
                    rule_decision.routing_strategy.value
                    if rule_decision.routing_strategy
                    else "none",
                    rule_decision.confidence,
                )
            if self.verbose:
                logger.info(
                    "Rule decision: %s (strategy=%s, confidence=%.2f)",
                    rule_decision.reason or "rule_engine",
                    rule_decision.routing_strategy.value
                    if rule_decision.routing_strategy
                    else "none",
                    rule_decision.confidence,
                )

        # Get routing decision (domain-aware)
        # Pass domain context so router can make domain-specific routing decisions
        routing_context = {
            "complexity": complexity,
            "complexity_confidence": complexity_confidence,
            "force_direct": force_direct,
            "available_models": available_models,
            "has_tools": bool(tools),
            "has_code": complexity_metadata.get("has_code", False),
            "has_multi_turn": has_multi_turn,
            # Domain context for domain-aware routing
            "detected_domain": detected_domain,
            "domain_config": domain_config,
            "domain_confidence": domain_confidence,
            "rule_decision": rule_decision,
            # 🆕 Phase 5: Domain-specific tool models
            "tool_drafter": tool_drafter,
            "tool_verifier": tool_verifier,
            # 🆕 v19: Tool complexity routing context
            "tool_complexity_strategy": tool_complexity_strategy,
            "tool_complexity_decision": tool_complexity_decision,
        }

        decision = await self.router.route(query_text, routing_context)
        use_cascade = decision.is_cascade()
        routing_strategy = "cascade" if use_cascade else "direct"
        routing_reason = decision.reason

        # 🆕 v19: Tool Complexity Routing Override
        # For tool calls, tool complexity takes precedence over text complexity
        # This enables: simple tool calls → cascade, complex tool calls → direct
        if tools and tool_complexity_decision is not None and self.enable_tool_complexity_routing:
            # TOOL_CASCADE means simple tool call → allow cascade (cheap model can handle)
            # TOOL_DIRECT_LARGE means complex tool call → force direct (need better model)
            if tool_complexity_decision == ToolRoutingDecision.TOOL_CASCADE:
                # Simple tool call - allow cascade (override text complexity if it said direct)
                if not use_cascade:
                    use_cascade = True
                    routing_strategy = "cascade"
                    level = tool_complexity_strategy.complexity_level.value
                    routing_reason = (
                        f"Tool complexity override: {level} tool call → cascade "
                        f"(simple tools can use cheap model)"
                    )
                    if self.verbose:
                        print("[Tool Routing Override: DIRECT → CASCADE]")
                        print("[Reason: Simple tool complexity allows cascade]")
            elif tool_complexity_decision == ToolRoutingDecision.TOOL_DIRECT_LARGE:
                # Complex tool call - force direct (override text complexity if it said cascade)
                if use_cascade:
                    use_cascade = False
                    routing_strategy = "direct"
                    level = tool_complexity_strategy.complexity_level.value
                    routing_reason = (
                        f"Tool complexity override: {level} tool call → direct "
                        f"(complex tools need better model)"
                    )
                    if self.verbose:
                        print("[Tool Routing Override: CASCADE → DIRECT]")
                        print("[Reason: Complex tool complexity requires direct]")

        if self.verbose:
            print(f"[Routing: {routing_strategy.upper()}]")
            print(f"[Reason: {routing_reason}]")
            print(f"[Confidence: {decision.confidence:.2f}]")

        # Execute
        # 🆕 v2.6: Apply domain-specific configuration if available
        effective_temperature = temperature
        effective_max_tokens = max_tokens
        effective_threshold = None
        quality_threshold_override = None

        if rule_decision and rule_decision.quality_threshold is not None:
            quality_threshold_override = rule_decision.quality_threshold

        if domain_config and domain_config.enabled:
            effective_temperature = domain_config.temperature
            effective_max_tokens = domain_config.max_tokens or max_tokens
            effective_threshold = domain_config.threshold
            # Domain config wins over tier/workflow thresholds
            quality_threshold_override = None
            if self.verbose:
                print(
                    f"[Applying domain config: temp={effective_temperature}, "
                    f"threshold={effective_threshold}]"
                )

        if use_cascade:
            result, exec_timing = await self._execute_cascade_with_timing(
                query_text,
                effective_max_tokens,
                effective_temperature,
                complexity,
                available_models,
                tools,
                tool_choice,
                domain_config=domain_config,  # 🆕 v2.6: Pass domain config
                quality_threshold_override=quality_threshold_override,
                messages=normalized_messages,
                **kwargs,
            )
            timing_breakdown.update(exec_timing)
        else:
            result, exec_timing = await self._execute_direct_with_timing(
                query_text,
                effective_max_tokens,
                effective_temperature,
                complexity,
                force_direct,
                available_models,
                tools,
                tool_choice,
                messages=normalized_messages,
                **kwargs,
            )
            timing_breakdown.update(exec_timing)

        total_latency = (time.time() - overall_start) * 1000

        if self.verbose:
            print(f"[Total latency: {total_latency:.1f}ms]")
            if hasattr(result, "tool_calls") and result.tool_calls:
                print(f"[Tool calls: {len(result.tool_calls)}]")

        # Record metrics
        self.telemetry.record(
            result=result,
            routing_strategy=routing_strategy,
            complexity=complexity.value,
            timing_breakdown=timing_breakdown,
            streaming=False,
            has_tools=bool(tools),
        )

        # Build result
        return self._build_cascade_result(
            spec_result=result,
            query=query_text,
            complexity=complexity.value,
            complexity_confidence=complexity_confidence,
            routing_strategy=routing_strategy,
            routing_reason=routing_reason,
            total_latency_ms=total_latency,
            timing_breakdown=timing_breakdown,
            tools=tools,
            streaming=False,
            # 🆕 v2.6: Domain detection info
            detected_domain=detected_domain,
            domain_confidence=domain_confidence,
            domain_config=domain_config,
            rule_decision=rule_decision,
            tenant_id=tenant_id,
            channel=channel,
        )

    # ========================================================================
    # API 2: STREAMING WITH VISUALS - WITH INTELLIGENT MANAGER SELECTION
    # ========================================================================

    async def run_streaming(
        self,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        complexity_hint: Optional[str] = None,
        force_direct: bool = False,
        enable_visual: bool = True,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        user_tier: Optional[str] = None,
        workflow: Optional[str] = None,
        kpi_flags: Optional[dict[str, Any]] = None,
        domain_hint: Optional[str] = None,
        domain_confidence_hint: Optional[float] = None,
        tenant_id: Optional[str] = None,
        channel: Optional[str] = None,
        **kwargs,
    ) -> CascadeResult:
        """
        Run query (STREAMING with visual feedback) with intelligent manager selection.

        🚀 v2.4 KEY FIX: This method now automatically selects the correct streaming manager:
        - IF tools present → Uses ToolStreamManager (streaming/tools.py)
        - ELSE → Uses StreamManager (streaming/base.py)

        Args:
            query: User query
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            complexity_hint: Override complexity detection
            force_direct: Force direct routing
            enable_visual: Show pulsing dot indicator
            tools: List of tools in universal format
            tool_choice: Control tool calling behavior
            messages: Optional multi-turn messages (role/content)
            user_tier: OPTIONAL - User tier for tier-based routing (v0.1.x compat)
            workflow: OPTIONAL - Workflow profile name (legacy)
            kpi_flags: OPTIONAL - KPI routing flags (risk/compliance, etc.)
            domain_hint: OPTIONAL - Override detected domain (OpenClaw pre-router)
            domain_confidence_hint: OPTIONAL - Confidence for domain_hint (0-1)
            tenant_id: OPTIONAL - Tenant identifier for routing overrides
            channel: OPTIONAL - Logical channel for model routing/failover
            **kwargs: Additional provider parameters

        Returns:
            CascadeResult with content, cost, latency, tool_calls, and full diagnostics
        """
        start_time = time.time()
        timing_breakdown = {}
        query_text, normalized_messages = self._normalize_messages(query, messages)

        # Detect complexity
        complexity_start = time.time()

        complexity_metadata = {}

        if complexity_hint:
            # Use hint if provided
            complexity = complexity_hint
            complexity_confidence = 1.0
        else:
            complexity, complexity_confidence, complexity_metadata = (
                self.complexity_detector.detect(query_text, return_metadata=True)
            )

        timing_breakdown["complexity_detection"] = (time.time() - complexity_start) * 1000

        # 🆕 v2.7: Detect domain and get domain-specific config for streaming
        detected_domain: Optional[str] = None
        domain_confidence: float = 0.0
        domain_config: Optional[DomainConfig] = None

        if domain_hint:
            detected_domain = domain_hint
            domain_confidence = domain_confidence_hint if domain_confidence_hint is not None else 1.0
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )
            timing_breakdown["domain_detection"] = 0.0
        elif self.domain_detector and self.enable_domain_detection:
            domain_start = time.time()
            domain_result = self.domain_detector.detect_with_scores(query_text)
            detected_domain = domain_result.domain.value
            domain_confidence = domain_result.confidence
            timing_breakdown["domain_detection"] = (time.time() - domain_start) * 1000

            # Get domain-specific config (user-provided or builtin)
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )

            logger.info(
                f"[Streaming] Query domain: {detected_domain} (confidence: {domain_confidence:.2f})"
            )

        # Resolve tier/workflow configs for rule engine
        tier_config = None
        if user_tier and self.tier_router:
            tier_config = self.tier_router.get_tier(user_tier)
            if tier_config is None:
                logger.warning(
                    f"Tier '{user_tier}' not found. "
                    f"Available tiers: {list(self._legacy_tiers.keys()) if self._legacy_tiers else []}. "
                    f"Ignoring tier parameter."
                )
        elif user_tier and not self.tier_router:
            logger.warning(
                f"user_tier='{user_tier}' specified but no tiers configured. "
                f"Ignoring tier parameter. To use tiers, initialize agent with: "
                f"CascadeAgent(models=[...], tiers=DEFAULT_TIERS)"
            )

        workflow_profile = None
        if workflow and self._legacy_workflows:
            workflow_profile = self._legacy_workflows.get(workflow)
            if workflow_profile is None:
                logger.warning(
                    f"workflow='{workflow}' specified but not found. "
                    f"Available workflows: {list(self._legacy_workflows.keys())}"
                )

        # Filter models by tool capability
        available_models = self.models
        tool_drafter = None
        tool_verifier = None

        if tools:
            tool_filter_result = self.tool_router.filter_tool_capable_models(
                tools=tools, available_models=self.models
            )
            available_models = tool_filter_result["models"]

            # 🆕 Phase 5: Domain-aware tool routing
            if domain_config:
                tool_drafter, tool_verifier = self.tool_router.get_domain_tool_models(
                    domain_config=domain_config, available_models=available_models
                )

        # Rule engine decision (domain/tiers/KPIs)
        has_multi_turn = bool(normalized_messages and len(normalized_messages) > 1)
        rule_decision = None
        if self.rule_engine:
            rule_context = RuleContext(
                query=query_text,
                complexity=complexity,
                complexity_confidence=complexity_confidence,
                detected_domain=detected_domain,
                domain_confidence=domain_confidence,
                domain_config=domain_config,
                has_tools=bool(tools),
                has_multi_turn=has_multi_turn,
                has_code=complexity_metadata.get("has_code", False),
                user_tier=user_tier,
                tier_config=tier_config,
                workflow_name=workflow,
                workflow_profile=workflow_profile,
                kpi_flags=kpi_flags,
                tenant_id=tenant_id,
                channel=channel,
            )
            rule_decision = self.rule_engine.decide(rule_context)

        if rule_decision:
            available_models = self._apply_rule_model_constraints(available_models, rule_decision)

        # Get routing decision (domain-aware routing for streaming)
        routing_context = {
            "complexity": complexity,
            "complexity_confidence": complexity_confidence,
            "force_direct": force_direct,
            "available_models": available_models,
            "has_tools": bool(tools),
            "has_code": complexity_metadata.get("has_code", False),
            "has_multi_turn": has_multi_turn,
            # Domain context for domain-aware routing
            "detected_domain": detected_domain,
            "domain_config": domain_config,
            "domain_confidence": domain_confidence,
            "rule_decision": rule_decision,
            # 🆕 Phase 5: Domain-specific tool models
            "tool_drafter": tool_drafter,
            "tool_verifier": tool_verifier,
        }

        decision = await self.router.route(query_text, routing_context)
        use_cascade = decision.is_cascade()
        routing_strategy = "cascade" if use_cascade else "direct"
        routing_reason = decision.reason

        # 🚀 v2.4 KEY FIX: Select correct streaming manager based on tools
        streaming_manager = self._get_streaming_manager(tools)

        # Stream execution using selected manager
        if use_cascade and streaming_manager:
            consumer = self.visual_consumer if enable_visual else self._get_silent_consumer()
            result_data = await consumer.consume(
                streaming_manager=streaming_manager,  # ← Uses correct manager!
                query=query_text,
                max_tokens=max_tokens,
                temperature=temperature,
                complexity=complexity.value,
                routing_strategy=routing_strategy,
                is_direct_route=False,
                tools=tools,
                tool_choice=tool_choice,
                messages=normalized_messages,
                **kwargs,
            )
            result = self._dict_to_result(result_data)
            if "timing" in result_data:
                timing_breakdown.update(result_data["timing"])
        else:
            if streaming_manager:
                consumer = self.visual_consumer if enable_visual else self._get_silent_consumer()
                result_data = await consumer.consume(
                    streaming_manager=streaming_manager,  # ← Uses correct manager!
                    query=query_text,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    complexity=complexity.value,
                    routing_strategy=routing_strategy,
                    is_direct_route=True,
                    tools=tools,
                    tool_choice=tool_choice,
                    messages=normalized_messages,
                    **kwargs,
                )
                result = self._dict_to_result(result_data)
                if "timing" in result_data:
                    timing_breakdown.update(result_data["timing"])
            else:
                result, exec_timing = await self._stream_direct_with_timing(
                    query_text,
                    max_tokens,
                    temperature,
                    complexity,
                    force_direct,
                    enable_visual,
                    available_models,
                    tools,
                    tool_choice,
                    messages=normalized_messages,
                    **kwargs,
                )
                timing_breakdown.update(exec_timing)

        total_latency_ms = (time.time() - start_time) * 1000

        # Record metrics
        self.telemetry.record(
            result=result,
            routing_strategy=routing_strategy,
            complexity=complexity.value,
            timing_breakdown=timing_breakdown,
            streaming=True,
            has_tools=bool(tools),
        )

        # Build result
        return self._build_cascade_result(
            spec_result=result,
            query=query_text,
            complexity=complexity.value,
            complexity_confidence=complexity_confidence,
            routing_strategy=routing_strategy,
            routing_reason=routing_reason,
            total_latency_ms=total_latency_ms,
            timing_breakdown=timing_breakdown,
            tools=tools,
            streaming=True,
            rule_decision=rule_decision,
            tenant_id=tenant_id,
            channel=channel,
        )

    # ========================================================================
    # API 3: ASYNC ITERATOR - WITH INTELLIGENT MANAGER SELECTION
    # ========================================================================

    async def stream_events(
        self,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        complexity_hint: Optional[str] = None,
        force_direct: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        user_tier: Optional[str] = None,
        workflow: Optional[str] = None,
        kpi_flags: Optional[dict[str, Any]] = None,
        domain_hint: Optional[str] = None,
        domain_confidence_hint: Optional[float] = None,
        tenant_id: Optional[str] = None,
        channel: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream events as async iterator with intelligent manager selection.

        🚀 v2.4 KEY FIX: Automatically selects correct streaming manager based on tools.

        Args:
            query: User query
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            complexity_hint: Override complexity detection
            force_direct: Force direct routing
            tools: List of tools in universal format
            tool_choice: Control tool calling behavior
            messages: Optional multi-turn messages (role/content)
            user_tier: OPTIONAL - User tier for tier-based routing (v0.1.x compat)
            workflow: OPTIONAL - Workflow profile name (legacy)
            kpi_flags: OPTIONAL - KPI routing flags (risk/compliance, etc.)
            domain_hint: OPTIONAL - Override detected domain (OpenClaw pre-router)
            domain_confidence_hint: OPTIONAL - Confidence for domain_hint (0-1)
            tenant_id: OPTIONAL - Tenant identifier for routing overrides
            channel: OPTIONAL - Logical channel for model routing/failover
            **kwargs: Additional provider parameters

        Yields:
            StreamEvent objects with type, content, and data
        """
        # Detect complexity
        query_text, normalized_messages = self._normalize_messages(query, messages)
        complexity_metadata = {}
        if complexity_hint:
            try:
                complexity = QueryComplexity(complexity_hint.lower())
                complexity_confidence = 1.0
            except ValueError:
                complexity, complexity_confidence, complexity_metadata = (
                    self.complexity_detector.detect(query_text, return_metadata=True)
                )
        else:
            complexity, complexity_confidence, complexity_metadata = (
                self.complexity_detector.detect(query_text, return_metadata=True)
            )

        # 🆕 v2.7: Detect domain and get domain-specific config for stream_events
        detected_domain: Optional[str] = None
        domain_confidence: float = 0.0
        domain_config: Optional[DomainConfig] = None

        if domain_hint:
            detected_domain = domain_hint
            domain_confidence = domain_confidence_hint if domain_confidence_hint is not None else 1.0
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )
        elif self.domain_detector and self.enable_domain_detection:
            domain_result = self.domain_detector.detect_with_scores(query_text)
            detected_domain = domain_result.domain.value
            domain_confidence = domain_result.confidence

            # Get domain-specific config (user-provided or builtin)
            domain_config = self.domain_configs.get(detected_domain) or get_builtin_domain_config(
                detected_domain
            )

            logger.info(
                f"[StreamEvents] Query domain: {detected_domain} "
                f"(confidence: {domain_confidence:.2f})"
            )

        # Resolve tier/workflow configs for rule engine
        tier_config = None
        if user_tier and self.tier_router:
            tier_config = self.tier_router.get_tier(user_tier)
            if tier_config is None:
                logger.warning(
                    f"Tier '{user_tier}' not found. "
                    f"Available tiers: {list(self._legacy_tiers.keys()) if self._legacy_tiers else []}. "
                    f"Ignoring tier parameter."
                )
        elif user_tier and not self.tier_router:
            logger.warning(
                f"user_tier='{user_tier}' specified but no tiers configured. "
                f"Ignoring tier parameter. To use tiers, initialize agent with: "
                f"CascadeAgent(models=[...], tiers=DEFAULT_TIERS)"
            )

        workflow_profile = None
        if workflow and self._legacy_workflows:
            workflow_profile = self._legacy_workflows.get(workflow)
            if workflow_profile is None:
                logger.warning(
                    f"workflow='{workflow}' specified but not found. "
                    f"Available workflows: {list(self._legacy_workflows.keys())}"
                )

        # Filter models by tool capability
        available_models = self.models
        tool_drafter = None
        tool_verifier = None

        if tools:
            tool_filter_result = self.tool_router.filter_tool_capable_models(
                tools=tools, available_models=self.models
            )
            available_models = tool_filter_result["models"]

            # 🆕 Phase 5: Domain-aware tool routing
            if domain_config:
                tool_drafter, tool_verifier = self.tool_router.get_domain_tool_models(
                    domain_config=domain_config, available_models=available_models
                )

        # Rule engine decision (domain/tiers/KPIs)
        has_multi_turn = bool(normalized_messages and len(normalized_messages) > 1)
        rule_decision = None
        if self.rule_engine:
            rule_context = RuleContext(
                query=query_text,
                complexity=complexity,
                complexity_confidence=complexity_confidence,
                detected_domain=detected_domain,
                domain_confidence=domain_confidence,
                domain_config=domain_config,
                has_tools=bool(tools),
                has_multi_turn=has_multi_turn,
                has_code=complexity_metadata.get("has_code", False),
                user_tier=user_tier,
                tier_config=tier_config,
                workflow_name=workflow,
                workflow_profile=workflow_profile,
                kpi_flags=kpi_flags,
                tenant_id=tenant_id,
                channel=channel,
            )
            rule_decision = self.rule_engine.decide(rule_context)

        if rule_decision:
            available_models = self._apply_rule_model_constraints(available_models, rule_decision)

        # Get routing decision (domain-aware routing for stream_events)
        routing_context = {
            "complexity": complexity,
            "complexity_confidence": complexity_confidence,
            "force_direct": force_direct,
            "available_models": available_models,
            "has_tools": bool(tools),
            "has_code": complexity_metadata.get("has_code", False),
            "has_multi_turn": has_multi_turn,
            # Domain context for domain-aware routing
            "detected_domain": detected_domain,
            "domain_config": domain_config,
            "domain_confidence": domain_confidence,
            "rule_decision": rule_decision,
            # 🆕 Phase 5: Domain-specific tool models
            "tool_drafter": tool_drafter,
            "tool_verifier": tool_verifier,
        }

        decision = await self.router.route(query_text, routing_context)
        use_cascade = decision.is_cascade()
        routing_strategy = "cascade" if use_cascade else "direct"

        # 🚀 v2.4 KEY FIX: Select correct streaming manager
        streaming_manager = self._get_streaming_manager(tools)

        # Yield events from selected manager
        if use_cascade and streaming_manager:
            async for event in streaming_manager.stream(
                query=query_text,
                max_tokens=max_tokens,
                temperature=temperature,
                complexity=complexity.value,
                routing_strategy=routing_strategy,
                is_direct_route=False,
                tools=tools,
                tool_choice=tool_choice,
                messages=normalized_messages,
                **kwargs,
            ):
                yield event
        else:
            if streaming_manager:
                async for event in streaming_manager.stream(
                    query=query_text,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    complexity=complexity.value,
                    routing_strategy=routing_strategy,
                    is_direct_route=True,
                    tools=tools,
                    tool_choice=tool_choice,
                    messages=normalized_messages,
                    **kwargs,
                ):
                    yield event
            else:
                # Fallback for manual streaming
                best_model = available_models[-1] if available_models else self.models[-1]
                provider = self._get_provider(best_model)

                yield StreamEvent(
                    type=StreamEventType.ROUTING,
                    content="",
                    data={
                        "strategy": "direct",
                        "complexity": complexity.value,
                        "model": best_model.name,
                        "has_tools": bool(tools),
                    },
                )

                chunks = []
                start_time = time.time()

                if hasattr(provider, "stream"):
                    async for chunk in provider.stream(
                        model=best_model.name,
                        prompt=query_text,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    ):
                        chunks.append(chunk)
                        yield StreamEvent(
                            type=StreamEventType.CHUNK,
                            content=chunk,
                            data={"model": best_model.name, "phase": "direct"},
                        )
                else:
                    response = await provider.complete(
                        model=best_model.name,
                        prompt=query_text,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    )
                    chunks = [response.content]

                    if hasattr(response, "tool_calls") and response.tool_calls:
                        yield StreamEvent(
                            type=StreamEventType.METADATA,
                            content="",
                            data={"tool_calls": response.tool_calls},
                        )

                    yield StreamEvent(
                        type=StreamEventType.CHUNK,
                        content=response.content,
                        data={"model": best_model.name, "phase": "direct"},
                    )

                content = "".join(chunks)
                latency_ms = (time.time() - start_time) * 1000
                tokens_used = len(content.split()) * 1.3
                cost = best_model.cost * (tokens_used / 1000)

                yield StreamEvent(
                    type=StreamEventType.COMPLETE,
                    content="",
                    data={
                        "result": {
                            "content": content,
                            "model_used": best_model.name,
                            "total_cost": cost,
                            "latency_ms": latency_ms,
                            "draft_accepted": None,
                            "routing_strategy": "direct",
                            "complexity": complexity.value,
                            "has_tools": bool(tools),
                        }
                    },
                )

        # Basic telemetry recording
        self.telemetry.stats["total_queries"] += 1
        self.telemetry.stats["streaming_used"] += 1
        if tools:
            if "tool_queries" not in self.telemetry.stats:
                self.telemetry.stats["tool_queries"] = 0
            self.telemetry.stats["tool_queries"] += 1

    async def stream(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream responses with real-time events.

        This is an alias for stream_events() with a simpler interface that matches
        the documented API. Use this method for most streaming needs.

        Args:
            prompt: User query or prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: System prompt override (not used in streaming yet)
            tools: List of tools in universal format
            **kwargs: Additional parameters passed to stream_events()

        Yields:
            StreamEvent objects with incremental content

        Example:
            ```python
            async for event in agent.stream("Tell me a story"):
                if event.type == StreamEventType.CHUNK:
                    print(event.content, end="", flush=True)
                elif event.type == StreamEventType.COMPLETE:
                    print(f"\\nCost: ${event.data.get('total_cost', 0):.6f}")
            ```
        """
        # Set defaults
        if max_tokens is None:
            max_tokens = 100
        if temperature is None:
            temperature = 0.7

        # Delegate to stream_events
        async for event in self.stream_events(
            query=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            **kwargs,
        ):
            yield event

    # ========================================================================
    # EXECUTION METHODS - WITH TOOL SUPPORT
    # ========================================================================

    async def _execute_cascade_with_timing(
        self,
        query,
        max_tokens,
        temperature,
        complexity,
        available_models,
        tools,
        tool_choice,
        domain_config: Optional[DomainConfig] = None,
        quality_threshold_override: Optional[float] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ):
        """
        Execute cascade with detailed timing tracking and tool support.

        🆕 v2.6: Supports domain-specific drafter/verifier selection.
        """
        # Use filtered models if available
        drafter = available_models[0] if available_models else self.models[0]
        verifier = available_models[-1] if available_models else self.models[-1]

        # 🆕 v2.6: Apply domain-specific drafter/verifier if configured
        if domain_config and domain_config.enabled:
            # Try to find domain-specific drafter model
            domain_drafter_name = (
                domain_config.drafter
                if isinstance(domain_config.drafter, str)
                else domain_config.drafter.name if hasattr(domain_config.drafter, "name") else None
            )
            domain_verifier_name = (
                domain_config.verifier
                if isinstance(domain_config.verifier, str)
                else (
                    domain_config.verifier.name if hasattr(domain_config.verifier, "name") else None
                )
            )

            # Find matching models from available models
            if domain_drafter_name:
                for model in available_models:
                    if model.name == domain_drafter_name or domain_drafter_name in model.name:
                        drafter = model
                        logger.info(f"Using domain-specific drafter: {drafter.name}")
                        break

            if domain_verifier_name:
                for model in available_models:
                    if model.name == domain_verifier_name or domain_verifier_name in model.name:
                        verifier = model
                        logger.info(f"Using domain-specific verifier: {verifier.name}")
                        break

        logger.info(f"Routing to cascade: {drafter.name} → {verifier.name}")
        if tools:
            logger.info(f"Tool calling enabled with {len(tools)} tools")

        cascade_start = time.time()

        # 🆕 v2.6: Pass domain-specific or rule-based quality threshold if configured
        cascade_kwargs = dict(kwargs)
        if quality_threshold_override is not None:
            cascade_kwargs["quality_threshold"] = quality_threshold_override
            if self.verbose:
                logger.info(
                    f"Using rule-based quality threshold: {quality_threshold_override}"
                )
        elif domain_config and domain_config.threshold:
            cascade_kwargs["quality_threshold"] = domain_config.threshold
            if self.verbose:
                logger.info(f"Using domain-specific quality threshold: {domain_config.threshold}")

        # Pass tools to cascade execution
        result = await self.cascade.execute(
            query=query,
            max_tokens=max_tokens,
            temperature=temperature,
            complexity=complexity.value,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
            **cascade_kwargs,
        )
        cascade_total = (time.time() - cascade_start) * 1000

        # Extract timing from cascade metadata
        timing = {}
        if hasattr(result, "metadata") and result.metadata:
            timing["draft_generation"] = result.metadata.get("draft_latency_ms", 0)
            timing["quality_verification"] = result.metadata.get("quality_check_ms", 0)
            timing["verifier_generation"] = result.metadata.get("verifier_latency_ms", 0)
            timing["cascade_overhead"] = result.metadata.get("cascade_overhead_ms", 0)
        else:
            timing["cascade_total"] = cascade_total

        if self.verbose:
            print(f"[Draft generation: {timing.get('draft_generation', 0):.1f}ms]")
            print(f"[Quality check: {timing.get('quality_verification', 0):.1f}ms]")
            if timing.get("verifier_generation", 0) > 0:
                print(f"[Verifier generation: {timing['verifier_generation']:.1f}ms]")
            if timing.get("cascade_overhead", 0) > 0:
                print(f"[Cascade overhead: {timing['cascade_overhead']:.1f}ms]")

        return result, timing

    async def _execute_direct_with_timing(
        self,
        query,
        max_tokens,
        temperature,
        complexity,
        force_direct,
        available_models,
        tools,
        tool_choice,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ):
        """Execute direct routing with detailed timing and tool support."""
        best_model = available_models[-1] if available_models else self.models[-1]
        provider = self._get_provider(best_model)
        reason = (
            "Forced direct routing"
            if force_direct
            else f"Complexity {complexity.value} requires best model"
        )

        logger.info(f"Routing directly to: {best_model.name} ({reason})")
        if tools:
            logger.info(f"Tool calling enabled with {len(tools)} tools")

        direct_start = time.time()
        if tools and hasattr(provider, "complete_with_tools"):
            tool_messages = messages or [{"role": "user", "content": query}]
            response = await provider.complete_with_tools(
                messages=tool_messages,
                tools=tools,
                tool_choice=tool_choice,
                model=best_model.name,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        else:
            prompt = messages_to_prompt(messages) if messages else query
            response = await provider.complete(
                model=best_model.name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs,
            )
        direct_latency = (time.time() - direct_start) * 1000

        tokens_used = response.tokens_used if hasattr(response, "tokens_used") else max_tokens
        cost = best_model.cost * (tokens_used / 1000)

        result = self._create_direct_result(
            response.content,
            best_model.name,
            cost,
            direct_latency,
            reason,
            tool_calls=getattr(response, "tool_calls", None),
        )

        timing = {
            "direct_generation": direct_latency,
            "draft_generation": 0,
            "quality_verification": 0,
            "verifier_generation": 0,
            "cascade_overhead": 0,
        }

        return result, timing

    async def _stream_direct_with_timing(
        self,
        query,
        max_tokens,
        temperature,
        complexity,
        force_direct,
        enable_visual,
        available_models,
        tools,
        tool_choice,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ):
        """Stream directly from best model with timing tracking and tool support."""
        best_model = available_models[-1] if available_models else self.models[-1]
        provider = self._get_provider(best_model)
        reason = (
            "Forced direct routing"
            if force_direct
            else f"Complexity {complexity.value} requires best model"
        )

        logger.info(f"Streaming directly from: {best_model.name} ({reason})")
        if tools:
            logger.info(f"Tool calling enabled with {len(tools)} tools")

        visual = self._create_visual_indicator(enable_visual)
        chunks = []
        start_time = time.time()
        tool_calls = None

        if tools and hasattr(provider, "stream_with_tools"):
            visual.show()
            try:
                tool_messages = messages or [{"role": "user", "content": query}]
                async for chunk in provider.stream_with_tools(
                    messages=tool_messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    model=best_model.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                ):
                    print(chunk, end="", flush=True)
                    chunks.append(chunk)
                visual.complete()
                visual.clear()
                print()
                content = "".join(chunks)
            except Exception as e:
                logger.error(f"Streaming failed: {e}")
                visual.clear()
                raise
        elif hasattr(provider, "stream"):
            visual.show()
            try:
                prompt = messages_to_prompt(messages) if messages else query
                async for chunk in provider.stream(
                    model=best_model.name,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                ):
                    print(chunk, end="", flush=True)
                    chunks.append(chunk)
                visual.complete()
                visual.clear()
                print()
                content = "".join(chunks)
            except Exception as e:
                logger.error(f"Streaming failed: {e}")
                visual.clear()
                raise
        else:
            if tools and hasattr(provider, "complete_with_tools"):
                tool_messages = messages or [{"role": "user", "content": query}]
                response = await provider.complete_with_tools(
                    messages=tool_messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    model=best_model.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
            else:
                prompt = messages_to_prompt(messages) if messages else query
                response = await provider.complete(
                    model=best_model.name,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                )
            content = response.content
            tool_calls = getattr(response, "tool_calls", None)
            print(content)

        latency_ms = (time.time() - start_time) * 1000
        tokens_used = len(content.split()) * 1.3
        cost = best_model.cost * (tokens_used / 1000)

        result = self._create_direct_result(
            content, best_model.name, cost, latency_ms, reason, tool_calls=tool_calls
        )

        timing = {
            "direct_generation": latency_ms,
            "draft_generation": 0,
            "quality_verification": 0,
            "verifier_generation": 0,
            "cascade_overhead": 0,
        }

        return result, timing

    # ========================================================================
    # RESULT BUILDING - WITH COST CALCULATOR INTEGRATION (v2.5 FIX)
    # ========================================================================

    def _build_cascade_result(
        self,
        spec_result: Any,
        query: str,
        complexity: str,
        complexity_confidence: float,
        routing_strategy: str,
        routing_reason: str,
        total_latency_ms: float,
        timing_breakdown: dict[str, float],
        tools: Optional[list[dict]] = None,
        streaming: bool = False,
        # 🆕 v2.6: Domain detection info
        detected_domain: Optional[str] = None,
        domain_confidence: float = 0.0,
        domain_config: Optional[DomainConfig] = None,
        rule_decision: Optional["RuleDecision"] = None,
        tenant_id: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> CascadeResult:
        """
        Build comprehensive cascade result with ALL diagnostic metadata and tool calls.

        🆕 v2.5 ENHANCEMENT: Now uses CostCalculator for accurate cost aggregation.
        This fixes the bug where cascaded queries only showed draft cost.

        🆕 v2.6 ENHANCEMENT: Includes domain detection metadata.
        """
        # Extract ALL diagnostic information from metadata
        quality_score = None
        quality_threshold = None
        quality_check_passed = None
        rejection_reason = None
        draft_response = None
        verifier_response = None
        response_length = None
        response_word_count = None
        tool_calls = None

        if hasattr(spec_result, "metadata") and spec_result.metadata:
            quality_score = spec_result.metadata.get("quality_score")
            quality_threshold = spec_result.metadata.get("quality_threshold")
            quality_check_passed = spec_result.metadata.get("quality_check_passed")
            rejection_reason = spec_result.metadata.get("rejection_reason")
            draft_response = spec_result.metadata.get("draft_response")
            verifier_response = spec_result.metadata.get("verifier_response")
            response_length = spec_result.metadata.get("response_length")
            response_word_count = spec_result.metadata.get("response_word_count")
            tool_calls = spec_result.metadata.get("tool_calls")

        # Also check for tool_calls directly on result
        if not tool_calls and hasattr(spec_result, "tool_calls"):
            tool_calls = spec_result.tool_calls

        # Fallback to calculation if not in metadata
        if response_length is None:
            response_length = len(spec_result.content)
        if response_word_count is None:
            response_word_count = len(spec_result.content.split())

        # 🆕 v2.5: Determine cost breakdown using CostCalculator
        use_cascade = routing_strategy == "cascade"
        draft_accepted_value = spec_result.draft_accepted if use_cascade else False
        if use_cascade and quality_check_passed is not None:
            if draft_accepted_value != quality_check_passed:
                logger.warning(
                    "Draft acceptance mismatch detected; "
                    "aligning draft_accepted with quality_check_passed."
                )
            draft_accepted_value = quality_check_passed

        if use_cascade:
            metadata_costs = None
            if hasattr(spec_result, "metadata") and spec_result.metadata:
                metadata = spec_result.metadata
                if any(
                    key in metadata
                    for key in ("drafter_cost", "draft_cost", "verifier_cost", "cost_saved")
                ):
                    metadata_costs = {
                        "draft_cost": metadata.get("drafter_cost", metadata.get("draft_cost", 0.0)),
                        "verifier_cost": metadata.get("verifier_cost", 0.0),
                        "total_cost": metadata.get("total_cost", spec_result.total_cost),
                        "cost_saved": metadata.get("cost_saved", 0.0),
                    }

            # Use CostCalculator for accurate breakdown.
            try:
                cost_breakdown = self.cost_calculator.calculate(spec_result, query_text=query)

                draft_cost = cost_breakdown.draft_cost
                verifier_cost = cost_breakdown.verifier_cost
                total_cost = cost_breakdown.total_cost  # ✅ PROPERLY AGGREGATED!
                cost_saved = cost_breakdown.cost_saved

                if metadata_costs and total_cost == 0.0 and metadata_costs["total_cost"] > 0.0:
                    draft_cost = metadata_costs["draft_cost"]
                    verifier_cost = metadata_costs["verifier_cost"]
                    total_cost = metadata_costs["total_cost"]
                    cost_saved = metadata_costs["cost_saved"]

                if self.verbose:
                    logger.debug(
                        f"Cost breakdown: draft=${draft_cost:.6f}, "
                        f"verifier=${verifier_cost:.6f}, "
                        f"total=${total_cost:.6f} "
                        f"(accepted={spec_result.draft_accepted})"
                    )
            except Exception as e:
                # Fallback to metadata or old method if calculator fails
                logger.warning(f"CostCalculator failed, using fallback: {e}")
                if metadata_costs:
                    draft_cost = metadata_costs["draft_cost"]
                    verifier_cost = metadata_costs["verifier_cost"]
                    total_cost = metadata_costs["total_cost"]
                    cost_saved = metadata_costs["cost_saved"]
                else:
                    if spec_result.draft_accepted:
                        draft_cost = spec_result.total_cost
                        verifier_cost = 0.0
                        total_cost = draft_cost
                    else:
                        draft_cost = (
                            spec_result.metadata.get("drafter_cost", self.models[0].cost * 0.1)
                            if hasattr(spec_result, "metadata")
                            else self.models[0].cost * 0.1
                        )
                        verifier_cost = spec_result.total_cost - draft_cost
                        total_cost = spec_result.total_cost

                    # Calculate cost saved
                    best_model_cost = self.models[-1].cost
                    tokens_used = len(spec_result.content.split()) * 1.3
                    baseline_cost = best_model_cost * (tokens_used / 1000)
                    cost_saved = baseline_cost - total_cost

            # Extract latencies from metadata
            if draft_accepted_value:
                draft_latency_ms = spec_result.latency_ms
                verifier_latency_ms = 0.0
            else:
                draft_latency_ms = (
                    spec_result.metadata.get("draft_latency_ms", spec_result.latency_ms * 0.3)
                    if hasattr(spec_result, "metadata")
                    else spec_result.latency_ms * 0.3
                )
                verifier_latency_ms = spec_result.latency_ms - draft_latency_ms
        else:
            # Direct routing - no cascade
            draft_cost = 0.0
            draft_latency_ms = 0.0
            verifier_cost = spec_result.total_cost
            verifier_latency_ms = spec_result.latency_ms
            total_cost = spec_result.total_cost
            cost_saved = 0.0

        # Build comprehensive metadata
        metadata = {
            "query_length": len(query),
            "query_word_count": len(query.split()),
            "complexity": complexity,
            "complexity_confidence": complexity_confidence,
            "complexity_detection_ms": timing_breakdown.get("complexity_detection", 0),
            # 🆕 v2.6: Domain detection info
            "detected_domain": detected_domain,
            "domain_confidence": domain_confidence,
            "domain_detection_ms": timing_breakdown.get("domain_detection", 0),
            "domain_config_used": domain_config is not None,
            "domain_drafter": domain_config.drafter if domain_config else None,
            "domain_verifier": domain_config.verifier if domain_config else None,
            "domain_threshold": domain_config.threshold if domain_config else None,
            # 🆕 v2.8: Rule engine trace info
            "rule_strategy": (
                rule_decision.routing_strategy.value
                if rule_decision and rule_decision.routing_strategy
                else None
            ),
            "rule_reason": rule_decision.reason if rule_decision else None,
            "rule_confidence": rule_decision.confidence if rule_decision else None,
            "rule_metadata": rule_decision.metadata if rule_decision else None,
            "rule_allowed_models": rule_decision.allowed_models if rule_decision else None,
            "rule_excluded_models": rule_decision.excluded_models if rule_decision else None,
            "rule_preferred_models": rule_decision.preferred_models if rule_decision else None,
            "rule_forced_models": rule_decision.forced_models if rule_decision else None,
            "rule_quality_threshold": rule_decision.quality_threshold if rule_decision else None,
            "rule_max_budget": rule_decision.max_budget if rule_decision else None,
            "rule_failover_channel": rule_decision.failover_channel if rule_decision else None,
            "tenant_id": tenant_id,
            "channel": channel,
            # Original fields
            "routing_strategy": routing_strategy,
            "routing_reason": routing_reason,
            "direct_routing": routing_strategy == "direct",
            "streaming": streaming,
            "quality_score": quality_score,
            "quality_threshold": quality_threshold,
            "quality_check_passed": quality_check_passed,
            "rejection_reason": rejection_reason,
            "draft_response": draft_response,
            "verifier_response": verifier_response,
            "response_length": response_length,
            "response_word_count": response_word_count,
            "total_latency_ms": total_latency_ms,
            **timing_breakdown,
            "tokens_generated": (
                spec_result.metadata.get("tokens_generated", 0)
                if hasattr(spec_result, "metadata")
                else 0
            ),
            "speedup": spec_result.speedup if hasattr(spec_result, "speedup") else None,
            "cost_saved": cost_saved,
            "quality_config": self.quality_config.__class__.__name__,
            "has_tools": bool(tools),
            "tool_count": len(tools) if tools else 0,
            "tool_calls": tool_calls,
        }

        # Copy token counts from provider response if available (for LiteLLM integration)
        if hasattr(spec_result, "metadata") and spec_result.metadata:
            if "prompt_tokens" in spec_result.metadata:
                metadata["prompt_tokens"] = spec_result.metadata["prompt_tokens"]
            if "completion_tokens" in spec_result.metadata:
                metadata["completion_tokens"] = spec_result.metadata["completion_tokens"]
            if "total_tokens" in spec_result.metadata:
                metadata["total_tokens"] = spec_result.metadata["total_tokens"]
            for token_key in (
                "draft_prompt_tokens",
                "draft_completion_tokens",
                "draft_total_tokens",
                "verifier_prompt_tokens",
                "verifier_completion_tokens",
                "verifier_total_tokens",
            ):
                if token_key in spec_result.metadata:
                    metadata[token_key] = spec_result.metadata[token_key]

        if use_cascade:
            metadata["cascade_used"] = True
            metadata["draft_accepted"] = draft_accepted_value
            metadata["draft_model"] = self.models[0].name
            metadata["verifier_model"] = self.models[-1].name
        else:
            metadata["cascade_used"] = False
            metadata["direct_model"] = spec_result.model_used

        return CascadeResult(
            content=spec_result.content,
            model_used=spec_result.model_used,
            total_cost=total_cost,  # ✅ v2.5 FIX: Properly aggregated!
            latency_ms=total_latency_ms,
            complexity=complexity,
            cascaded=use_cascade,
            draft_accepted=draft_accepted_value,
            routing_strategy=routing_strategy,
            reason=routing_reason,
            tool_calls=tool_calls,
            has_tool_calls=bool(tool_calls),
            quality_score=quality_score,
            quality_threshold=quality_threshold,
            quality_check_passed=quality_check_passed,
            rejection_reason=rejection_reason,
            draft_response=draft_response,
            verifier_response=verifier_response,
            response_length=response_length,
            response_word_count=response_word_count,
            complexity_detection_ms=timing_breakdown.get("complexity_detection", 0),
            draft_generation_ms=timing_breakdown.get("draft_generation", 0),
            quality_verification_ms=timing_breakdown.get("quality_verification", 0),
            verifier_generation_ms=timing_breakdown.get("verifier_generation", 0),
            cascade_overhead_ms=timing_breakdown.get("cascade_overhead", 0),
            draft_cost=draft_cost,
            verifier_cost=verifier_cost,
            cost_saved=cost_saved,
            draft_model=spec_result.drafter_model if use_cascade else None,
            draft_latency_ms=draft_latency_ms,
            draft_confidence=spec_result.draft_confidence if use_cascade else None,
            verifier_model=spec_result.verifier_model if use_cascade else self.models[-1].name,
            verifier_latency_ms=verifier_latency_ms,
            verifier_confidence=(
                spec_result.verifier_confidence
                if hasattr(spec_result, "verifier_confidence")
                else None
            ),
            metadata=metadata,
        )

    # ========================================================================
    # HELPER METHODS - WITH TOOL SUPPORT
    # ========================================================================

    def _create_direct_result(self, content, model, cost, latency, reason, tool_calls=None):
        """
        Create result object for direct routing with tool support.

        CRITICAL: This must be compatible with telemetry.record()!
        """

        class DirectResult:
            """Mimics cascade results for telemetry compatibility."""

            def __init__(self, content, model, cost, latency, reason, tool_calls=None):
                # Core attributes
                self.content = content
                self.model_used = model
                self.total_cost = cost
                self.latency_ms = latency
                self.tool_calls = tool_calls

                # Cascade attributes
                self.draft_accepted = False
                self.drafter_model = None
                self.verifier_model = model
                self.draft_confidence = None
                self.verifier_confidence = 0.95
                self.speedup = 1.0

                # Complete metadata
                self.metadata = {
                    "reason": reason,
                    "direct_execution": True,
                    "routing_strategy": "direct",
                    "cascaded": False,
                    "drafter_cost": 0.0,
                    "draft_cost": 0.0,
                    "verifier_cost": cost,
                    "total_cost": cost,
                    "cost_saved": 0.0,
                    "draft_latency_ms": 0.0,
                    "drafter_latency_ms": 0.0,
                    "verifier_latency_ms": latency,
                    "total_latency_ms": latency,
                    "quality_check_ms": 0.0,
                    "quality_verification_ms": 0.0,
                    "decision_overhead_ms": 0.0,
                    "cascade_overhead_ms": 0.0,
                    "response_length": len(content),
                    "response_word_count": len(content.split()),
                    "quality_score": None,
                    "validation_score": None,
                    "quality_threshold": None,
                    "quality_check_passed": None,
                    "rejection_reason": None,
                    "tokens_generated": int(len(content.split()) * 1.3),
                    "total_tokens": int(len(content.split()) * 1.3),
                    "draft_tokens": 0,
                    "verifier_tokens": int(len(content.split()) * 1.3),
                    "draft_model": None,
                    "verifier_model": model,
                    "tool_calls": tool_calls,
                    "has_tool_calls": bool(tool_calls),
                }

            def __repr__(self):
                tool_info = f", tools={len(self.tool_calls)}" if self.tool_calls else ""
                return (
                    f"DirectResult(model={self.model_used}, "
                    f"cost=${self.total_cost:.6f}, "
                    f"latency={self.latency_ms:.1f}ms{tool_info})"
                )

            def to_dict(self):
                return {
                    "content": self.content,
                    "model_used": self.model_used,
                    "total_cost": self.total_cost,
                    "latency_ms": self.latency_ms,
                    "draft_accepted": self.draft_accepted,
                    "drafter_model": self.drafter_model,
                    "verifier_model": self.verifier_model,
                    "speedup": self.speedup,
                    "tool_calls": self.tool_calls,
                    "metadata": self.metadata,
                }

        return DirectResult(content, model, cost, latency, reason, tool_calls)

    def _dict_to_result(self, data):
        """Convert dict to result object."""

        class StreamResult:
            def __init__(self, data):
                self.content = data.get("content", "")
                self.model_used = data.get("model_used", "")
                self.total_cost = data.get("total_cost", 0.0)
                self.latency_ms = data.get("latency_ms", 0.0)
                self.draft_accepted = data.get("draft_accepted", False)
                self.drafter_model = data.get("draft_model", "")
                self.verifier_model = data.get("verifier_model", "")
                self.draft_confidence = data.get("draft_confidence", 0.0)
                self.verifier_confidence = data.get("verifier_confidence", 0.0)
                self.speedup = data.get("speedup", 1.0)
                self.tool_calls = data.get("tool_calls")
                self.metadata = data

        return StreamResult(data)

    def _create_visual_indicator(self, enabled):
        """Create visual indicator helper."""

        class VisualIndicator:
            def __init__(self, enabled):
                self.enabled = enabled and sys.stdout.isatty()

            def show(self):
                if self.enabled:
                    sys.stdout.write("\r\033[32m●\033[0m ")
                    sys.stdout.flush()

            def complete(self):
                if self.enabled:
                    sys.stdout.write("\r\033[32m✓\033[0m ")
                    sys.stdout.flush()

            def clear(self):
                if self.enabled:
                    sys.stdout.write("\r  ")
                    sys.stdout.flush()

        return VisualIndicator(enabled)

    def _get_silent_consumer(self):
        """Get silent consumer for non-visual streaming."""
        from .interface import SilentConsumer

        return SilentConsumer(verbose=self.verbose)

    # ========================================================================
    # STATISTICS - DELEGATED TO TELEMETRY
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive agent statistics including tool usage."""
        telemetry_stats = self.telemetry.get_summary()
        router_stats = self.router.get_stats()
        tool_router_stats = self.tool_router.get_stats()

        return {
            **telemetry_stats,
            "router_stats": router_stats,
            "tool_router_stats": tool_router_stats,
        }

    def print_stats(self):
        """Print formatted statistics including tool usage."""
        print("\n" + "=" * 80)
        print("CASCADEFLOW AGENT STATISTICS v2.5 (Cost Calculator Integration)")
        print("=" * 80)

        telemetry_stats = self.telemetry.get_summary()

        if telemetry_stats.get("total_queries", 0) == 0:
            print("No statistics available")
            print("=" * 80 + "\n")
            return

        print(f"Total Queries:        {telemetry_stats['total_queries']}")
        print(f"Total Cost:           ${telemetry_stats['total_cost']:.6f}")
        print(f"Avg Cost/Query:       ${telemetry_stats['avg_cost']:.6f}")
        print(f"Avg Latency:          {telemetry_stats['avg_latency_ms']:.1f}ms")
        print()

        # Tool usage stats (NEW)
        tool_queries = telemetry_stats.get("tool_queries", 0)
        if tool_queries > 0:
            print("TOOL USAGE:")
            total = telemetry_stats["total_queries"]
            pct = tool_queries / total * 100
            print(f"  Tool Queries:       {tool_queries} ({pct:.1f}%)")
            print()

        print("ROUTING:")
        cascade_used = telemetry_stats["cascade_used"]
        cascade_rate = telemetry_stats["cascade_rate"]
        print(f"  Cascade Used:       {cascade_used} ({cascade_rate:.1f}%)")
        print(f"  Direct Routed:      {telemetry_stats['direct_routed']}")
        streaming_used = telemetry_stats.get("streaming_used", 0)
        streaming_rate = telemetry_stats["streaming_rate"]
        print(f"  Streaming Used:     {streaming_used} ({streaming_rate:.1f}%)")
        print()

        # Router stats
        router_stats = self.router.get_stats()
        if router_stats.get("total_queries", 0) > 0:
            print("ROUTER (PreRouter):")
            print(f"  Total Routed:       {router_stats['total_queries']}")
            print(f"  Cascade Rate:       {router_stats.get('cascade_rate', '0%')}")
            print(f"  Direct Rate:        {router_stats.get('direct_rate', '0%')}")
            print(f"  Forced Direct:      {router_stats.get('forced_direct', 0)}")
            print()

        # Tool router stats (NEW)
        tool_router_stats = self.tool_router.get_stats()
        if tool_router_stats.get("total_filters", 0) > 0:
            print("TOOL ROUTER:")
            print(f"  Total Filters:      {tool_router_stats['total_filters']}")
            print(
                f"  Avg Models/Filter:  {tool_router_stats.get('avg_models_after_filter', 0):.1f}"
            )
            print()

        print("CASCADE PERFORMANCE:")
        print(f"  Draft Accepted:     {telemetry_stats['draft_accepted']}")
        print(f"  Draft Rejected:     {telemetry_stats['draft_rejected']}")
        print(f"  Acceptance Rate:    {telemetry_stats['acceptance_rate']:.1f}%")
        print()

        if telemetry_stats.get("quality_stats"):
            qs = telemetry_stats["quality_stats"]
            print("QUALITY SYSTEM:")
            print(f"  Mean Score:         {qs['mean']:.3f}")
            print(f"  Median Score:       {qs['median']:.3f}")
            print(f"  Range:              {qs['min']:.3f} - {qs['max']:.3f}")
            print()

        if telemetry_stats.get("timing_stats"):
            ts = telemetry_stats["timing_stats"]
            print("TIMING BREAKDOWN (ms):")
            for key in sorted(ts.keys()):
                if key.startswith("avg_"):
                    component = key.replace("avg_", "").replace("_ms", "")
                    avg_val = ts[key]
                    p95_key = f"p95_{component}_ms"
                    p95_val = ts.get(p95_key, 0)
                    print(f"  {component:25s}: {avg_val:6.1f} (p95: {p95_val:6.1f})")
            print()

        print("BY COMPLEXITY:")
        for complexity, count in telemetry_stats["by_complexity"].items():
            if count > 0:
                acceptance_info = ""
                if complexity in telemetry_stats.get("acceptance_by_complexity", {}):
                    acc = telemetry_stats["acceptance_by_complexity"][complexity]
                    total = acc["accepted"] + acc["rejected"]
                    if total > 0:
                        acc_rate = acc["accepted"] / total * 100
                        acceptance_info = f" (acceptance: {acc_rate:.1f}%)"
                print(f"  {complexity:12s}: {count}{acceptance_info}")

        print("=" * 80 + "\n")

    # ========================================================================
    # 🆕 v0.2.1: BATCH PROCESSING
    # ========================================================================

    async def run_batch(
        self, queries: list[str], batch_config: Optional["BatchConfig"] = None, **kwargs
    ) -> "BatchResult":
        """
        Process multiple queries in batch.

        🆕 NEW in v0.2.1: Efficient batch processing with LiteLLM + fallback

        Features:
        - LiteLLM native batch (preferred, automatic)
        - Sequential fallback with concurrency control
        - Cost tracking per query
        - Quality validation per query
        - Automatic retry on failures

        Args:
            queries: List of query strings
            batch_config: Batch configuration (default: BatchConfig())
            **kwargs: Additional arguments passed to run()

        Returns:
            BatchResult with all results and statistics

        Example:
            queries = ["What is Python?", "What is JS?", "What is Rust?"]
            result = await agent.run_batch(queries)

            print(f"Success: {result.success_count}/{len(queries)}")
            print(f"Total cost: ${result.total_cost:.4f}")
            print(f"Strategy: {result.strategy_used}")

            for i, cascade_result in enumerate(result.results):
                if cascade_result:
                    print(f"{i}: {cascade_result.content[:100]}...")
        """
        from .core.batch import BatchProcessor

        if not hasattr(self, "_batch_processor") or self._batch_processor is None:
            self._batch_processor = BatchProcessor(self)

        return await self._batch_processor.process_batch(queries, batch_config, **kwargs)

    @classmethod
    def from_env(cls, quality_config=None, enable_cascade=True, verbose=False):
        """Auto-discover providers from environment with tool support."""
        providers = get_available_providers()
        if not providers:
            raise cascadeflowError("No providers available. Set API keys in environment.")

        models = []
        if "openai" in providers:
            models.extend(
                [
                    ModelConfig(
                        name="gpt-3.5-turbo",
                        provider="openai",
                        cost=0.002,
                        speed_ms=800,
                        supports_tools=False,
                    ),
                    ModelConfig(
                        name="gpt-4",
                        provider="openai",
                        cost=0.03,
                        speed_ms=2500,
                        supports_tools=True,
                    ),
                    ModelConfig(
                        name="gpt-4o-mini",
                        provider="openai",
                        cost=0.0002,
                        speed_ms=600,
                        supports_tools=True,
                    ),
                ]
            )
        if "anthropic" in providers:
            models.append(
                ModelConfig(
                    name="claude-3-haiku-20240307",
                    provider="anthropic",
                    cost=0.00125,
                    speed_ms=700,
                    supports_tools=True,
                )
            )
        if "groq" in providers:
            models.append(
                ModelConfig(
                    name="llama-3.3-70b-versatile",
                    provider="groq",
                    cost=0.0,
                    speed_ms=300,
                    supports_tools=True,
                )
            )

        if not models:
            raise cascadeflowError("No models configured for available providers")

        logger.info(
            f"Auto-discovered {len(providers)} providers, created {len(models)} model configs"
        )
        return cls(
            models=models,
            quality_config=quality_config,
            enable_cascade=enable_cascade,
            verbose=verbose,
        )

    @classmethod
    def from_profile(
        cls,
        profile: "UserProfile",
        quality_config: Optional[QualityConfig] = None,
        verbose: bool = False,
    ):
        """
        Create CascadeAgent from UserProfile (v0.2.1+).

        This factory method configures the agent based on a user's profile,
        including tier limits, preferred models, and quality settings.

        Args:
            profile: UserProfile instance with tier and preferences
            quality_config: Optional quality config (overrides profile settings)
            verbose: Enable verbose logging

        Returns:
            CascadeAgent configured for the user's tier and preferences

        Example:
            >>> from cascadeflow.profiles import UserProfile, TierLevel
            >>> from cascadeflow import CascadeAgent
            >>>
            >>> # Create profile from tier
            >>> profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
            >>>
            >>> # Create agent from profile
            >>> agent = CascadeAgent.from_profile(profile)
            >>>
            >>> # Run queries with tier limits applied
            >>> result = await agent.run("What is Python?")
        """

        # Auto-discover providers from environment
        providers = get_available_providers()
        if not providers:
            raise cascadeflowError("No providers available. Set API keys in environment.")

        # Build model list based on profile preferences
        models = []

        # Filter by preferred models if specified
        preferred_models_set = set(profile.preferred_models) if profile.preferred_models else None

        # Add models from available providers
        if "openai" in providers:
            openai_models = [
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.0002,
                    speed_ms=600,
                    supports_tools=True,
                ),
                ModelConfig(
                    name="gpt-3.5-turbo",
                    provider="openai",
                    cost=0.002,
                    speed_ms=800,
                    supports_tools=False,
                ),
                ModelConfig(
                    name="gpt-4",
                    provider="openai",
                    cost=0.03,
                    speed_ms=2500,
                    supports_tools=True,
                ),
            ]
            for model in openai_models:
                if preferred_models_set is None or model.name in preferred_models_set:
                    models.append(model)

        if "anthropic" in providers:
            anthropic_models = [
                ModelConfig(
                    name="claude-3-haiku-20240307",
                    provider="anthropic",
                    cost=0.00125,
                    speed_ms=700,
                    supports_tools=True,
                )
            ]
            for model in anthropic_models:
                if preferred_models_set is None or model.name in preferred_models_set:
                    models.append(model)

        if "groq" in providers:
            groq_models = [
                ModelConfig(
                    name="llama-3.3-70b-versatile",
                    provider="groq",
                    cost=0.0,
                    speed_ms=300,
                    supports_tools=True,
                )
            ]
            for model in groq_models:
                if preferred_models_set is None or model.name in preferred_models_set:
                    models.append(model)

        if not models:
            raise cascadeflowError(
                "No models available. Check preferred_models or provider availability."
            )

        # Configure quality based on profile tier
        if quality_config is None:
            # Use tier's quality settings
            quality_config = QualityConfig(
                confidence_thresholds={
                    QueryComplexity.TRIVIAL: profile.tier.min_quality,
                    QueryComplexity.SIMPLE: profile.tier.min_quality,
                    QueryComplexity.MODERATE: profile.tier.target_quality,
                    QueryComplexity.HARD: profile.tier.target_quality,
                    QueryComplexity.EXPERT: profile.tier.target_quality,
                }
            )

        # Determine cascade enablement based on tier features
        enable_cascade = len(models) >= 2 and profile.tier.enable_streaming

        logger.info(
            f"Created agent from profile (tier={profile.tier.name}, "
            f"models={len(models)}, cascade={enable_cascade})"
        )

        # Create agent
        agent = cls(
            models=models,
            quality_config=quality_config,
            enable_cascade=enable_cascade,
            verbose=verbose,
        )

        # Store profile reference for future use (rate limiting, guardrails, etc.)
        agent._user_profile = profile

        return agent


__all__ = ["CascadeAgent", "CascadeResult"]
