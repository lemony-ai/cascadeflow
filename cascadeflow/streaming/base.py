"""
cascadeflow Streaming Module - WITH TELEMETRY COST INTEGRATION
===============================================================

✅ FIX #1: Explicit tools/tool_choice parameters in signature
✅ FIX #2: Actual draft confidence (not hardcoded 0.8)
✅ FIX #3: Kwargs filtering to prevent provider contamination
✅ FIX #4: Logprobs support with provider-aware fallback
✅ FIX #5: Tool + logprobs conflict resolved (OpenAI limitation)
✅ FIX #6: Correct parameter name validation (draft_content=)
🆕 FIX #7: Integrated CostCalculator from telemetry module
🆕 FIX #8: Proper cost aggregation (draft + verifier when cascaded)
🆕 FIX #9: Input token counting - query_text parameter added

Professional event-based streaming implementation with complete diagnostics
and centralized cost calculation.
"""

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# EVENT TYPES AND DATA STRUCTURES
# ============================================================================


class StreamEventType(Enum):
    """Types of streaming events."""

    ROUTING = "routing"
    CHUNK = "chunk"
    DRAFT_DECISION = "draft_decision"
    SWITCH = "switch"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StreamEvent:
    """Individual streaming event."""

    type: StreamEventType
    content: str = ""
    data: Optional[dict[str, Any]] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}

    @property
    def metadata(self):
        """Alias for data (backward compatibility)."""
        return self.data


# ============================================================================
# STREAMING CASCADE WRAPPER WITH COST CALCULATOR INTEGRATION
# ============================================================================


class StreamManager:
    """
    Manages streaming for cascade operations with integrated cost calculation.

    Wraps WholeResponseCascade to provide real-time event streaming
    without modifying the underlying cascade logic. Now uses CostCalculator
    from telemetry module for consistent cost calculations.
    """

    def __init__(self, cascade, verbose: bool = False):
        """
        Initialize stream manager with cost calculator.

        Args:
            cascade: WholeResponseCascade instance to wrap
            verbose: Enable verbose logging for debugging
        """
        self.cascade = cascade
        self.verbose = verbose

        # 🆕 Initialize CostCalculator from telemetry module
        try:
            from ..telemetry.cost_calculator import CostCalculator

            self.cost_calculator = CostCalculator(
                drafter=cascade.drafter, verifier=cascade.verifier, verbose=verbose
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

        if verbose:
            logger.setLevel(logging.INFO)

        logger.info("StreamManager initialized")

    def _calculate_cost_from_tokens(self, model_config, tokens: float) -> float:
        """
        Calculate cost from token count (fallback method).

        Args:
            model_config: ModelConfig with cost per 1K tokens
            tokens: Number of tokens used

        Returns:
            Cost in USD
        """
        return model_config.cost * (tokens / 1000)

    def _estimate_tokens_from_text(self, text: str) -> int:
        """
        Estimate token count from text (fallback method).

        Uses standard approximation: 1 token ≈ 0.75 words (1.3 tokens per word)

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
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
        query_text: str = "",  # 🆕 NEW: Added for input token counting
    ) -> dict[str, float]:
        """
        Calculate costs using CostCalculator or fallback method.

        🆕 FIXED: Now includes query_text for input token counting!

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

        # Fallback: Manual calculation (includes input tokens)
        query_input_tokens = self._estimate_tokens_from_text(query_text)
        draft_output_tokens = self._estimate_tokens_from_text(draft_content)
        draft_total_tokens = query_input_tokens + draft_output_tokens
        draft_cost = self._calculate_cost_from_tokens(self.cascade.drafter, draft_total_tokens)

        if draft_accepted:
            # Draft accepted - only paid for draft
            # Verifier would have used same input + similar output
            verifier_would_be_tokens = query_input_tokens + draft_output_tokens
            verifier_cost_avoided = self._calculate_cost_from_tokens(
                self.cascade.verifier, verifier_would_be_tokens
            )
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
            # Draft rejected - paid for both (both include input tokens)
            verifier_output_tokens = self._estimate_tokens_from_text(verifier_content)
            verifier_total_tokens = query_input_tokens + verifier_output_tokens
            verifier_cost = self._calculate_cost_from_tokens(
                self.cascade.verifier, verifier_total_tokens
            )
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

    def _calculate_confidence_from_logprobs(
        self, logprobs: list[float], provider_type: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate confidence from logprobs with provider-specific handling.

        Args:
            logprobs: List of logprob values
            provider_type: Provider type ('openai', 'groq', 'anthropic', etc.)

        Returns:
            Confidence score 0.0-1.0, or None if not available
        """
        if not logprobs:
            return None

        # Provider-specific handling
        if provider_type == "anthropic":
            # Anthropic doesn't provide logprobs
            return None

        try:
            import math

            # Calculate average logprob
            avg_logprob = sum(logprobs) / len(logprobs)

            # Convert to probability
            confidence = math.exp(avg_logprob)

            # Clamp to [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            if self.verbose:
                logger.info(f"Calculated confidence from logprobs: {confidence:.3f}")
            return confidence

        except (ValueError, OverflowError) as e:
            logger.warning(f"Failed to calculate confidence from logprobs: {e}")
            return None

    def _estimate_confidence_from_content(self, content: str, query: str) -> float:
        """
        Estimate confidence from content characteristics (fallback).

        Uses heuristics when logprobs unavailable:
        - Response length
        - Presence of uncertainty markers
        - Content structure

        Args:
            content: Generated content
            query: Original query

        Returns:
            Estimated confidence 0.0-1.0
        """
        confidence = 0.75  # Base confidence

        # Check for uncertainty markers
        uncertainty_markers = [
            "i'm not sure",
            "i don't know",
            "maybe",
            "possibly",
            "unclear",
            "uncertain",
            "cannot determine",
            "insufficient",
        ]
        content_lower = content.lower()

        if any(marker in content_lower for marker in uncertainty_markers):
            confidence -= 0.15

        # Very short responses might be uncertain
        if len(content.strip()) < 20:
            confidence -= 0.10

        # Longer, structured responses suggest confidence
        if len(content.split("\n")) > 3:
            confidence += 0.05

        # Clamp to reasonable range
        confidence = max(0.50, min(0.85, confidence))

        if self.verbose:
            logger.info(f"Estimated confidence from content: {confidence:.3f}")
        return confidence

    # ========================================================================
    # MAIN STREAMING METHOD
    # ========================================================================

    async def stream(
        self,
        query: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        complexity: Optional[str] = None,
        routing_strategy: str = "cascade",
        is_direct_route: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream cascade execution with real-time events and accurate cost tracking.

        🆕 FIXED: Now properly includes input tokens in all cost calculations!

        Args:
            query: User query to process
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)
            complexity: Query complexity (trivial/simple/moderate/hard/expert)
            routing_strategy: "cascade" or "direct" (for metadata)
            is_direct_route: If True, skip cascade and go straight to verifier
            tools: List of tool definitions for function calling
            tool_choice: Tool selection strategy
            **kwargs: Additional provider parameters

        Yields:
            StreamEvent objects with type, content, and data
        """
        try:
            logger.info(f"Starting streaming execution for query: {query[:50]}...")

            # ================================================================
            # FIX #3: Filter kwargs to prevent contamination
            # ================================================================
            provider_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                not in {"routing_strategy", "is_direct_route", "complexity", "tools", "tool_choice"}
            }

            # Add tools and tool_choice if provided
            if tools is not None:
                provider_kwargs["tools"] = tools
            if tool_choice is not None:
                provider_kwargs["tool_choice"] = tool_choice

            # ================================================================
            # FIX #5: Add logprobs ONLY if no tools present (OpenAI limitation)
            # ================================================================
            logprobs_kwargs = provider_kwargs.copy()

            provider_type = self.cascade.drafter.provider
            has_tools = tools is not None or "tools" in provider_kwargs

            if provider_type in ["openai"] and not has_tools:
                logprobs_kwargs.update({"logprobs": True, "top_logprobs": 5})
                if self.verbose:
                    logger.info(f"Logprobs enabled for {provider_type} (no tools)")
            elif has_tools and self.verbose:
                logger.info("Logprobs disabled: tools present (OpenAI limitation)")

            # ================================================================
            # STAGE 0: Emit Routing Event
            # ================================================================

            yield StreamEvent(
                type=StreamEventType.ROUTING,
                content="",
                data={"strategy": routing_strategy, "complexity": complexity or "unknown"},
            )

            # ================================================================
            # HANDLE DIRECT ROUTING (when is_direct_route=True)
            # ================================================================

            if is_direct_route:
                logger.info("Direct routing - using verifier model only")

                verifier_provider = self.cascade.providers[self.cascade.verifier.provider]
                overall_start_time = time.time()
                verifier_start_time = time.time()
                verifier_chunks = []
                verifier_content = ""

                verifier_logprobs_kwargs = provider_kwargs.copy()
                has_tools = tools is not None or "tools" in provider_kwargs

                if self.cascade.verifier.provider in ["openai"] and not has_tools:
                    verifier_logprobs_kwargs.update({"logprobs": True, "top_logprobs": 5})

                if hasattr(verifier_provider, "stream"):
                    async for chunk in verifier_provider.stream(
                        model=self.cascade.verifier.name,
                        prompt=query,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **verifier_logprobs_kwargs,
                    ):
                        verifier_chunks.append(chunk)
                        yield StreamEvent(
                            type=StreamEventType.CHUNK,
                            content=chunk,
                            data={
                                "model": self.cascade.verifier.name,
                                "phase": "direct",
                                "provider": self.cascade.verifier.provider,
                            },
                        )
                    verifier_content = "".join(verifier_chunks)
                else:
                    response = await verifier_provider.complete(
                        model=self.cascade.verifier.name,
                        prompt=query,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **provider_kwargs,
                    )
                    verifier_content = response.content
                    yield StreamEvent(
                        type=StreamEventType.CHUNK,
                        content=verifier_content,
                        data={
                            "model": self.cascade.verifier.name,
                            "phase": "direct",
                            "provider": self.cascade.verifier.provider,
                            "streaming_supported": False,
                        },
                    )

                verifier_latency_ms = (time.time() - verifier_start_time) * 1000
                total_latency_ms = (time.time() - overall_start_time) * 1000

                # 🆕 Use CostCalculator for direct route WITH query_text
                costs = self._calculate_costs(
                    draft_content="",  # No draft in direct route
                    verifier_content=verifier_content,
                    draft_accepted=False,  # Force verifier cost calculation
                    query_text=query,  # 🆕 NEW: Pass query for input tokens!
                )

                result_data = {
                    "content": verifier_content,
                    "model_used": self.cascade.verifier.name,
                    "draft_accepted": None,
                    "cascaded": False,
                    "reason": "direct_routing",
                    "draft_model": None,
                    "drafter_model": None,
                    "verifier_model": self.cascade.verifier.name,
                    "quality_score": None,
                    "validation_score": None,
                    "draft_confidence": None,
                    "verifier_confidence": 0.95,
                    "quality_threshold": None,
                    "quality_check_passed": None,
                    "rejection_reason": None,
                    "latency_ms": total_latency_ms,
                    "total_latency_ms": total_latency_ms,
                    "draft_latency_ms": 0.0,
                    "drafter_latency_ms": 0.0,
                    "verifier_latency_ms": verifier_latency_ms,
                    "quality_check_ms": 0.0,
                    "quality_overhead_ms": 0.0,
                    "decision_overhead_ms": 0.0,
                    "total_cost": costs["verifier_cost"],  # 🆕 From calculator
                    "draft_cost": 0.0,
                    "drafter_cost": 0.0,
                    "verifier_cost": costs["verifier_cost"],  # 🆕 From calculator
                    "cost_saved": 0.0,
                    "tokens_drafted": 0,
                    "draft_tokens": 0,
                    "tokens_verified": costs["verifier_tokens"],  # 🆕 From calculator
                    "verifier_tokens": costs["verifier_tokens"],  # 🆕 From calculator
                    "total_tokens": costs["verifier_tokens"],  # 🆕 From calculator
                    "speedup": 1.0,
                    "response_length": len(verifier_content),
                    "response_word_count": len(verifier_content.split()),
                    "draft_response": None,
                    "verifier_response": verifier_content,
                    "bigonly_cost": costs["verifier_cost"],  # 🆕 From calculator
                    "bigonly_latency_ms": verifier_latency_ms,
                    "direct_equivalent_ms": verifier_latency_ms,
                    "cascade_overhead_ms": 0.0,
                }

                yield StreamEvent(
                    type=StreamEventType.COMPLETE, content="", data={"result": result_data}
                )

                logger.info(f"Direct routing complete: {total_latency_ms:.0f}ms")
                return

            # ================================================================
            # NORMAL CASCADE PATH (when is_direct_route=False)
            # ================================================================

            draft_provider = self.cascade.providers[self.cascade.drafter.provider]
            verifier_provider = self.cascade.providers[self.cascade.verifier.provider]

            overall_start_time = time.time()

            # ================================================================
            # STAGE 1: Stream Draft Generation
            # ================================================================

            draft_start_time = time.time()
            draft_chunks = []
            draft_content = ""
            draft_logprobs = []

            if hasattr(draft_provider, "stream"):
                logger.info(f"Streaming from draft model: {self.cascade.drafter.name}")

                async for chunk in draft_provider.stream(
                    model=self.cascade.drafter.name,
                    prompt=query,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **logprobs_kwargs,
                ):
                    draft_chunks.append(chunk)

                    if hasattr(chunk, "logprobs") and chunk.logprobs:
                        draft_logprobs.extend(chunk.logprobs)

                    yield StreamEvent(
                        type=StreamEventType.CHUNK,
                        content=chunk,
                        data={
                            "model": self.cascade.drafter.name,
                            "phase": "draft",
                            "provider": self.cascade.drafter.provider,
                        },
                    )

                draft_content = "".join(draft_chunks)
                draft_latency_ms = (time.time() - draft_start_time) * 1000
                logger.info(
                    f"Draft streaming complete: {len(draft_chunks)} chunks, {draft_latency_ms:.0f}ms"
                )

            else:
                logger.info("Provider doesn't support streaming, using complete()")

                response = await draft_provider.complete(
                    model=self.cascade.drafter.name,
                    prompt=query,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **provider_kwargs,
                )
                draft_content = response.content
                draft_latency_ms = (time.time() - draft_start_time) * 1000

                yield StreamEvent(
                    type=StreamEventType.CHUNK,
                    content=draft_content,
                    data={
                        "model": self.cascade.drafter.name,
                        "phase": "draft",
                        "provider": self.cascade.drafter.provider,
                        "streaming_supported": False,
                    },
                )

            # ================================================================
            # FIX #2: Calculate Actual Draft Confidence from Logprobs
            # ================================================================

            draft_confidence = self._calculate_confidence_from_logprobs(
                draft_logprobs, self.cascade.drafter.provider
            )

            if draft_confidence is None:
                draft_confidence = self._estimate_confidence_from_content(draft_content, query)
                logger.info(f"Estimated draft confidence (no logprobs): {draft_confidence:.3f}")
            else:
                logger.info(f"Calculated draft confidence from logprobs: {draft_confidence:.3f}")

            # ================================================================
            # STAGE 2: Validate Draft
            # ================================================================

            logger.info("Validating draft quality...")
            quality_check_start = time.time()

            validation_result = self.cascade.quality_validator.validate(
                draft_content=draft_content,
                query=query,
                confidence=draft_confidence,
                complexity=complexity,
            )

            quality_check_ms = (time.time() - quality_check_start) * 1000
            draft_accepted = validation_result.passed

            if self.verbose:
                logger.info(
                    f"Draft validation: {'ACCEPTED' if draft_accepted else 'REJECTED'} "
                    f"(score: {validation_result.score:.2f}, "
                    f"confidence: {draft_confidence:.2f}, "
                    f"overhead: {quality_check_ms:.1f}ms)"
                )

            # ================================================================
            # STAGE 2.5: Emit Draft Decision Event
            # ================================================================

            decision_overhead_start = time.time()

            yield StreamEvent(
                type=StreamEventType.DRAFT_DECISION,
                content="",
                data={
                    "accepted": draft_accepted,
                    "score": validation_result.score,
                    "confidence": draft_confidence,
                    "draft_model": self.cascade.drafter.name,
                    "verifier_model": self.cascade.verifier.name,
                    "reason": "quality_passed" if draft_accepted else "quality_failed",
                    "checks_passed": validation_result.passed,
                    "quality_threshold": self.cascade.quality_validator.config.confidence_thresholds.get(
                        complexity or "moderate", 0.5
                    ),
                },
            )

            decision_overhead_ms = (time.time() - decision_overhead_start) * 1000

            # ================================================================
            # STAGE 3: Handle Result - Build Complete Metadata
            # ================================================================

            if draft_accepted:
                # ============================================================
                # DRAFT ACCEPTED PATH
                # ============================================================
                logger.info("Draft accepted, no cascade needed")

                # 🆕 Use CostCalculator WITH query_text
                costs = self._calculate_costs(
                    draft_content=draft_content,
                    verifier_content=None,
                    draft_accepted=True,
                    query_text=query,  # 🆕 NEW: Pass query for input tokens!
                )

                result_data = {
                    "content": draft_content,
                    "model_used": self.cascade.drafter.name,
                    "draft_accepted": True,
                    "cascaded": False,
                    "reason": "draft_accepted",
                    "draft_model": self.cascade.drafter.name,
                    "drafter_model": self.cascade.drafter.name,
                    "verifier_model": self.cascade.verifier.name,
                    "quality_score": validation_result.score,
                    "validation_score": validation_result.score,
                    "draft_confidence": draft_confidence,
                    "verifier_confidence": None,
                    "quality_threshold": self.cascade.quality_validator.config.confidence_thresholds.get(
                        complexity or "moderate", 0.5
                    ),
                    "quality_check_passed": True,
                    "rejection_reason": None,
                    "latency_ms": (time.time() - overall_start_time) * 1000,
                    "total_latency_ms": (time.time() - overall_start_time) * 1000,
                    "draft_latency_ms": draft_latency_ms,
                    "drafter_latency_ms": draft_latency_ms,
                    "verifier_latency_ms": 0.0,
                    "quality_check_ms": quality_check_ms,
                    "quality_overhead_ms": quality_check_ms,
                    "decision_overhead_ms": decision_overhead_ms,
                    "total_cost": costs["total_cost"],  # 🆕 From calculator
                    "draft_cost": costs["draft_cost"],  # 🆕 From calculator
                    "drafter_cost": costs["draft_cost"],  # 🆕 From calculator
                    "verifier_cost": 0.0,
                    "cost_saved": costs["cost_saved"],  # 🆕 From calculator
                    "tokens_drafted": costs["draft_tokens"],  # 🆕 From calculator (includes input!)
                    "draft_tokens": costs["draft_tokens"],  # 🆕 From calculator (includes input!)
                    "tokens_verified": 0,
                    "verifier_tokens": 0,
                    "total_tokens": costs["total_tokens"],  # 🆕 From calculator
                    "speedup": 1.5,
                    "response_length": len(draft_content),
                    "response_word_count": len(draft_content.split()),
                    "draft_response": draft_content,
                    "verifier_response": None,
                    "bigonly_cost": costs["draft_cost"] + costs["cost_saved"],  # 🆕 Calculated
                    "bigonly_latency_ms": self.cascade.verifier.speed_ms,
                    "direct_equivalent_ms": draft_latency_ms * 1.5,
                    "cascade_overhead_ms": quality_check_ms + decision_overhead_ms,
                }

            else:
                # ============================================================
                # DRAFT REJECTED PATH - CASCADE TO VERIFIER
                # ============================================================
                logger.info(f"Draft rejected, cascading to {self.cascade.verifier.name}")

                yield StreamEvent(
                    type=StreamEventType.SWITCH,
                    content=f"⤴ Cascading to {self.cascade.verifier.name}",
                    data={
                        "from_model": self.cascade.drafter.name,
                        "to_model": self.cascade.verifier.name,
                        "reason": "Quality threshold not met",
                        "draft_confidence": draft_confidence,
                        "quality_threshold": self.cascade.quality_validator.config.confidence_thresholds.get(
                            complexity or "moderate", 0.5
                        ),
                    },
                )

                # ============================================================
                # STAGE 4: Stream Verifier Generation
                # ============================================================

                verifier_start_time = time.time()
                verifier_chunks = []
                verifier_content = ""

                verifier_logprobs_kwargs = provider_kwargs.copy()
                has_tools = tools is not None or "tools" in provider_kwargs

                if self.cascade.verifier.provider in ["openai"] and not has_tools:
                    verifier_logprobs_kwargs.update({"logprobs": True, "top_logprobs": 5})

                if hasattr(verifier_provider, "stream"):
                    logger.info(f"Streaming from verifier model: {self.cascade.verifier.name}")

                    async for chunk in verifier_provider.stream(
                        model=self.cascade.verifier.name,
                        prompt=query,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **verifier_logprobs_kwargs,
                    ):
                        verifier_chunks.append(chunk)

                        yield StreamEvent(
                            type=StreamEventType.CHUNK,
                            content=chunk,
                            data={
                                "model": self.cascade.verifier.name,
                                "phase": "verifier",
                                "provider": self.cascade.verifier.provider,
                            },
                        )

                    verifier_content = "".join(verifier_chunks)
                    verifier_latency_ms = (time.time() - verifier_start_time) * 1000
                    logger.info(
                        f"Verifier streaming complete: {len(verifier_chunks)} chunks, {verifier_latency_ms:.0f}ms"
                    )

                else:
                    logger.info("Verifier doesn't support streaming, using complete()")

                    response = await verifier_provider.complete(
                        model=self.cascade.verifier.name,
                        prompt=query,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **provider_kwargs,
                    )
                    verifier_content = response.content
                    verifier_latency_ms = (time.time() - verifier_start_time) * 1000

                    yield StreamEvent(
                        type=StreamEventType.CHUNK,
                        content=verifier_content,
                        data={
                            "model": self.cascade.verifier.name,
                            "phase": "verifier",
                            "provider": self.cascade.verifier.provider,
                            "streaming_supported": False,
                        },
                    )

                # 🆕 Use CostCalculator for cascade path WITH query_text
                costs = self._calculate_costs(
                    draft_content=draft_content,
                    verifier_content=verifier_content,
                    draft_accepted=False,
                    query_text=query,  # 🆕 NEW: Pass query for input tokens!
                )

                result_data = {
                    "content": verifier_content,
                    "model_used": self.cascade.verifier.name,
                    "draft_accepted": False,
                    "cascaded": True,
                    "reason": "cascade_to_verifier",
                    "draft_model": self.cascade.drafter.name,
                    "drafter_model": self.cascade.drafter.name,
                    "verifier_model": self.cascade.verifier.name,
                    "quality_score": validation_result.score,
                    "validation_score": validation_result.score,
                    "draft_confidence": draft_confidence,
                    "verifier_confidence": 0.95,
                    "quality_threshold": self.cascade.quality_validator.config.confidence_thresholds.get(
                        complexity or "moderate", 0.5
                    ),
                    "quality_check_passed": False,
                    "rejection_reason": "quality_threshold_not_met",
                    "latency_ms": (time.time() - overall_start_time) * 1000,
                    "total_latency_ms": (time.time() - overall_start_time) * 1000,
                    "draft_latency_ms": draft_latency_ms,
                    "drafter_latency_ms": draft_latency_ms,
                    "verifier_latency_ms": verifier_latency_ms,
                    "quality_check_ms": quality_check_ms,
                    "quality_overhead_ms": quality_check_ms,
                    "decision_overhead_ms": decision_overhead_ms,
                    "total_cost": costs["total_cost"],  # 🆕 CORRECT: draft + verifier (with input!)
                    "draft_cost": costs["draft_cost"],  # 🆕 From calculator (includes input!)
                    "drafter_cost": costs["draft_cost"],  # 🆕 From calculator (includes input!)
                    "verifier_cost": costs["verifier_cost"],  # 🆕 From calculator (includes input!)
                    "cost_saved": costs["cost_saved"],  # 🆕 From calculator (negative)
                    "tokens_drafted": costs["draft_tokens"],  # 🆕 From calculator (includes input!)
                    "draft_tokens": costs["draft_tokens"],  # 🆕 From calculator (includes input!)
                    "tokens_verified": costs[
                        "verifier_tokens"
                    ],  # 🆕 From calculator (includes input!)
                    "verifier_tokens": costs[
                        "verifier_tokens"
                    ],  # 🆕 From calculator (includes input!)
                    "total_tokens": costs["total_tokens"],  # 🆕 From calculator
                    "speedup": 0.0,
                    "response_length": len(verifier_content),
                    "response_word_count": len(verifier_content.split()),
                    "draft_response": draft_content,
                    "verifier_response": verifier_content,
                    "bigonly_cost": costs["verifier_cost"],  # 🆕 From calculator
                    "bigonly_latency_ms": self.cascade.verifier.speed_ms,
                    "direct_equivalent_ms": verifier_latency_ms,
                    "cascade_overhead_ms": draft_latency_ms
                    + quality_check_ms
                    + decision_overhead_ms,
                }

            # ================================================================
            # STAGE 5: Emit Complete Event
            # ================================================================

            result_data["latency_ms"] = (time.time() - overall_start_time) * 1000
            result_data["total_latency_ms"] = result_data["latency_ms"]

            yield StreamEvent(
                type=StreamEventType.COMPLETE, content="", data={"result": result_data}
            )

            logger.info(
                f"Streaming execution complete: {result_data['latency_ms']:.0f}ms total, "
                f"draft_accepted={draft_accepted}, confidence={draft_confidence:.3f}, "
                f"total_cost=${result_data['total_cost']:.6f}"
            )

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield StreamEvent(
                type=StreamEventType.ERROR,
                content=str(e),
                data={"error": str(e), "type": type(e).__name__},
            )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "StreamEventType",
    "StreamEvent",
    "StreamManager",
]
