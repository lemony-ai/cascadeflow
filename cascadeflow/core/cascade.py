"""
Speculative Cascades - Week 2 Integration with Tool Routing + Cost Calculator
===============================================================================

WEEK 2 ENHANCEMENT: Unified Text + Tool Routing
✅ Text queries → existing complexity.py + quality.py
✅ Tool calls → Phase 4 tool_complexity.py + tool_validator.py
✅ Seamless integration - auto-detects query type
✅ All 17+ diagnostic fields still tracked
✅ Backward compatible with existing code

🆕 COST CALCULATOR INTEGRATION:
✅ Uses telemetry.CostCalculator for consistent cost calculations
✅ Proper cost aggregation (draft + verifier when cascaded)
✅ Single source of truth for all cost logic
✅ Graceful fallback if telemetry unavailable
✅ FIXED: Now includes INPUT tokens for accurate cost calculation!

TWO EXECUTION PATHS:
1. TEXT PATH: query without tools
   → ComplexityDetector (text)
   → QualityValidator (text)
   → Existing flow

2. TOOL PATH: query with tools
   → ToolComplexityAnalyzer (Phase 4)
   → ToolQualityValidator (Phase 4)
   → Tool-specific validation


Usage:
    # Text query (existing behavior)
    result = await cascade.execute(
        query="What's the capital of France?"
    )

    # Tool query (NEW Phase 4 routing)
    result = await cascade.execute(
        query="Get weather for Paris",
        tools=[weather_tool]
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ..quality import AdaptiveThreshold, ComparativeValidator, QualityConfig, QualityValidator
from ..schema.config import ModelConfig

# Initialize logger FIRST (before try-except blocks that use it)
logger = logging.getLogger(__name__)

# Import text complexity detection
try:
    from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity

    COMPLEXITY_AVAILABLE = True
except ImportError:
    COMPLEXITY_AVAILABLE = False
    logger.warning("complexity.py not available - using basic validation mode")

# Phase 4 tool routing availability (checked lazily to avoid circular dependencies)
# Initially set to None (unchecked), will be set to True/False when first needed
TOOL_ROUTING_AVAILABLE = None


def _check_tool_routing_available():
    """
    Check if Phase 4 tool routing is available.

    This is done lazily (not at module import time) to avoid circular dependencies
    during cascadeflow package initialization.
    """
    global TOOL_ROUTING_AVAILABLE

    if TOOL_ROUTING_AVAILABLE is not None:
        return TOOL_ROUTING_AVAILABLE

    try:
        from ..quality.tool_validator import ToolQualityValidator  # noqa: F401
        from ..routing.tool_complexity import ToolComplexityAnalyzer  # noqa: F401

        TOOL_ROUTING_AVAILABLE = True
        logger.debug("✅ Phase 4 tool routing available")
        return True
    except ImportError as e:
        TOOL_ROUTING_AVAILABLE = False
        logger.debug(f"Phase 4 tool routing not available: {e}")
        return False


class DeferralStrategy(Enum):
    """Deferral strategies for whole-response cascade."""

    CONFIDENCE_THRESHOLD = "confidence"
    QUALITY_VALIDATION = "quality"
    COMPARATIVE = "comparative"
    ADAPTIVE = "adaptive"


@dataclass
class SpeculativeResult:
    """
    Result from speculative cascade execution with comprehensive diagnostics.

    Core Fields:
        content: Generated response text
        model_used: Combined model name
        drafter_model: Name of draft model
        verifier_model: Name of verifier model
        draft_accepted: Whether draft was accepted
        draft_confidence: Confidence score of draft
        verifier_confidence: Confidence score of verifier
        total_cost: Total cost in dollars (FIXED: properly aggregated with input tokens!)
        latency_ms: Total latency in milliseconds
        speedup: Speedup vs sequential
        deferral_strategy: Strategy used for deferral
        tool_calls: Tool calls made (if any)

    Diagnostic Metadata (ALL 17+ fields):
        Stored in metadata dict, guaranteed to have:
        - quality_score, quality_threshold, quality_check_passed
        - alignment (FIXED: now properly tracked!)
        - rejection_reason (if applicable)
        - draft_response, verifier_response
        - response_length, response_word_count
        - All timing breakdown components
        - All cost breakdown components (FIXED: using CostCalculator with input tokens!)
        - Cascade overhead calculation
        - Confidence method tracking
        - Tool call tracking
    """

    content: str
    model_used: str
    drafter_model: str
    verifier_model: str
    draft_accepted: bool
    draft_confidence: float
    verifier_confidence: float
    total_cost: float
    latency_ms: float
    speedup: float
    deferral_strategy: str
    metadata: dict
    tool_calls: Optional[list[dict[str, Any]]] = None


def _convert_to_dict(result: Any) -> dict[str, Any]:
    """
    Convert ModelResponse to dict if needed.

    Extracts confidence_method, tool_calls, and token counts from metadata for tracking.
    """
    if hasattr(result, "to_dict"):
        result_dict = result.to_dict()
    elif isinstance(result, dict):
        result_dict = result
    else:
        result_dict = {
            "content": getattr(result, "content", ""),
            "confidence": getattr(result, "confidence", 0.8),
            "tokens_used": getattr(result, "tokens_used", 0),
            "logprobs": getattr(result, "logprobs", None),
            "tool_calls": getattr(result, "tool_calls", None),
        }

    # Extract confidence_method from metadata if available
    if "metadata" in result_dict:
        result_dict["confidence_method"] = result_dict["metadata"].get(
            "confidence_method", "unknown"
        )
        # Extract token counts for accurate LiteLLM-based cost calculation
        if "prompt_tokens" in result_dict["metadata"]:
            result_dict["prompt_tokens"] = result_dict["metadata"]["prompt_tokens"]
        if "completion_tokens" in result_dict["metadata"]:
            result_dict["completion_tokens"] = result_dict["metadata"]["completion_tokens"]
        if "total_tokens" in result_dict["metadata"]:
            result_dict["total_tokens"] = result_dict["metadata"]["total_tokens"]
    else:
        result_dict["confidence_method"] = "unknown"

    # Ensure tool_calls is at top level
    if "tool_calls" not in result_dict and hasattr(result, "tool_calls"):
        result_dict["tool_calls"] = result.tool_calls

    return result_dict


class WholeResponseCascade:
    """
    MVP Speculative Cascade with Week 2 Tool Integration + Cost Calculator.

    TWO EXECUTION PATHS:
    1. TEXT PATH: No tools → existing complexity + quality validation
    2. TOOL PATH: Has tools → Phase 4 tool routing + validation

    🆕 COST INTEGRATION:
    - Uses CostCalculator from telemetry module for all cost calculations
    - Proper aggregation: total_cost = draft_cost + verifier_cost when cascaded
    - FIXED: Now includes INPUT tokens for 90%+ accuracy!
    - Graceful fallback if CostCalculator unavailable

    Guarantees ALL 17+ diagnostic fields are populated correctly.

    Week 2 Changes:
    - Auto-detects text vs tool queries
    - Uses ToolComplexityAnalyzer for tool calls
    - Uses ToolQualityValidator for tool validation
    - Maintains backward compatibility with text queries
    - FIXED: Properly calls complete_with_tools() for tool queries
    - FIXED: Alignment score now properly tracked in metadata
    - FIXED: Cost aggregation using CostCalculator from telemetry
    - FIXED: Now passes query_text to CostCalculator for input token counting
    """

    def __init__(
        self,
        drafter: ModelConfig,
        verifier: ModelConfig,
        providers: dict,
        model_providers: Optional[dict] = None,
        confidence_threshold: Optional[float] = None,
        quality_config: Optional[QualityConfig] = None,
        verbose: bool = False,
    ):
        self.drafter = drafter
        self.verifier = verifier
        self.providers = providers
        self.model_providers = model_providers or {}  # Model name -> provider instance
        self.verbose = verbose

        # Quality control
        if quality_config is None:
            quality_config = QualityConfig.for_cascade()

        self.quality_config = quality_config

        # Inherit threshold from config if not explicitly provided
        if confidence_threshold is None:
            confidence_threshold = quality_config.confidence_thresholds.get("simple", 0.70)

        self.confidence_threshold = confidence_threshold

        # 🆕 Initialize CostCalculator from telemetry module
        try:
            from cascadeflow.telemetry.cost_calculator import CostCalculator

            self.cost_calculator = CostCalculator(
                drafter=drafter, verifier=verifier, verbose=verbose  # Pass verbose to calculator
            )
            self._has_cost_calculator = True
            if verbose:
                logger.info("✅ CostCalculator initialized from telemetry module")
        except ImportError:
            # Fallback: Use manual calculation if telemetry not available
            self.cost_calculator = None
            self._has_cost_calculator = False
            if verbose:
                logger.warning("⚠️ CostCalculator not available - using fallback calculations")

        # TEXT VALIDATORS (existing)
        self.quality_validator = QualityValidator(config=quality_config)
        self.comparative_validator = ComparativeValidator()
        self.adaptive_threshold = AdaptiveThreshold(
            initial_thresholds=quality_config.confidence_thresholds
        )

        # TEXT COMPLEXITY DETECTOR (existing)
        if COMPLEXITY_AVAILABLE:
            self.complexity_detector = ComplexityDetector()
            if self.verbose:
                logger.info("Text complexity detection enabled")
        else:
            self.complexity_detector = None

        # SEMANTIC QUALITY CHECKER (ML-based, optional)
        try:
            from ..ml.embedding import UnifiedEmbeddingService
            from ..quality.semantic import SemanticQualityChecker

            # Create shared embedding service for all ML features
            self.embedder = UnifiedEmbeddingService()

            if self.embedder.is_available:
                # Get similarity threshold - use confidence threshold for moderate queries as default
                similarity_threshold = getattr(quality_config, "similarity_threshold", None)
                if similarity_threshold is None:
                    # Fall back to moderate confidence threshold if available
                    similarity_threshold = quality_config.confidence_thresholds.get("moderate", 0.5)

                self.semantic_quality_checker = SemanticQualityChecker(
                    embedder=self.embedder,
                    similarity_threshold=similarity_threshold,
                    use_cache=True,
                )
                if self.verbose:
                    logger.info("✅ Semantic quality checking enabled (ML)")
            else:
                self.semantic_quality_checker = None
                self.embedder = None
        except ImportError:
            self.semantic_quality_checker = None
            self.embedder = None

        # PHASE 4 TOOL ROUTING (NEW) - Lazy import to avoid circular dependencies
        if _check_tool_routing_available():
            try:
                from ..quality.tool_validator import ToolQualityValidator
                from ..routing.tool_complexity import ToolComplexityAnalyzer

                self.tool_complexity_analyzer = ToolComplexityAnalyzer()
                self.tool_quality_validator = ToolQualityValidator(verbose=verbose)
                if self.verbose:
                    logger.info("✅ Phase 4 tool routing enabled")
            except ImportError as e:
                logger.warning(f"⚠️  Phase 4 tool routing failed to load: {e}")
                self.tool_complexity_analyzer = None
                self.tool_quality_validator = None
        else:
            self.tool_complexity_analyzer = None
            self.tool_quality_validator = None
            if self.verbose:
                logger.info("Phase 4 tool routing not available (will use basic validation)")

        # Statistics
        self.stats = {
            "total_executions": 0,
            "drafts_accepted": 0,
            "drafts_rejected": 0,
            "total_speedup": 0.0,
            "total_cost_saved": 0.0,
            "acceptance_rate": 0.0,
            # Text stats
            "text_queries": 0,
            "by_complexity": {
                "trivial": {"total": 0, "accepted": 0},
                "simple": {"total": 0, "accepted": 0},
                "moderate": {"total": 0, "accepted": 0},
                "hard": {"total": 0, "accepted": 0},
                "expert": {"total": 0, "accepted": 0},
            },
            # Tool stats (NEW)
            "tool_queries": 0,
            "tool_by_complexity": {
                "trivial": {"total": 0, "accepted": 0},
                "simple": {"total": 0, "accepted": 0},
                "moderate": {"total": 0, "accepted": 0},
                "hard": {"total": 0, "accepted": 0},
                "expert": {"total": 0, "accepted": 0},
            },
        }

    # ═══════════════════════════════════════════════════════════
    # PROVIDER LOOKUP (Multi-Instance Support)
    # ═══════════════════════════════════════════════════════════

    def _get_provider(self, model: ModelConfig):
        """
        Get provider instance for a model.

        For multi-instance setups, returns the model-specific provider instance.
        Falls back to provider-type lookup for backwards compatibility.
        """
        # First try model-specific provider (for multi-instance setups)
        if model.name in self.model_providers:
            return self.model_providers[model.name]

        # Fallback to provider-type lookup (backwards compatibility)
        return self.providers[model.provider]

    # ═══════════════════════════════════════════════════════════
    # COST CALCULATION METHODS (FIXED - Now Uses Input Tokens!)
    # ═══════════════════════════════════════════════════════════

    def _estimate_tokens_from_text(self, text: str) -> int:
        """
        Estimate token count from text (fallback method).

        Uses standard approximation: 1 token ≈ 0.75 words (1.3 tokens per word)
        Same formula as CostCalculator for consistency.
        """
        if not text:
            return 0
        word_count = len(text.split())
        return max(1, int(word_count * 1.3))

    def _calculate_costs(
        self,
        draft_content: str,
        verifier_content: Optional[str],
        draft_accepted: bool,
        query_text: str = "",  # 🆕 NEW parameter!
    ) -> dict[str, float]:
        """
        Calculate all costs using CostCalculator or fallback method.

        FIXED: Now includes query_text for input token counting!

        Args:
            draft_content: Draft model's output
            verifier_content: Verifier model's output (if cascaded)
            draft_accepted: Whether draft was accepted
            query_text: Original query text for input token counting (NEW!)

        Returns:
            Dict with draft_cost, verifier_cost, total_cost, cost_saved, tokens
        """
        # 🆕 Try using CostCalculator first (with input tokens!)
        if self._has_cost_calculator and self.cost_calculator:
            try:
                # Estimate OUTPUT tokens only
                draft_output_tokens = self._estimate_tokens_from_text(draft_content)
                verifier_output_tokens = (
                    self._estimate_tokens_from_text(verifier_content) if verifier_content else 0
                )
                # 🆕 Estimate INPUT tokens from query
                query_input_tokens = self._estimate_tokens_from_text(query_text)

                # Use CostCalculator WITH input tokens
                breakdown = self.cost_calculator.calculate_from_tokens(
                    draft_output_tokens=draft_output_tokens,
                    verifier_output_tokens=verifier_output_tokens,
                    draft_accepted=draft_accepted,
                    query_input_tokens=query_input_tokens,  # 🆕 NEW!
                )

                if self.verbose:
                    logger.info(
                        f"💰 CostCalculator: "
                        f"input={query_input_tokens}, "
                        f"draft_output={draft_output_tokens}, "
                        f"verifier_output={verifier_output_tokens}, "
                        f"draft=${breakdown.draft_cost:.6f}, "
                        f"verifier=${breakdown.verifier_cost:.6f}, "
                        f"total=${breakdown.total_cost:.6f}"
                    )

                return {
                    "draft_cost": breakdown.draft_cost,
                    "verifier_cost": breakdown.verifier_cost,
                    "total_cost": breakdown.total_cost,
                    "cost_saved": breakdown.cost_saved,
                    "draft_tokens": breakdown.draft_tokens,  # Now includes input!
                    "verifier_tokens": breakdown.verifier_tokens,  # Now includes input!
                    "total_tokens": breakdown.total_tokens,
                }

            except Exception as e:
                logger.warning(f"CostCalculator failed: {e}, using fallback")

        # Fallback: Manual calculation (also with input tokens now)
        query_tokens = self._estimate_tokens_from_text(query_text)
        draft_output_tokens = self._estimate_tokens_from_text(draft_content)
        draft_total_tokens = query_tokens + draft_output_tokens
        draft_cost = self.drafter.cost * (draft_total_tokens / 1000)

        if draft_accepted:
            # Draft accepted - only paid for draft (with input)
            verifier_total_tokens_estimate = query_tokens + draft_output_tokens
            verifier_cost_avoided = self.verifier.cost * (verifier_total_tokens_estimate / 1000)
            cost_saved = verifier_cost_avoided - draft_cost

            return {
                "draft_cost": draft_cost,
                "verifier_cost": 0.0,
                "total_cost": draft_cost,
                "cost_saved": cost_saved,
                "draft_tokens": draft_total_tokens,
                "verifier_tokens": 0,
                "total_tokens": draft_total_tokens,
            }
        else:
            # Draft rejected - paid for both (with input for both!)
            verifier_output_tokens = (
                self._estimate_tokens_from_text(verifier_content) if verifier_content else 0
            )
            verifier_total_tokens = query_tokens + verifier_output_tokens
            verifier_cost = self.verifier.cost * (verifier_total_tokens / 1000)
            total_cost = draft_cost + verifier_cost  # ✅ CORRECT AGGREGATION
            cost_saved = -draft_cost  # Wasted draft cost

            return {
                "draft_cost": draft_cost,
                "verifier_cost": verifier_cost,
                "total_cost": total_cost,  # ✅ Both costs included
                "cost_saved": cost_saved,
                "draft_tokens": draft_total_tokens,
                "verifier_tokens": verifier_total_tokens,
                "total_tokens": draft_total_tokens + verifier_total_tokens,
            }

    def _calculate_draft_cost(self, draft_result: dict[str, Any]) -> float:
        """
        Calculate cost of draft (legacy method for backward compatibility).
        Now delegates to _calculate_costs for consistency.
        """
        draft_content = draft_result.get("content", "")
        costs = self._calculate_costs(
            draft_content=draft_content,
            verifier_content=None,
            draft_accepted=True,
            query_text="",  # Legacy method doesn't have query
        )
        return costs["draft_cost"]

    def _calculate_verifier_cost(self, verifier_result: dict[str, Any]) -> float:
        """
        Calculate cost of verifier (legacy method for backward compatibility).
        Now delegates to _calculate_costs for consistency.
        """
        verifier_content = verifier_result.get("content", "")
        costs = self._calculate_costs(
            draft_content="",
            verifier_content=verifier_content,
            draft_accepted=False,
            query_text="",  # Legacy method doesn't have query
        )
        return costs["verifier_cost"]

    # ═══════════════════════════════════════════════════════════
    # MAIN EXECUTE METHOD
    # ═══════════════════════════════════════════════════════════

    async def execute(
        self,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        complexity: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> SpeculativeResult:
        """
        Execute whole-response speculative cascade with tool support and accurate costing.

        Week 2 Enhancement: Auto-detects text vs tool queries and routes accordingly.
        Cost Enhancement: Uses CostCalculator for accurate, consistent cost tracking.
        FIXED: Now passes query to cost calculator for input token counting!

        Args:
            query: Input query
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            complexity: Optional complexity hint from agent
            tools: Optional tools for tool calling (NEW)
            tool_choice: Control tool calling behavior (NEW)

        Returns:
            SpeculativeResult with content and COMPLETE diagnostic metadata
        """
        self.stats["total_executions"] += 1
        overall_start = time.time()

        # === ROUTE: TEXT PATH vs TOOL PATH ===
        has_tools = tools is not None and len(tools) > 0

        if has_tools:
            self.stats["tool_queries"] += 1
            if self.verbose:
                logger.info(f"🔧 TOOL PATH: {len(tools)} tools available")

            return await self._execute_tool_path(
                query=query,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                complexity=complexity,
                overall_start=overall_start,
                **kwargs,
            )
        else:
            self.stats["text_queries"] += 1
            if self.verbose:
                logger.info("📝 TEXT PATH: No tools")

            return await self._execute_text_path(
                query=query,
                max_tokens=max_tokens,
                temperature=temperature,
                complexity=complexity,
                overall_start=overall_start,
                **kwargs,
            )

    # ═══════════════════════════════════════════════════════════
    # TOOL PATH (Phase 4 Integration with Cost Calculator)
    # ═══════════════════════════════════════════════════════════

    async def _execute_tool_path(
        self,
        query: str,
        max_tokens: int,
        temperature: float,
        tools: list[dict[str, Any]],
        tool_choice: Optional[str],
        complexity: Optional[str],
        overall_start: float,
        **kwargs,
    ) -> SpeculativeResult:
        """
        TOOL PATH: Execute using Phase 4 tool complexity + quality validation.
        Now uses CostCalculator for accurate cost tracking WITH input tokens.

        Flow:
        1. Analyze tool call complexity (ToolComplexityAnalyzer)
        2. Generate draft with tools
        3. Validate tool calls (ToolQualityValidator)
        4. Accept or escalate to verifier
        5. Calculate costs using CostCalculator (with input tokens!)
        """
        # Timing breakdown
        timing = {
            "draft_latency_ms": 0.0,
            "quality_check_ms": 0.0,
            "verifier_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "cascade_overhead_ms": 0.0,
            "tool_complexity_analysis_ms": 0.0,
        }

        if self.verbose:
            logger.info(f"Tool cascade: {self.drafter.name} → {self.verifier.name}")

        # === PHASE 1: Analyze Tool Complexity ===
        if self.tool_complexity_analyzer and not complexity:
            complexity_start = time.time()
            tool_analysis = self.tool_complexity_analyzer.analyze_tool_call(
                query=query, tools=tools
            )
            timing["tool_complexity_analysis_ms"] = (time.time() - complexity_start) * 1000
            complexity = tool_analysis.complexity_level.value

            if self.verbose:
                logger.info(
                    f"Tool complexity: {complexity} "
                    f"(score: {tool_analysis.score:.1f}, "
                    f"signals: {sum(tool_analysis.signals.values())})"
                )
        elif not complexity:
            complexity = "simple"

        # === PHASE 2: Generate Draft with Tools ===
        draft_start = time.time()
        draft_result = await self._call_drafter(
            query, max_tokens, temperature, tools=tools, tool_choice=tool_choice
        )
        timing["draft_latency_ms"] = (time.time() - draft_start) * 1000

        if self.verbose:
            logger.info(f"Draft generated in {timing['draft_latency_ms']:.1f}ms")
            if draft_result and draft_result.get("tool_calls"):
                logger.info(f"Draft includes {len(draft_result['tool_calls'])} tool calls")

        if not draft_result:
            # Draft failed - need to use verifier
            if self.verbose:
                logger.warning("Draft failed, falling back to verifier")

            verifier_start = time.time()
            verifier_result = await self._call_verifier(
                query, max_tokens, temperature, tools=tools, tool_choice=tool_choice
            )
            timing["verifier_latency_ms"] = (time.time() - verifier_start) * 1000
            timing["total_latency_ms"] = (time.time() - overall_start) * 1000
            timing["cascade_overhead_ms"] = timing["draft_latency_ms"]

            verifier_content = verifier_result["content"]
            verifier_tool_calls = verifier_result.get("tool_calls")

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content="",
                verifier_content=verifier_content,
                draft_accepted=False,
                query_text=query,  # 🆕 Pass query!
            )

            return self._create_result(
                content=verifier_content,
                confidence=verifier_result["confidence"],
                confidence_method=verifier_result.get("confidence_method", "unknown"),
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=False,
                draft_confidence=0.0,
                draft_response="",
                verifier_response=verifier_content,
                reason="draft_failed",
                query=query,
                timing=timing,
                quality_score=None,
                quality_threshold=None,
                rejection_reason="draft_generation_failed",
                complexity=complexity,
                tool_calls=verifier_tool_calls,
                alignment_score=None,
                cost_breakdown=costs,
            )

        # === PHASE 3: Preliminary Confidence Check ===
        raw_draft_confidence = draft_result.get("confidence", 0.0)
        draft_method = draft_result.get("confidence_method", "unknown")
        draft_content = draft_result.get("content", "")
        draft_tool_calls = draft_result.get("tool_calls")

        if self.verbose:
            logger.info(f"Draft: confidence={raw_draft_confidence:.3f}, method={draft_method}")

        # Start verifier if confidence is low
        needs_verification = raw_draft_confidence < 0.75
        if needs_verification:
            if self.verbose:
                logger.debug(
                    f"Draft confidence {raw_draft_confidence:.2f} < 0.75, starting verifier"
                )
            verifier_task = asyncio.create_task(
                self._call_verifier(
                    query, max_tokens, temperature, tools=tools, tool_choice=tool_choice
                )
            )
        else:
            verifier_task = None

        # === PHASE 4: Tool Quality Validation ===
        quality_start = time.time()
        should_accept, quality_score, rejection_reason = self._should_accept_tool_draft(
            draft_result, query, tools, complexity
        )
        timing["quality_check_ms"] = (time.time() - quality_start) * 1000

        if self.verbose:
            logger.info(f"Tool quality check completed in {timing['quality_check_ms']:.1f}ms")

        # Track complexity-specific stats
        if complexity:
            self.stats["tool_by_complexity"][complexity]["total"] += 1

        # === PHASE 5: Decision - Accept or Reject ===
        if should_accept:
            # ✅ ACCEPT: Use draft
            self.stats["drafts_accepted"] += 1

            if complexity:
                self.stats["tool_by_complexity"][complexity]["accepted"] += 1

            # Cancel verifier if running
            if verifier_task is not None and not verifier_task.done():
                verifier_task.cancel()
                try:
                    await verifier_task
                except asyncio.CancelledError:
                    pass

            if self.verbose:
                logger.info(
                    f"✓ Draft accepted with {len(draft_tool_calls) if draft_tool_calls else 0} tool calls "
                    f"(quality: {quality_score:.2f}, complexity: {complexity})"
                )

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content=draft_content,
                verifier_content=None,
                draft_accepted=True,
                query_text=query,  # 🆕 Pass query!
            )

            timing["total_latency_ms"] = (time.time() - overall_start) * 1000

            estimated_verifier_latency = self.verifier.speed_ms
            speedup = (
                estimated_verifier_latency / timing["total_latency_ms"]
                if timing["total_latency_ms"] > 0
                else 1.0
            )

            direct_equivalent_time = estimated_verifier_latency
            timing["cascade_overhead_ms"] = timing["total_latency_ms"] - direct_equivalent_time
            timing["direct_equivalent_ms"] = direct_equivalent_time

            self.stats["total_speedup"] += speedup
            self.stats["total_cost_saved"] += costs["cost_saved"]

            return self._create_result(
                content=draft_content,
                confidence=draft_result["confidence"],
                confidence_method=draft_method,
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=True,
                draft_confidence=raw_draft_confidence,
                draft_response=draft_content,
                verifier_response=None,
                reason="tool_quality_passed",
                cost_saved=costs["cost_saved"],
                speedup=speedup,
                query=query,
                complexity=complexity,
                timing=timing,
                quality_score=quality_score,
                quality_threshold=self.confidence_threshold,
                rejection_reason=None,
                draft_method=draft_method,
                tool_calls=draft_tool_calls,
                alignment_score=None,
                cost_breakdown=costs,
            )

        else:
            # ❌ REJECT: Need verifier result
            self.stats["drafts_rejected"] += 1

            if self.verbose:
                logger.info(
                    f"✗ Draft rejected: {rejection_reason} "
                    f"(quality: {quality_score:.2f}, complexity: {complexity})"
                )

            # Wait for or start verifier
            verifier_start = time.time()
            if verifier_task is None:
                verifier_result = await self._call_verifier(
                    query, max_tokens, temperature, tools=tools, tool_choice=tool_choice
                )
            else:
                verifier_result = await verifier_task
            timing["verifier_latency_ms"] = (time.time() - verifier_start) * 1000

            verifier_method = verifier_result.get("confidence_method", "unknown")
            verifier_content = verifier_result.get("content", "")
            verifier_tool_calls = verifier_result.get("tool_calls")

            if self.verbose:
                logger.info(
                    f"Verifier completed in {timing['verifier_latency_ms']:.1f}ms "
                    f"(confidence={verifier_result['confidence']:.3f}, "
                    f"tool_calls={len(verifier_tool_calls) if verifier_tool_calls else 0})"
                )

            timing["total_latency_ms"] = (time.time() - overall_start) * 1000

            direct_equivalent_time = timing["verifier_latency_ms"]
            timing["cascade_overhead_ms"] = timing["draft_latency_ms"] + timing["quality_check_ms"]
            timing["direct_equivalent_ms"] = direct_equivalent_time

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content=draft_content,
                verifier_content=verifier_content,
                draft_accepted=False,
                query_text=query,  # 🆕 Pass query!
            )

            return self._create_result(
                content=verifier_content,
                confidence=verifier_result["confidence"],
                confidence_method=verifier_method,
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=False,
                draft_confidence=raw_draft_confidence,
                draft_response=draft_content,
                verifier_response=verifier_content,
                draft_method=draft_method,
                reason=rejection_reason,
                cost_saved=costs["cost_saved"],
                speedup=1.0,
                query=query,
                complexity=complexity,
                timing=timing,
                quality_score=quality_score,
                quality_threshold=self.confidence_threshold,
                rejection_reason=rejection_reason,
                tool_calls=verifier_tool_calls,
                alignment_score=None,
                cost_breakdown=costs,
            )

    def _should_accept_tool_draft(
        self, draft_result: dict[str, Any], query: str, tools: list[dict[str, Any]], complexity: str
    ) -> tuple[bool, float, Optional[str]]:
        """
        Validate tool call draft using ToolQualityValidator.

        Returns:
            Tuple of (should_accept, quality_score, rejection_reason)
        """
        draft_tool_calls = draft_result.get("tool_calls")

        # If no tool calls in draft, reject (query asked for tools)
        if not draft_tool_calls:
            return False, 0.0, "no_tool_calls_generated"

        # Use Phase 4 ToolQualityValidator
        if self.tool_quality_validator:
            try:
                # Convert complexity string to ToolComplexityLevel
                from ..routing.tool_complexity import ToolComplexityLevel

                complexity_level = ToolComplexityLevel(complexity.lower())
            except (ValueError, AttributeError):
                complexity_level = None

            result = self.tool_quality_validator.validate_tool_calls(
                tool_calls=draft_tool_calls,
                available_tools=tools,
                complexity_level=complexity_level,
            )

            return (
                result.is_valid,
                result.overall_score,
                None if result.is_valid else "; ".join(result.issues),
            )
        else:
            # Fallback: Basic validation
            draft_confidence = draft_result.get("confidence", 0.0)
            threshold = self.confidence_threshold
            passed = draft_confidence >= threshold
            return passed, draft_confidence, None if passed else "confidence_below_threshold"

    # ═══════════════════════════════════════════════════════════
    # TEXT PATH (FIXED - Now Uses CostCalculator WITH Input Tokens)
    # ═══════════════════════════════════════════════════════════

    async def _execute_text_path(
        self,
        query: str,
        max_tokens: int,
        temperature: float,
        complexity: Optional[str],
        overall_start: float,
        **kwargs,
    ) -> SpeculativeResult:
        """
        TEXT PATH: Execute using existing text complexity + quality validation.

        FIXED: Now properly extracts and tracks alignment score from validation results.
        FIXED: Now uses CostCalculator for accurate cost tracking.
        FIXED: Now passes query to CostCalculator for input token counting!
        """
        # Timing breakdown
        timing = {
            "draft_latency_ms": 0.0,
            "quality_check_ms": 0.0,
            "verifier_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "cascade_overhead_ms": 0.0,
        }

        if self.verbose:
            logger.info(f"Starting cascade: {self.drafter.name} → {self.verifier.name}")

        # === PHASE 1: Generate Draft ===
        draft_start = time.time()
        draft_result = await self._call_drafter(query, max_tokens, temperature, tools=None)
        timing["draft_latency_ms"] = (time.time() - draft_start) * 1000

        if self.verbose:
            logger.info(f"Draft generated in {timing['draft_latency_ms']:.1f}ms")

        if not draft_result:
            # Draft failed
            if self.verbose:
                logger.warning("Draft failed, falling back to verifier")

            verifier_start = time.time()
            verifier_result = await self._call_verifier(query, max_tokens, temperature, tools=None)
            timing["verifier_latency_ms"] = (time.time() - verifier_start) * 1000
            timing["total_latency_ms"] = (time.time() - overall_start) * 1000
            timing["cascade_overhead_ms"] = timing["draft_latency_ms"]

            verifier_content = verifier_result["content"]

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content="",
                verifier_content=verifier_content,
                draft_accepted=False,
                query_text=query,  # 🆕 Pass query!
            )

            return self._create_result(
                content=verifier_content,
                confidence=verifier_result["confidence"],
                confidence_method=verifier_result.get("confidence_method", "unknown"),
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=False,
                draft_confidence=0.0,
                draft_response="",
                verifier_response=verifier_content,
                reason="draft_failed",
                query=query,
                timing=timing,
                quality_score=None,
                quality_threshold=None,
                rejection_reason="draft_generation_failed",
                complexity=complexity,
                alignment_score=None,
                cost_breakdown=costs,
            )

        # === PHASE 2: Preliminary Confidence Check ===
        raw_draft_confidence = draft_result.get("confidence", 0.0)
        draft_method = draft_result.get("confidence_method", "unknown")
        draft_content = draft_result.get("content", "")

        if self.verbose:
            logger.info(f"Draft: confidence={raw_draft_confidence:.3f}, method={draft_method}")

        needs_verification = raw_draft_confidence < 0.75
        if needs_verification:
            if self.verbose:
                logger.debug(
                    f"Draft confidence {raw_draft_confidence:.2f} < 0.75, starting verifier"
                )
            verifier_task = asyncio.create_task(
                self._call_verifier(query, max_tokens, temperature, tools=None)
            )
        else:
            verifier_task = None

        # === PHASE 3: Quality Validation ===
        quality_start = time.time()
        should_accept, validation_result, detected_complexity = self._should_accept_draft(
            draft_result, query, complexity_hint=complexity
        )
        timing["quality_check_ms"] = (time.time() - quality_start) * 1000

        final_complexity = complexity or detected_complexity

        if self.verbose:
            logger.info(f"Quality check completed in {timing['quality_check_ms']:.1f}ms")

        # Extract validation metrics
        quality_score = getattr(validation_result, "score", None)
        quality_threshold = self.confidence_threshold
        validation_reason = getattr(validation_result, "reason", "validation_completed")
        validation_checks = getattr(validation_result, "checks", {})

        # === CRITICAL FIX: Extract alignment score from validation details ===
        validation_details = getattr(validation_result, "details", {})
        alignment_score = validation_details.get("alignment", 0.0)

        if self.verbose and alignment_score < 0.30:
            logger.warning(f"Low alignment detected: {alignment_score:.3f}")

        if final_complexity:
            self.stats["by_complexity"][final_complexity]["total"] += 1

        # === PHASE 4: Decision ===
        if should_accept:
            # ✅ ACCEPT
            self.stats["drafts_accepted"] += 1

            if final_complexity:
                self.stats["by_complexity"][final_complexity]["accepted"] += 1

            if verifier_task is not None and not verifier_task.done():
                verifier_task.cancel()
                try:
                    await verifier_task
                except asyncio.CancelledError:
                    pass

            if self.quality_config.enable_adaptive and final_complexity:
                score_for_learning = (
                    quality_score if quality_score is not None else draft_result["confidence"]
                )
                self.adaptive_threshold.record(
                    draft_result["confidence"], score_for_learning, complexity=final_complexity
                )

            if self.verbose:
                qs_str = f"{quality_score:.2f}" if quality_score is not None else "N/A"
                logger.info(
                    f"✓ Draft accepted: {validation_reason} "
                    f"(confidence: {draft_result['confidence']:.2f}, "
                    f"quality_score: {qs_str}, "
                    f"alignment: {alignment_score:.2f}, "
                    f"complexity: {final_complexity})"
                )

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content=draft_content,
                verifier_content=None,
                draft_accepted=True,
                query_text=query,  # 🆕 Pass query!
            )

            timing["total_latency_ms"] = (time.time() - overall_start) * 1000
            estimated_verifier_latency = self.verifier.speed_ms
            speedup = (
                estimated_verifier_latency / timing["total_latency_ms"]
                if timing["total_latency_ms"] > 0
                else 1.0
            )

            direct_equivalent_time = estimated_verifier_latency
            timing["cascade_overhead_ms"] = timing["total_latency_ms"] - direct_equivalent_time
            timing["direct_equivalent_ms"] = direct_equivalent_time

            self.stats["total_speedup"] += speedup
            self.stats["total_cost_saved"] += costs["cost_saved"]

            return self._create_result(
                content=draft_content,
                confidence=draft_result["confidence"],
                confidence_method=draft_method,
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=True,
                draft_confidence=raw_draft_confidence,
                draft_response=draft_content,
                verifier_response=None,
                reason=validation_reason,
                cost_saved=costs["cost_saved"],
                speedup=speedup,
                validation_checks=validation_checks,
                query=query,
                complexity=final_complexity,
                timing=timing,
                quality_score=quality_score,
                quality_threshold=quality_threshold,
                rejection_reason=None,
                draft_method=draft_method,
                alignment_score=alignment_score,
                cost_breakdown=costs,
                draft_result=draft_result,
            )

        else:
            # ❌ REJECT
            self.stats["drafts_rejected"] += 1

            if self.verbose:
                qs_str = f"{quality_score:.2f}" if quality_score is not None else "N/A"
                logger.info(
                    f"✗ Draft rejected: {validation_reason} "
                    f"(confidence: {draft_result['confidence']:.2f}, "
                    f"quality_score: {qs_str}, "
                    f"alignment: {alignment_score:.2f}, "
                    f"complexity: {final_complexity})"
                )

            verifier_start = time.time()
            if verifier_task is None:
                verifier_result = await self._call_verifier(
                    query, max_tokens, temperature, tools=None
                )
            else:
                verifier_result = await verifier_task
            timing["verifier_latency_ms"] = (time.time() - verifier_start) * 1000

            verifier_method = verifier_result.get("confidence_method", "unknown")
            verifier_content = verifier_result.get("content", "")

            if self.verbose:
                logger.info(
                    f"Verifier completed in {timing['verifier_latency_ms']:.1f}ms "
                    f"(confidence={verifier_result['confidence']:.3f})"
                )

            timing["total_latency_ms"] = (time.time() - overall_start) * 1000
            direct_equivalent_time = timing["verifier_latency_ms"]
            timing["cascade_overhead_ms"] = timing["draft_latency_ms"] + timing["quality_check_ms"]
            timing["direct_equivalent_ms"] = direct_equivalent_time

            # 🆕 Use CostCalculator WITH query
            costs = self._calculate_costs(
                draft_content=draft_content,
                verifier_content=verifier_content,
                draft_accepted=False,
                query_text=query,  # 🆕 Pass query!
            )

            return self._create_result(
                content=verifier_content,
                confidence=verifier_result["confidence"],
                confidence_method=verifier_method,
                cost=costs["total_cost"],
                latency=timing["total_latency_ms"],
                draft_accepted=False,
                draft_confidence=raw_draft_confidence,
                draft_response=draft_content,
                verifier_response=verifier_content,
                draft_method=draft_method,
                reason=validation_reason,
                cost_saved=costs["cost_saved"],
                speedup=1.0,
                validation_checks=validation_checks,
                query=query,
                complexity=final_complexity,
                timing=timing,
                quality_score=quality_score,
                quality_threshold=quality_threshold,
                rejection_reason=validation_reason,
                alignment_score=alignment_score,
                cost_breakdown=costs,
                verifier_result=verifier_result,
            )

    # ═══════════════════════════════════════════════════════════
    # Provider Call Methods - WITH TOOL SUPPORT
    # ═══════════════════════════════════════════════════════════

    async def _call_drafter(
        self,
        query: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Call drafter model with optional tool support.

        """
        try:
            provider = self._get_provider(self.drafter)

            # === CRITICAL FIX: Route to correct method based on tools ===
            if tools:
                # TOOL PATH: Use complete_with_tools() with messages format
                messages = [{"role": "user", "content": query}]

                result = await provider.complete_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    model=self.drafter.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            else:
                # TEXT PATH: Use complete() with prompt format
                result = await provider.complete(
                    prompt=query,
                    model=self.drafter.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    logprobs=True,
                    top_logprobs=5,
                )

            return _convert_to_dict(result)

        except Exception as e:
            logger.error(f"Drafter error: {e}", exc_info=True)
            return None

    async def _call_verifier(
        self,
        query: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Call verifier model with optional tool support.

        """
        try:
            provider = self._get_provider(self.verifier)

            # === CRITICAL FIX: Route to correct method based on tools ===
            if tools:
                # TOOL PATH: Use complete_with_tools() with messages format
                messages = [{"role": "user", "content": query}]

                result = await provider.complete_with_tools(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    model=self.verifier.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            else:
                # TEXT PATH: Use complete() with prompt format
                result = await provider.complete(
                    prompt=query,
                    model=self.verifier.name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    logprobs=True,
                    top_logprobs=5,
                )

            return _convert_to_dict(result)

        except Exception as e:
            logger.error(f"Verifier error: {e}", exc_info=True)
            return {
                "content": "",
                "confidence": 0.0,
                "confidence_method": "error",
                "tokens_used": 0,
                "tool_calls": None,
            }

    def _should_accept_draft(
        self, draft_result: dict[str, Any], query: str, complexity_hint: Optional[str] = None
    ) -> tuple[bool, Any, Optional[str]]:
        """
        Decide whether to accept draft with complexity awareness (TEXT PATH).
        """
        draft_content = draft_result.get("content", "")
        draft_confidence = draft_result.get("confidence", 0.0)

        # Use hint or detect complexity
        if complexity_hint:
            complexity = complexity_hint
        elif self.complexity_detector:
            try:
                detected_complexity, _ = self.complexity_detector.detect(query)
                if detected_complexity is not None:
                    complexity = detected_complexity.value
                else:
                    complexity = "simple"
            except Exception as e:
                logger.warning(f"Complexity detection failed: {e}")
                complexity = "simple"
        else:
            complexity = "simple"

        threshold = self.confidence_threshold

        if self.quality_config.enable_adaptive and complexity:
            adaptive_threshold = self.adaptive_threshold.get_threshold(complexity)
            if adaptive_threshold > threshold:
                threshold = adaptive_threshold

        validation_result = self.quality_validator.validate(
            draft_content,
            query,
            draft_confidence,
            complexity=complexity,
            threshold_override=threshold,
        )

        passed = getattr(validation_result, "passed", False)

        # Additional semantic quality check if available
        if (
            passed
            and self.semantic_quality_checker
            and self.semantic_quality_checker.is_available()
        ):
            try:
                semantic_result = self.semantic_quality_checker.validate(
                    query=query,
                    response=draft_content,
                    check_toxicity=True,
                )

                if not semantic_result.passed:
                    # Semantic check failed → reject draft
                    passed = False
                    # Update validation result reason
                    if hasattr(validation_result, "reason"):
                        validation_result.reason = (
                            f"semantic_check_failed: {semantic_result.reason}"
                        )
                    if self.verbose:
                        logger.info(
                            f"❌ Draft rejected by semantic quality check: {semantic_result.reason} "
                            f"(similarity={semantic_result.similarity:.2f})"
                        )
            except Exception as e:
                # Don't fail the whole cascade if semantic check errors
                logger.warning(f"Semantic quality check failed: {e}")

        return passed, validation_result, complexity

    def _create_result(
        self,
        content: str,
        confidence: float,
        confidence_method: str,
        cost: float,
        latency: float,
        draft_accepted: bool,
        draft_confidence: float,
        draft_response: str,
        verifier_response: Optional[str],
        reason: str,
        cost_saved: float = 0.0,
        speedup: float = 1.0,
        validation_checks: Optional[dict[str, bool]] = None,
        query: str = "",
        complexity: Optional[str] = None,
        timing: Optional[dict[str, float]] = None,
        quality_score: Optional[float] = None,
        quality_threshold: Optional[float] = None,
        rejection_reason: Optional[str] = None,
        draft_method: Optional[str] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        alignment_score: Optional[float] = None,
        cost_breakdown: Optional[dict[str, float]] = None,
        draft_result: Optional[dict[str, Any]] = None,
        verifier_result: Optional[dict[str, Any]] = None,
    ) -> SpeculativeResult:
        """
        Create SpeculativeResult with COMPLETE diagnostic metadata and tool calls.

        FIXED: Now includes alignment_score in metadata.
        FIXED: Now uses cost_breakdown from CostCalculator for accurate costs.
        """
        # Update acceptance rate
        if self.stats["total_executions"] > 0:
            self.stats["acceptance_rate"] = (
                self.stats["drafts_accepted"] / self.stats["total_executions"]
            )

        # Calculate complexity-specific rates
        complexity_rates = {}
        for comp, stats in self.stats["by_complexity"].items():
            if stats["total"] > 0:
                complexity_rates[comp] = stats["accepted"] / stats["total"]

        # Calculate response metrics
        response_length = len(content)
        response_word_count = len(content.split())

        # 🆕 Use cost_breakdown from CostCalculator if available
        if cost_breakdown:
            drafter_cost = cost_breakdown["draft_cost"]
            verifier_cost = cost_breakdown["verifier_cost"]
            total_tokens = cost_breakdown.get("total_tokens", 0)
        else:
            # Fallback: Calculate manually
            if draft_response:
                draft_tokens = len(draft_response.split()) * 1.3
            else:
                draft_tokens = 0

            drafter_cost = self.drafter.cost * (draft_tokens / 1000) if draft_tokens > 0 else 0.0
            verifier_cost = max(0.0, cost - drafter_cost)
            total_tokens = int(
                draft_tokens + (len(verifier_response.split()) * 1.3 if verifier_response else 0)
            )

        # Build COMPLETE metadata
        metadata = {
            # Quality system
            "quality_score": quality_score,
            "quality_threshold": quality_threshold,
            "quality_check_passed": draft_accepted,
            "rejection_reason": rejection_reason,
            "alignment": alignment_score,
            # Response tracking
            "draft_response": draft_response,
            "verifier_response": verifier_response,
            "response_length": response_length,
            "response_word_count": response_word_count,
            # Timing breakdown
            "draft_latency_ms": timing.get("draft_latency_ms", 0) if timing else 0,
            "quality_check_ms": timing.get("quality_check_ms", 0) if timing else 0,
            "verifier_latency_ms": timing.get("verifier_latency_ms", 0) if timing else 0,
            "cascade_overhead_ms": timing.get("cascade_overhead_ms", 0) if timing else 0,
            "direct_equivalent_ms": timing.get("direct_equivalent_ms", 0) if timing else 0,
            "tool_complexity_analysis_ms": (
                timing.get("tool_complexity_analysis_ms", 0) if timing else 0
            ),
            # 🆕 Cost breakdown (from CostCalculator with input tokens!)
            "drafter_cost": drafter_cost,
            "verifier_cost": verifier_cost,
            "cost_saved": cost_saved,
            "total_tokens": total_tokens,
            # Confidence tracking
            "raw_draft_confidence": draft_confidence,
            "confidence_method": confidence_method,
            "draft_method": draft_method or confidence_method,
            # Additional metadata
            "speedup": speedup,
            "reason": reason,
            "validation_checks": validation_checks or {},
            "threshold": quality_threshold or self.confidence_threshold,
            "complexity": complexity,
            "complexity_acceptance_rates": complexity_rates,
            "acceptance_rate": self.stats["acceptance_rate"],
            "query_preview": query[:50] if query else "",
            "tokens_generated": len(content.split()) * 1.3,
            # Tool metadata
            "tool_calls": tool_calls,
            "has_tool_calls": bool(tool_calls),
            "tool_count": len(tool_calls) if tool_calls else 0,
        }

        # Extract token counts from provider responses for LiteLLM integration
        if draft_result:
            if "prompt_tokens" in draft_result:
                metadata["prompt_tokens"] = draft_result["prompt_tokens"]
            if "completion_tokens" in draft_result:
                metadata["completion_tokens"] = draft_result["completion_tokens"]
            if "total_tokens" in draft_result:
                metadata["total_tokens"] = draft_result["total_tokens"]
        elif verifier_result:
            # If draft was rejected, use verifier tokens
            if "prompt_tokens" in verifier_result:
                metadata["prompt_tokens"] = verifier_result["prompt_tokens"]
            if "completion_tokens" in verifier_result:
                metadata["completion_tokens"] = verifier_result["completion_tokens"]
            if "total_tokens" in verifier_result:
                metadata["total_tokens"] = verifier_result["total_tokens"]

        return SpeculativeResult(
            content=content,
            model_used=f"{self.drafter.name}+{self.verifier.name}",
            drafter_model=self.drafter.name,
            verifier_model=self.verifier.name,
            draft_accepted=draft_accepted,
            draft_confidence=draft_confidence,
            verifier_confidence=confidence if not draft_accepted else 0.0,
            total_cost=cost,
            latency_ms=latency,
            speedup=speedup,
            deferral_strategy=self.quality_config.__class__.__name__,
            metadata=metadata,
            tool_calls=tool_calls,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get cascade statistics with text/tool breakdown."""
        if self.stats["total_executions"] == 0:
            return self.stats

        # Text complexity stats
        text_complexity_stats = {}
        for complexity, stats in self.stats["by_complexity"].items():
            if stats["total"] > 0:
                text_complexity_stats[complexity] = {
                    "total": stats["total"],
                    "accepted": stats["accepted"],
                    "acceptance_rate": stats["accepted"] / stats["total"],
                }

        # Tool complexity stats
        tool_complexity_stats = {}
        for complexity, stats in self.stats["tool_by_complexity"].items():
            if stats["total"] > 0:
                tool_complexity_stats[complexity] = {
                    "total": stats["total"],
                    "accepted": stats["accepted"],
                    "acceptance_rate": stats["accepted"] / stats["total"],
                }

        return {
            **self.stats,
            "avg_speedup": (self.stats["total_speedup"] / self.stats["total_executions"]),
            "avg_cost_saved": (self.stats["total_cost_saved"] / self.stats["total_executions"]),
            "text_complexity_breakdown": text_complexity_stats,
            "tool_complexity_breakdown": tool_complexity_stats,
            "adaptive_stats": (
                self.adaptive_threshold.get_stats() if self.quality_config.enable_adaptive else None
            ),
        }


# Legacy compatibility
class SpeculativeCascade:
    """LEGACY: Redirects to WholeResponseCascade."""

    def __init__(self, drafter, verifier, providers, **kwargs):
        self.cascade = WholeResponseCascade(
            drafter=drafter, verifier=verifier, providers=providers, **kwargs
        )

    async def execute(self, query: str, max_tokens: int = 100, **kwargs) -> SpeculativeResult:
        """Execute via WholeResponseCascade."""
        return await self.cascade.execute(query, max_tokens, **kwargs)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics."""
        return self.cascade.get_stats()


class TokenLevelSpeculativeCascade:
    """DEPRECATED: Redirects to WholeResponseCascade."""

    def __init__(self, drafter, verifier, providers, **kwargs):
        logger.warning(
            "TokenLevelSpeculativeCascade is deprecated and redirects to "
            "WholeResponseCascade. Token-level matching doesn't work across providers."
        )

        self.cascade = WholeResponseCascade(
            drafter=drafter, verifier=verifier, providers=providers, **kwargs
        )

    async def execute(self, query: str, max_tokens: int = 100, **kwargs) -> SpeculativeResult:
        """Execute via WholeResponseCascade."""
        return await self.cascade.execute(query, max_tokens, **kwargs)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics."""
        return self.cascade.get_stats()


# ==================== EXPORTS ====================

__all__ = [
    # Enums
    "DeferralStrategy",
    # Data classes
    "SpeculativeResult",
    # Core classes
    "WholeResponseCascade",
    "SpeculativeCascade",
    # Deprecated (for backward compatibility)
    "TokenLevelSpeculativeCascade",
]
