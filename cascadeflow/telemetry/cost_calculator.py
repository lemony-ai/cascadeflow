"""
Cost Calculator - Single Source of Truth for Cost Calculations

FIXED VERSION: Now properly accounts for BOTH input and output tokens!

This module handles ALL cost calculations for cascadeflow, extracting the logic
from agent.py, speculative.py, and base.py into a centralized, testable component.

Architecture:
    - CostCalculator: Pure calculation logic (stateless, deterministic)
    - CostBreakdown: Structured cost data with transparency
    - Works alongside CostTracker (which tracks costs over time)

Benefits:
    - Single responsibility (SRP)
    - Easy to test independently
    - No duplication across files
    - Easy to extend (tiered pricing, caching, budgets)
    - Swappable implementations (custom cost models)

Usage:
    >>> from cascadeflow.telemetry import CostCalculator
    >>>
    >>> calculator = CostCalculator(
    ...     drafter=ModelConfig(name='gpt-3.5-turbo', cost=0.002),
    ...     verifier=ModelConfig(name='gpt-4o', cost=0.03)
    ... )
    >>>
    >>> # Calculate from SpeculativeResult with query
    >>> breakdown = calculator.calculate(spec_result, query_text="What is 2+2?")
    >>> print(f"Total: ${breakdown.total_cost:.6f}")
    >>> print(f"Draft: ${breakdown.draft_cost:.6f}")
    >>> print(f"Verifier: ${breakdown.verifier_cost:.6f}")
    >>> print(f"Saved: ${breakdown.cost_saved:.6f}")

Created: October 20, 2025
Author: cascadeflow Team
Fixed: October 20, 2025 - Added input token support
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# COST BREAKDOWN DATA STRUCTURE
# ============================================================================


@dataclass
class CostBreakdown:
    """
    Detailed cost breakdown for a cascade execution.

    Provides complete transparency into where costs come from, enabling
    detailed cost analysis, optimization, and monitoring.

    Attributes:
        draft_cost: Cost of draft model execution (input + output tokens)
        verifier_cost: Cost of verifier model execution (0 if draft accepted)
        total_cost: Total cost (draft + verifier)
        cost_saved: Cost savings vs using only verifier
                   Positive = saved money, Negative = wasted draft cost
        bigonly_cost: What it would cost using only the verifier model
        savings_percent: Percentage savings vs bigonly approach

        draft_tokens: Number of tokens used by draft model (input + output)
        verifier_tokens: Number of tokens used by verifier model (input + output)
        total_tokens: Total tokens across both models

        was_cascaded: Whether cascade system was used
        draft_accepted: Whether draft was accepted (if cascaded)

        metadata: Additional context and diagnostics

    Example:
        >>> breakdown = CostBreakdown(
        ...     draft_cost=0.00008,  # Now includes input tokens!
        ...     verifier_cost=0.0,
        ...     total_cost=0.00008,
        ...     cost_saved=0.0015,
        ...     bigonly_cost=0.00158,
        ...     savings_percent=94.9,
        ...     draft_tokens=65,  # input (15) + output (50)
        ...     verifier_tokens=0,
        ...     total_tokens=65,
        ...     was_cascaded=True,
        ...     draft_accepted=True
        ... )
        >>> print(f"Saved {breakdown.savings_percent:.1f}%!")
        Saved 94.9%!
    """

    # Individual costs
    draft_cost: float
    verifier_cost: float

    # Aggregated
    total_cost: float

    # Savings analysis
    cost_saved: float
    bigonly_cost: float
    savings_percent: float

    # Token breakdown (now includes input + output!)
    draft_tokens: int
    verifier_tokens: int
    total_tokens: int

    # Metadata
    was_cascaded: bool
    draft_accepted: bool
    metadata: dict[str, Any] = None

    def __post_init__(self):
        """Ensure metadata is initialized."""
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            Dict with all cost breakdown fields
        """
        return asdict(self)

    def __repr__(self) -> str:
        """Human-readable representation."""
        status = "accepted" if self.draft_accepted else "rejected"
        return (
            f"CostBreakdown(total=${self.total_cost:.6f}, "
            f"draft=${self.draft_cost:.6f}, "
            f"verifier=${self.verifier_cost:.6f}, "
            f"saved=${self.cost_saved:.6f} ({self.savings_percent:.1f}%), "
            f"draft_{status})"
        )


# ============================================================================
# COST CALCULATOR
# ============================================================================


class CostCalculator:
    """
    Calculate costs for cascade executions.

    FIXED: Now properly accounts for BOTH input and output tokens!

    Single source of truth for ALL cost calculations in cascadeflow.
    Handles both accepted and rejected drafts with proper aggregation.

    Architecture:
        1. Extracts costs from SpeculativeResult metadata
        2. Calculates baseline (big-only) costs for comparison
        3. Computes savings and provides detailed breakdown
        4. Handles fallback calculations if metadata missing
        5. FIXED: Includes input tokens in all calculations

    Key Methods:
        - calculate(): Main API - compute costs from a result
        - calculate_from_tokens(): Direct calculation from token counts
        - estimate_tokens(): Fallback token estimation

    Future Extensions:
        - Tiered pricing (volume discounts)
        - Caching (deduplication savings)
        - Budget tracking and alerts
        - Cost forecasting
        - Custom cost models per provider

    Example:
        >>> calculator = CostCalculator(
        ...     drafter=ModelConfig(name='gpt-3.5-turbo', cost=0.002),
        ...     verifier=ModelConfig(name='gpt-4o', cost=0.03)
        ... )
        >>>
        >>> # From cascade result WITH query
        >>> breakdown = calculator.calculate(spec_result, query_text="What is 2+2?")
        >>>
        >>> # Direct from tokens (now with input tokens!)
        >>> breakdown = calculator.calculate_from_tokens(
        ...     draft_output_tokens=50,
        ...     verifier_output_tokens=150,
        ...     query_input_tokens=10,  # NEW!
        ...     draft_accepted=False
        ... )
    """

    def __init__(self, drafter, verifier, verbose: bool = False):  # ModelConfig  # ModelConfig
        """
        Initialize cost calculator.

        Args:
            drafter: Draft model configuration with cost info
            verifier: Verifier model configuration with cost info
            verbose: Enable verbose logging for debugging
        """
        self.drafter = drafter
        self.verifier = verifier
        self.verbose = verbose

        if self.verbose:
            logger.info(
                f"CostCalculator initialized:\n"
                f"  Drafter: {drafter.name} (${drafter.cost}/1K tokens)\n"
                f"  Verifier: {verifier.name} (${verifier.cost}/1K tokens)"
            )

    # ========================================================================
    # MAIN API
    # ========================================================================

    def calculate(self, result, query_text: str = "") -> CostBreakdown:
        """
        Calculate comprehensive cost breakdown from result.

        FIXED: Now accepts query_text to properly count input tokens!

        Main entry point for cost calculation. Automatically handles both
        accepted and rejected drafts, extracting costs from metadata or
        calculating from content if needed.

        Args:
            result: SpeculativeResult from cascade execution
            query_text: Original query text for input token counting (NEW!)

        Returns:
            CostBreakdown with complete cost analysis

        Example:
            >>> breakdown = calculator.calculate(
            ...     spec_result,
            ...     query_text="What is the capital of France?"
            ... )
            >>> if breakdown.draft_accepted:
            ...     print(f"Saved ${breakdown.cost_saved:.6f}!")
            ... else:
            ...     print(f"Wasted ${abs(breakdown.cost_saved):.6f}")
        """
        # Determine if draft was accepted
        draft_accepted = getattr(result, "draft_accepted", False)

        # 🆕 Estimate input tokens from query
        query_input_tokens = self.estimate_tokens(query_text) if query_text else 0

        if draft_accepted:
            return self._calculate_accepted_costs(result, query_input_tokens)
        else:
            return self._calculate_rejected_costs(result, query_input_tokens)

    def calculate_from_tokens(
        self,
        draft_output_tokens: int,
        verifier_output_tokens: int,
        draft_accepted: bool,
        query_input_tokens: int = 0,  # 🆕 NEW parameter!
    ) -> CostBreakdown:
        """
        Calculate costs directly from token counts.

        FIXED: Now includes query_input_tokens for accurate cost calculation!

        Useful when you have token counts but not a full result object.

        Args:
            draft_output_tokens: OUTPUT tokens from draft model response
            verifier_output_tokens: OUTPUT tokens from verifier model response
            draft_accepted: Whether draft was accepted
            query_input_tokens: INPUT tokens from query/prompt (NEW!)

        Returns:
            CostBreakdown with cost analysis

        Example:
            >>> breakdown = calculator.calculate_from_tokens(
            ...     draft_output_tokens=10,
            ...     verifier_output_tokens=0,
            ...     draft_accepted=True,
            ...     query_input_tokens=5  # NEW!
            ... )
            >>> print(f"Draft cost: ${breakdown.draft_cost:.6f}")
            >>> # Now includes BOTH input (5) and output (10) = 15 tokens total
        """
        # 🆕 Add input tokens to get TOTAL tokens
        draft_total_tokens = query_input_tokens + draft_output_tokens

        # 🔧 CRITICAL FIX: When draft accepted, verifier was NOT called
        # So verifier should have 0 tokens, not query_input_tokens + verifier_output_tokens
        if draft_accepted:
            verifier_total_tokens = 0  # Verifier never called!
            # For bigonly calculation, we estimate what verifier would have cost
            bigonly_tokens = query_input_tokens + draft_output_tokens
        else:
            # When draft rejected, BOTH models were called (both get input tokens)
            verifier_total_tokens = query_input_tokens + verifier_output_tokens
            bigonly_tokens = verifier_total_tokens

        # Calculate individual costs with BOTH input and output
        draft_cost = self._calculate_model_cost(self.drafter, draft_total_tokens)
        verifier_cost = self._calculate_model_cost(self.verifier, verifier_total_tokens)

        # Total cost
        total_cost = draft_cost + verifier_cost

        # Calculate savings
        if draft_accepted:
            # Saved by using draft instead of verifier
            # Verifier would have used same input + similar output
            bigonly_cost = self._calculate_model_cost(self.verifier, bigonly_tokens)
            cost_saved = bigonly_cost - draft_cost
        else:
            # Both models called - no savings (wasted draft cost)
            bigonly_cost = verifier_cost  # Would have called verifier anyway
            cost_saved = -draft_cost  # Negative = wasted

        # Calculate savings percentage
        savings_percent = (cost_saved / bigonly_cost * 100) if bigonly_cost > 0 else 0.0

        if self.verbose:
            logger.debug(
                f"Token breakdown: query_input={query_input_tokens}, "
                f"draft_output={draft_output_tokens}, "
                f"verifier_output={verifier_output_tokens}, "
                f"draft_total={draft_total_tokens}, "
                f"verifier_total={verifier_total_tokens}, "
                f"draft_accepted={draft_accepted}"
            )

        return CostBreakdown(
            draft_cost=draft_cost,
            verifier_cost=verifier_cost,
            total_cost=total_cost,
            cost_saved=cost_saved,
            bigonly_cost=bigonly_cost,
            savings_percent=savings_percent,
            draft_tokens=draft_total_tokens,
            verifier_tokens=verifier_total_tokens,
            total_tokens=draft_total_tokens + verifier_total_tokens,
            was_cascaded=True,
            draft_accepted=draft_accepted,
            metadata={
                "calculation_method": "from_tokens",
                "drafter_model": self.drafter.name,
                "verifier_model": self.verifier.name,
                "query_input_tokens": query_input_tokens,  # 🆕 Track this
                "draft_output_tokens": draft_output_tokens,
                "verifier_output_tokens": verifier_output_tokens,
            },
        )

    # ========================================================================
    # INTERNAL CALCULATION METHODS
    # ========================================================================

    def _calculate_accepted_costs(
        self, result, query_input_tokens: int = 0  # 🆕 NEW parameter
    ) -> CostBreakdown:
        """
        Calculate costs when draft was accepted.

        FIXED: Now includes input tokens from query!

        Only drafter was used, verifier was skipped. This is the ideal case
        for cascade cost savings.

        Args:
            result: SpeculativeResult with draft_accepted=True
            query_input_tokens: Number of input tokens from query (NEW!)

        Returns:
            CostBreakdown with savings analysis
        """
        # Extract or calculate draft OUTPUT tokens
        draft_output_tokens = self._extract_or_estimate_tokens(result, "draft")

        # 🆕 Add input tokens to get TOTAL tokens
        draft_total_tokens = query_input_tokens + draft_output_tokens

        # Calculate draft cost with BOTH input and output
        draft_cost = self._calculate_model_cost(self.drafter, draft_total_tokens)

        # 🔧 CRITICAL FIX: Verifier was NOT called, so 0 tokens and $0 cost
        verifier_cost = 0.0
        verifier_tokens = 0

        # Calculate what verifier would have cost (for savings analysis)
        # 🆕 Include input tokens in bigonly calculation
        verifier_total_tokens_estimate = query_input_tokens + draft_output_tokens
        bigonly_cost = self._calculate_model_cost(self.verifier, verifier_total_tokens_estimate)

        # Savings = avoided verifier cost - draft cost
        cost_saved = bigonly_cost - draft_cost
        savings_percent = (cost_saved / bigonly_cost * 100) if bigonly_cost > 0 else 0.0

        if self.verbose:
            logger.debug(
                f"Draft accepted: input_tokens={query_input_tokens}, "
                f"output_tokens={draft_output_tokens}, "
                f"total_tokens={draft_total_tokens}, "
                f"draft=${draft_cost:.6f}, "
                f"saved=${cost_saved:.6f} ({savings_percent:.1f}%)"
            )

        return CostBreakdown(
            draft_cost=draft_cost,
            verifier_cost=verifier_cost,
            total_cost=draft_cost,  # Only draft cost
            cost_saved=cost_saved,
            bigonly_cost=bigonly_cost,
            savings_percent=savings_percent,
            draft_tokens=draft_total_tokens,
            verifier_tokens=verifier_tokens,  # 0 tokens
            total_tokens=draft_total_tokens,  # Only draft tokens
            was_cascaded=True,
            draft_accepted=True,
            metadata={
                "calculation_method": "accepted_draft",
                "drafter_model": self.drafter.name,
                "verifier_model": self.verifier.name,
                "query_input_tokens": query_input_tokens,  # 🆕 Track this
                "draft_output_tokens": draft_output_tokens,
            },
        )

    def _calculate_rejected_costs(
        self, result, query_input_tokens: int = 0  # 🆕 NEW parameter
    ) -> CostBreakdown:
        """
        Calculate costs when draft was rejected.

        FIXED: Now includes input tokens for BOTH models!

        BOTH drafter and verifier were called - costs must be aggregated.
        This is the fix for the bug where only one cost was shown.

        Args:
            result: SpeculativeResult with draft_accepted=False
            query_input_tokens: Number of input tokens from query (NEW!)

        Returns:
            CostBreakdown with aggregated costs
        """
        # Extract OUTPUT tokens for both models
        draft_output_tokens = self._extract_or_estimate_tokens(result, "draft")
        verifier_output_tokens = self._extract_or_estimate_tokens(result, "verifier")

        # 🆕 Add input tokens to BOTH models (both were called!)
        draft_total_tokens = query_input_tokens + draft_output_tokens
        verifier_total_tokens = query_input_tokens + verifier_output_tokens

        # Calculate costs with BOTH input and output
        draft_cost = self._calculate_model_cost(self.drafter, draft_total_tokens)
        verifier_cost = self._calculate_model_cost(self.verifier, verifier_total_tokens)

        # Total cost = both models (THIS IS THE KEY FIX!)
        total_cost = draft_cost + verifier_cost

        # Calculate big-only baseline (just verifier with input tokens)
        bigonly_cost = verifier_cost  # Would have called verifier anyway

        # No savings - wasted draft cost
        cost_saved = -draft_cost  # Negative = additional cost wasted
        savings_percent = (cost_saved / bigonly_cost * 100) if bigonly_cost > 0 else 0.0

        if self.verbose:
            logger.debug(
                f"Draft rejected: input_tokens={query_input_tokens}, "
                f"draft_output={draft_output_tokens}, "
                f"verifier_output={verifier_output_tokens}, "
                f"draft_total={draft_total_tokens}, "
                f"verifier_total={verifier_total_tokens}, "
                f"draft=${draft_cost:.6f}, "
                f"verifier=${verifier_cost:.6f}, "
                f"total=${total_cost:.6f}, "
                f"wasted=${abs(cost_saved):.6f}"
            )

        return CostBreakdown(
            draft_cost=draft_cost,
            verifier_cost=verifier_cost,
            total_cost=total_cost,  # ← PROPERLY AGGREGATED!
            cost_saved=cost_saved,
            bigonly_cost=bigonly_cost,
            savings_percent=savings_percent,
            draft_tokens=draft_total_tokens,
            verifier_tokens=verifier_total_tokens,
            total_tokens=draft_total_tokens + verifier_total_tokens,
            was_cascaded=True,
            draft_accepted=False,
            metadata={
                "calculation_method": "rejected_draft",
                "drafter_model": self.drafter.name,
                "verifier_model": self.verifier.name,
                "query_input_tokens": query_input_tokens,  # 🆕 Track this
                "draft_output_tokens": draft_output_tokens,
                "verifier_output_tokens": verifier_output_tokens,
            },
        )

    # ========================================================================
    # COST EXTRACTION METHODS
    # ========================================================================

    def _extract_or_calculate_draft_cost(self, result) -> float:
        """
        Extract draft cost from metadata or calculate from tokens.

        Tries metadata first for accuracy, falls back to calculation.

        Args:
            result: SpeculativeResult

        Returns:
            Draft cost in dollars
        """
        # Try metadata first (most accurate)
        if hasattr(result, "metadata") and result.metadata:
            draft_cost = result.metadata.get("draft_cost", 0.0)
            if draft_cost > 0:
                if self.verbose:
                    logger.debug(f"Extracted draft_cost from metadata: ${draft_cost:.6f}")
                return draft_cost

            # Try alternate keys
            drafter_cost = result.metadata.get("drafter_cost", 0.0)
            if drafter_cost > 0:
                if self.verbose:
                    logger.debug(f"Extracted drafter_cost from metadata: ${drafter_cost:.6f}")
                return drafter_cost

        # Try total_cost if draft was accepted (it's the only cost)
        if hasattr(result, "draft_accepted") and result.draft_accepted:
            if hasattr(result, "total_cost") and result.total_cost > 0:
                if self.verbose:
                    logger.debug(
                        f"Using total_cost as draft_cost (draft accepted): "
                        f"${result.total_cost:.6f}"
                    )
                return result.total_cost

        # Fallback: calculate from tokens
        draft_tokens = self._extract_or_estimate_tokens(result, "draft")
        cost = self._calculate_model_cost(self.drafter, draft_tokens)

        if self.verbose:
            logger.debug(f"Calculated draft_cost from tokens ({draft_tokens}): ${cost:.6f}")

        return cost

    def _extract_or_calculate_verifier_cost(self, result) -> float:
        """
        Extract verifier cost from metadata or calculate from tokens.

        Args:
            result: SpeculativeResult

        Returns:
            Verifier cost in dollars
        """
        # Try metadata first
        if hasattr(result, "metadata") and result.metadata:
            verifier_cost = result.metadata.get("verifier_cost", 0.0)
            if verifier_cost > 0:
                if self.verbose:
                    logger.debug(f"Extracted verifier_cost from metadata: ${verifier_cost:.6f}")
                return verifier_cost

        # Fallback: calculate from tokens
        verifier_tokens = self._extract_or_estimate_tokens(result, "verifier")
        cost = self._calculate_model_cost(self.verifier, verifier_tokens)

        if self.verbose:
            logger.debug(f"Calculated verifier_cost from tokens ({verifier_tokens}): ${cost:.6f}")

        return cost

    def _extract_or_estimate_tokens(self, result, model_type: str) -> int:  # 'draft' or 'verifier'
        """
        Extract OUTPUT token count from metadata or estimate from content.

        NOTE: This extracts OUTPUT tokens only. Input tokens are added separately.

        Priority:
        1. Metadata with exact token count
        2. Metadata with response text
        3. Result content (final response)
        4. Estimation from token average

        Args:
            result: SpeculativeResult
            model_type: 'draft' or 'verifier'

        Returns:
            OUTPUT token count (actual or estimated)
        """
        # Try metadata first
        if hasattr(result, "metadata") and result.metadata:
            if model_type == "draft":
                # Try direct token count
                tokens = result.metadata.get("draft_tokens", 0)
                if tokens > 0:
                    return tokens

                # Try alternate keys
                tokens = result.metadata.get("tokens_drafted", 0)
                if tokens > 0:
                    return tokens

                # Try estimating from draft response text
                draft_response = result.metadata.get("draft_response", "")
                if draft_response:
                    return self.estimate_tokens(draft_response)

            else:  # verifier
                # Try direct token count
                tokens = result.metadata.get("verifier_tokens", 0)
                if tokens > 0:
                    return tokens

                # Try alternate keys
                tokens = result.metadata.get("tokens_verified", 0)
                if tokens > 0:
                    return tokens

                # Try estimating from verifier response text
                verifier_response = result.metadata.get("verifier_response", "")
                if verifier_response:
                    return self.estimate_tokens(verifier_response)

        # Fallback: estimate from final content
        if hasattr(result, "content"):
            content = result.content or ""
            return self.estimate_tokens(content)

        # Last resort: use average
        if self.verbose:
            logger.warning(f"Could not extract tokens for {model_type}, using average (100)")
        return 100

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _calculate_model_cost(self, model, tokens: int) -> float:
        """
        Calculate cost for a model given token count.

        Args:
            model: ModelConfig with cost per 1K tokens
            tokens: Number of tokens (input + output)

        Returns:
            Cost in dollars
        """
        # model.cost is cost per 1K tokens
        return (tokens / 1000) * model.cost

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count from text.

        Uses rule of thumb: 1 token ≈ 0.75 words (or 1.3 tokens per word)

        Note: This is an approximation. For exact counts, use tiktoken
        (OpenAI) or the provider's tokenizer.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count

        Example:
            >>> CostCalculator.estimate_tokens("Hello world!")
            3  # ~2 words * 1.3 = ~3 tokens
        """
        if not text:
            return 0

        word_count = len(text.split())
        token_estimate = int(word_count * 1.3)

        return max(1, token_estimate)  # At least 1 token


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "CostCalculator",
    "CostBreakdown",
]
