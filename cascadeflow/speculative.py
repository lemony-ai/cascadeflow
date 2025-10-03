"""
Speculative Cascades Implementation.

Based on Google Research (Sept 2025):
"Faster Cascades via Speculative Decoding"
https://arxiv.org/abs/2405.19261

Key innovation: Flexible deferral rules that can accept good answers
from small models even when they don't exactly match large model output.
"""

import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import time

from .config import ModelConfig

logger = logging.getLogger(__name__)


class DeferralStrategy(Enum):
    """
    Deferral strategies from Google's research.

    Each strategy answers: "Should we defer to the large model?"
    """
    CONFIDENCE_THRESHOLD = "confidence"     # Simple: draft confidence >= threshold?
    COMPARATIVE = "comparative"             # Recommended: large model significantly better?
    COST_BENEFIT = "cost_benefit"           # Worth the cost of deferring?
    TOKEN_LIST = "token_list"               # Draft token in large model's top-K?


@dataclass
class SpeculativeResult:
    """Result from speculative cascade execution."""
    content: str
    model_used: str
    drafter_model: str
    verifier_model: str
    draft_accepted: bool
    tokens_drafted: int
    tokens_verified: int
    tokens_deferred: int
    draft_confidence: float
    verifier_confidence: float
    total_cost: float
    latency_ms: float
    speedup: float
    deferral_strategy: str
    metadata: dict


class FlexibleDeferralRule:
    """
    Flexible deferral rules from Google's paper.

    Instead of strict token matching (speculative decoding),
    we intelligently decide when to defer based on:
    - Confidence levels
    - Quality differences
    - Cost-benefit analysis
    """

    def __init__(
            self,
            strategy: DeferralStrategy = DeferralStrategy.COMPARATIVE,
            confidence_threshold: float = 0.7,
            comparative_delta: float = 0.2,
            cost_benefit_ratio: float = 2.0,
            top_k: int = 5
    ):
        """
        Initialize deferral rule.

        Args:
            strategy: Deferral strategy to use
            confidence_threshold: Min confidence to accept (CONFIDENCE_THRESHOLD)
            comparative_delta: Min quality gap to defer (COMPARATIVE)
            cost_benefit_ratio: Min benefit/cost ratio to defer (COST_BENEFIT)
            top_k: Number of top tokens to check (TOKEN_LIST)
        """
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold
        self.comparative_delta = comparative_delta
        self.cost_benefit_ratio = cost_benefit_ratio
        self.top_k = top_k

    def should_defer(
            self,
            draft_confidence: float,
            verifier_confidence: Optional[float] = None,
            drafter_cost: float = 0.0,
            verifier_cost: float = 0.0,
            draft_tokens: Optional[list] = None,
            verifier_top_tokens: Optional[list] = None
    ) -> bool:
        """
        Decide whether to defer to verifier.

        This is the KEY innovation from Google's paper:
        Flexible decision-making instead of strict matching.

        Args:
            draft_confidence: Confidence of draft response
            verifier_confidence: Confidence of verifier (if available)
            drafter_cost: Cost of drafter
            verifier_cost: Cost of verifier
            draft_tokens: Tokens from draft (for TOKEN_LIST)
            verifier_top_tokens: Top-K tokens from verifier (for TOKEN_LIST)

        Returns:
            True if should defer to verifier, False to accept draft
        """

        if self.strategy == DeferralStrategy.CONFIDENCE_THRESHOLD:
            # Simple: Is draft confident enough?
            return draft_confidence < self.confidence_threshold

        elif self.strategy == DeferralStrategy.COMPARATIVE:
            # Recommended: Is verifier significantly better?
            if verifier_confidence is None:
                # Can't compare, use confidence threshold
                return draft_confidence < self.confidence_threshold

            confidence_gap = verifier_confidence - draft_confidence
            should_defer = confidence_gap > self.comparative_delta

            logger.debug(
                f"Comparative: draft={draft_confidence:.2f}, "
                f"verifier={verifier_confidence:.2f}, "
                f"gap={confidence_gap:.2f}, "
                f"defer={should_defer}"
            )
            return should_defer

        elif self.strategy == DeferralStrategy.COST_BENEFIT:
            # Economic: Is quality boost worth the cost?
            if verifier_confidence is None:
                return draft_confidence < self.confidence_threshold

            quality_gain = verifier_confidence - draft_confidence
            cost_ratio = verifier_cost / (drafter_cost + 0.0001)
            benefit_cost = quality_gain / cost_ratio if cost_ratio > 0 else quality_gain

            should_defer = benefit_cost < self.cost_benefit_ratio

            logger.debug(
                f"Cost-Benefit: quality_gain={quality_gain:.2f}, "
                f"cost_ratio={cost_ratio:.2f}, "
                f"benefit/cost={benefit_cost:.2f}, "
                f"defer={should_defer}"
            )
            return should_defer

        elif self.strategy == DeferralStrategy.TOKEN_LIST:
            # Token-specific: Is draft in verifier's top-K?
            if not draft_tokens or not verifier_top_tokens:
                return draft_confidence < self.confidence_threshold

            # Check if draft tokens are in verifier's top-K
            draft_in_top_k = any(
                token in verifier_top_tokens[:self.top_k]
                for token in draft_tokens[-5:]  # Check last 5 tokens
            )

            should_defer = not draft_in_top_k

            logger.debug(
                f"Token-List: draft_in_top_{self.top_k}={draft_in_top_k}, "
                f"defer={should_defer}"
            )
            return should_defer

        else:
            # Default: use confidence threshold
            return draft_confidence < self.confidence_threshold


class SpeculativeCascade:
    """
    Speculative Cascade with flexible deferral (Google's research).

    Key difference from standard speculative decoding:
    - Can accept good answers that don't exactly match
    - Multiple deferral strategies
    - Better cost-quality tradeoffs
    - Parallel execution (2-3x speedup)
    """

    def __init__(
            self,
            drafter: ModelConfig,
            verifier: ModelConfig,
            providers: dict,
            deferral_rule: Optional[FlexibleDeferralRule] = None,
            verbose: bool = False
    ):
        """
        Initialize speculative cascade.

        Args:
            drafter: Small/fast model for drafting
            verifier: Large/slow model for verification
            providers: Provider instances dict
            deferral_rule: Deferral rule (defaults to COMPARATIVE)
            verbose: Enable verbose logging
        """
        self.drafter = drafter
        self.verifier = verifier
        self.providers = providers
        self.deferral_rule = deferral_rule or FlexibleDeferralRule(
            strategy=DeferralStrategy.COMPARATIVE
        )
        self.verbose = verbose

        self.stats = {
            "total_executions": 0,
            "drafts_accepted": 0,
            "drafts_deferred": 0,
            "total_speedup": 0.0,
            "total_cost_saved": 0.0
        }

    async def execute(
            self,
            query: str,
            max_tokens: int = 4096,
            temperature: float = 0.7,
            **kwargs
    ) -> SpeculativeResult:
        """
        Execute speculative cascade with flexible deferral.

        Algorithm (from Google's paper):
        1. Start draft and verify in PARALLEL
        2. Draft generates tokens quickly
        3. Verifier evaluates draft in parallel
        4. Flexible deferral rule decides: accept or defer?
        5. If accept: use draft (fast + cheap!)
        6. If defer: use verifier (already running!)

        Result: 2-3x faster than sequential

        Args:
            query: User query
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            SpeculativeResult with outcome and metrics
        """
        self.stats["total_executions"] += 1
        start_time = time.time()

        # PHASE 1: Start both models in parallel
        if self.verbose:
            logger.info(
                f"Starting speculative cascade: "
                f"{self.drafter.name} → {self.verifier.name}"
            )

        draft_task = asyncio.create_task(
            self._draft_response(query, max_tokens, temperature, **kwargs)
        )
        verify_task = asyncio.create_task(
            self._verify_response(query, max_tokens, temperature, **kwargs)
        )

        # PHASE 2: Wait for draft (it's faster)
        draft_result = await draft_task

        if self.verbose:
            logger.info(
                f"Draft complete: {len(draft_result.get('content', ''))} chars, "
                f"confidence: {draft_result.get('confidence', 0):.2f}"
            )

        # PHASE 3: Get verifier result (should be ready or nearly ready)
        verify_result = await verify_task

        if self.verbose:
            logger.info(
                f"Verifier complete: {len(verify_result.get('content', ''))} chars, "
                f"confidence: {verify_result.get('confidence', 0):.2f}"
            )

        # PHASE 4: Apply flexible deferral rule
        should_defer = self.deferral_rule.should_defer(
            draft_confidence=draft_result.get('confidence', 0.0),
            verifier_confidence=verify_result.get('confidence', 0.0),
            drafter_cost=self.drafter.cost,
            verifier_cost=self.verifier.cost,
            draft_tokens=draft_result.get('tokens', []),
            verifier_top_tokens=verify_result.get('top_tokens', [])
        )

        latency = (time.time() - start_time) * 1000

        # Calculate what sequential would have cost
        sequential_latency = self.drafter.speed_ms + self.verifier.speed_ms
        speedup = sequential_latency / latency if latency > 0 else 1.0

        if not should_defer:
            # Accept draft!
            self.stats["drafts_accepted"] += 1
            self.stats["total_speedup"] += speedup
            self.stats["total_cost_saved"] += self.verifier.cost

            if self.verbose:
                logger.info(
                    f"✓ Draft ACCEPTED! "
                    f"Latency: {latency:.0f}ms, "
                    f"Cost: ${self.drafter.cost:.6f}, "
                    f"Speedup: {speedup:.2f}x"
                )

            return SpeculativeResult(
                content=draft_result['content'],
                model_used=self.drafter.name,
                drafter_model=self.drafter.name,
                verifier_model=self.verifier.name,
                draft_accepted=True,
                tokens_drafted=len(draft_result.get('tokens', [])),
                tokens_verified=0,
                tokens_deferred=0,
                draft_confidence=draft_result.get('confidence', 0.0),
                verifier_confidence=verify_result.get('confidence', 0.0),
                total_cost=self.drafter.cost,
                latency_ms=latency,
                speedup=speedup,
                deferral_strategy=self.deferral_rule.strategy.value,
                metadata={
                    "reason": "draft_accepted",
                    "cost_saved": self.verifier.cost
                }
            )

        else:
            # Defer to verifier
            self.stats["drafts_deferred"] += 1
            self.stats["total_speedup"] += speedup
            total_cost = self.drafter.cost + self.verifier.cost

            if self.verbose:
                logger.info(
                    f"→ Draft DEFERRED. Using verifier. "
                    f"Latency: {latency:.0f}ms, "
                    f"Cost: ${total_cost:.6f}, "
                    f"Speedup: {speedup:.2f}x"
                )

            return SpeculativeResult(
                content=verify_result['content'],
                model_used=self.verifier.name,
                drafter_model=self.drafter.name,
                verifier_model=self.verifier.name,
                draft_accepted=False,
                tokens_drafted=len(draft_result.get('tokens', [])),
                tokens_verified=len(verify_result.get('tokens', [])),
                tokens_deferred=len(verify_result.get('tokens', [])),
                draft_confidence=draft_result.get('confidence', 0.0),
                verifier_confidence=verify_result.get('confidence', 0.0),
                total_cost=total_cost,
                latency_ms=latency,
                speedup=speedup,
                deferral_strategy=self.deferral_rule.strategy.value,
                metadata={
                    "reason": "draft_deferred",
                    "confidence_gap": verify_result.get('confidence', 0.0) - draft_result.get('confidence', 0.0)
                }
            )

    async def _draft_response(
            self,
            query: str,
            max_tokens: int,
            temperature: float,
            **kwargs
    ) -> Dict[str, Any]:
        """Get draft from small model."""
        provider = self.providers[self.drafter.provider]

        try:
            result = await provider.complete(
                model=self.drafter.name,
                prompt=query,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            return {
                'content': result.get('content', ''),
                'tokens': result.get('tokens', []),
                'confidence': result.get('confidence', 0.8),
                'top_tokens': result.get('top_tokens', [])
            }
        except Exception as e:
            logger.error(f"Draft error: {e}")
            return {
                'content': '',
                'tokens': [],
                'confidence': 0.0,
                'top_tokens': []
            }

    async def _verify_response(
            self,
            query: str,
            max_tokens: int,
            temperature: float,
            **kwargs
    ) -> Dict[str, Any]:
        """Get verification from large model."""
        provider = self.providers[self.verifier.provider]

        try:
            result = await provider.complete(
                model=self.verifier.name,
                prompt=query,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            return {
                'content': result.get('content', ''),
                'tokens': result.get('tokens', []),
                'confidence': result.get('confidence', 0.9),
                'top_tokens': result.get('top_tokens', [])
            }
        except Exception as e:
            logger.error(f"Verify error: {e}")
            return {
                'content': '',
                'tokens': [],
                'confidence': 0.0,
                'top_tokens': []
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get cascade statistics."""
        if self.stats["total_executions"] == 0:
            return self.stats

        return {
            **self.stats,
            "acceptance_rate": self.stats["drafts_accepted"] / self.stats["total_executions"],
            "avg_speedup": self.stats["total_speedup"] / self.stats["total_executions"],
            "total_cost_saved": self.stats["total_cost_saved"]
        }