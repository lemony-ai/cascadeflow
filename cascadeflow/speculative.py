"""
Speculative Cascades Implementation - FULL TOKEN-LEVEL VERSION

Based on Google Research (Sept 2025):
"Faster Cascades via Speculative Decoding"
https://arxiv.org/abs/2405.19261

Key innovation: Token-by-token flexible deferral during generation.
Not after generation completes - DURING token generation.
"""

import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import math

from .config import ModelConfig

logger = logging.getLogger(__name__)


class DeferralStrategy(Enum):
    """
    Deferral strategies from Google's research.
    Each strategy answers: "Should we defer THIS TOKEN to the large model?"
    """
    CONFIDENCE_THRESHOLD = "confidence"
    COMPARATIVE = "comparative"
    COST_BENEFIT = "cost_benefit"
    TOKEN_LIST = "token_list"


@dataclass
class TokenPrediction:
    """Single token prediction with probability."""
    token: str
    logprob: float
    probability: float  # exp(logprob)
    token_id: Optional[int] = None


@dataclass
class DraftToken:
    """Token drafted by small model."""
    token: str
    logprob: float
    probability: float
    position: int
    alternatives: List[TokenPrediction] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of token verification."""
    accepted_tokens: List[str]
    deferred_at: Optional[int]  # Position where we deferred
    total_drafted: int
    total_accepted: int
    total_deferred: int
    acceptance_rate: float
    deferral_reason: Optional[str] = None


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
    tokens_accepted: int
    draft_confidence: float
    verifier_confidence: float
    total_cost: float
    latency_ms: float
    speedup: float
    deferral_strategy: str
    acceptance_rate: float
    chunks_processed: int
    metadata: dict


class FlexibleDeferralRule:
    """
    Flexible deferral rules from Google's paper.

    KEY: Per-token decisions, not all-or-nothing.
    """

    def __init__(
            self,
            strategy: DeferralStrategy = DeferralStrategy.TOKEN_LIST,
            confidence_threshold: float = 0.7,
            comparative_delta: float = 0.15,
            cost_benefit_threshold: float = 0.5,
            top_k: int = 10,
            min_probability: float = 0.01
    ):
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold
        self.comparative_delta = comparative_delta
        self.cost_benefit_threshold = cost_benefit_threshold
        self.top_k = top_k
        self.min_probability = min_probability

        self.decision_log = []

    def should_defer_token(
            self,
            draft_token: str,
            draft_logprob: float,
            verifier_top_k: List[TokenPrediction],
            position: int
    ) -> Tuple[bool, str]:
        """
        Decide whether to defer THIS SPECIFIC TOKEN.

        Returns:
            (should_defer, reason)
        """
        draft_prob = math.exp(draft_logprob)

        if self.strategy == DeferralStrategy.CONFIDENCE_THRESHOLD:
            # Simple: Is draft confident enough?
            should_defer = draft_prob < self.confidence_threshold
            reason = f"draft_prob={draft_prob:.3f} < threshold={self.confidence_threshold}"

        elif self.strategy == DeferralStrategy.COMPARATIVE:
            # Is verifier significantly more confident?
            verifier_best_prob = verifier_top_k[0].probability
            confidence_gap = verifier_best_prob - draft_prob
            should_defer = confidence_gap > self.comparative_delta
            reason = f"gap={confidence_gap:.3f} > delta={self.comparative_delta}"

        elif self.strategy == DeferralStrategy.COST_BENEFIT:
            # Is quality gain worth rejecting draft?
            verifier_best_prob = verifier_top_k[0].probability

            # Find draft token in verifier predictions
            draft_verifier_prob = None
            for pred in verifier_top_k:
                if pred.token == draft_token:
                    draft_verifier_prob = pred.probability
                    break

            if draft_verifier_prob is None:
                # Draft not in top-k, use minimum
                draft_verifier_prob = self.min_probability

            quality_gain = verifier_best_prob - draft_verifier_prob
            rejection_cost = draft_prob  # Higher draft confidence = higher cost

            if rejection_cost > 0:
                benefit_ratio = quality_gain / rejection_cost
            else:
                benefit_ratio = float('inf')

            # Defer if benefit ratio HIGH (worth the cost)
            should_defer = benefit_ratio >= self.cost_benefit_threshold
            reason = f"benefit_ratio={benefit_ratio:.3f} >= threshold={self.cost_benefit_threshold}"

        elif self.strategy == DeferralStrategy.TOKEN_LIST:
            # Most flexible: Defer if draft NOT in verifier's top-K
            approved_tokens = set()
            for pred in verifier_top_k[:self.top_k]:
                if pred.probability >= self.min_probability:
                    approved_tokens.add(pred.token)

            should_defer = draft_token not in approved_tokens
            reason = f"draft '{draft_token}' {'not ' if should_defer else ''}in top-{self.top_k}"

        else:
            # Default
            should_defer = draft_prob < self.confidence_threshold
            reason = "default_confidence"

        # Log decision
        self.decision_log.append({
            'position': position,
            'strategy': self.strategy.value,
            'draft_token': draft_token,
            'draft_prob': draft_prob,
            'deferred': should_defer,
            'reason': reason
        })

        return should_defer, reason


class ProviderCapabilities:
    """Detect provider capabilities for logprobs support."""

    LOGPROBS_SUPPORT = {
        'openai': True,
        'anthropic': True,
        'groq': True,
        'together': True,
        'vllm': True,
        'openrouter': True,
        'ollama': False,
        'replicate': False,
    }

    @classmethod
    def supports_logprobs(cls, provider: str) -> bool:
        return cls.LOGPROBS_SUPPORT.get(provider.lower(), False)

    @classmethod
    def get_fallback_strategy(cls, drafter_provider: str, verifier_provider: str) -> DeferralStrategy:
        """Get best strategy based on provider capabilities."""
        drafter_support = cls.supports_logprobs(drafter_provider)
        verifier_support = cls.supports_logprobs(verifier_provider)

        if drafter_support and verifier_support:
            return DeferralStrategy.TOKEN_LIST  # Most powerful
        elif verifier_support:
            return DeferralStrategy.COMPARATIVE
        else:
            return DeferralStrategy.CONFIDENCE_THRESHOLD


class TokenLevelSpeculativeCascade:
    """
    TRUE Speculative Cascade with token-by-token decisions.

    This is the CORE innovation from Google's paper:
    - Draft tokens one-by-one
    - Verify each token against verifier's predictions
    - Flexible deferral per token
    - Continue from defer point
    """

    def __init__(
            self,
            drafter: ModelConfig,
            verifier: ModelConfig,
            providers: dict,
            deferral_rule: Optional[FlexibleDeferralRule] = None,
            chunk_size: int = 10,
            verbose: bool = False
    ):
        self.drafter = drafter
        self.verifier = verifier
        self.providers = providers
        self.chunk_size = chunk_size
        self.verbose = verbose

        # Auto-select best strategy based on provider capabilities
        if deferral_rule is None:
            strategy = ProviderCapabilities.get_fallback_strategy(
                drafter.provider,
                verifier.provider
            )
            self.deferral_rule = FlexibleDeferralRule(strategy=strategy)
        else:
            self.deferral_rule = deferral_rule

        self.stats = {
            "total_executions": 0,
            "tokens_drafted": 0,
            "tokens_accepted": 0,
            "tokens_deferred": 0,
            "chunks_processed": 0,
            "total_speedup": 0.0,
            "total_cost_saved": 0.0
        }

    async def execute(
            self,
            query: str,
            max_tokens: int = 100,
            temperature: float = 0.7,
            **kwargs
    ) -> SpeculativeResult:
        """
        Execute chunked speculative cascade.

        From paper: "The process efficiently repeats, drafting and
        verifying the next chunk until the answer is complete."
        """
        self.stats["total_executions"] += 1
        start_time = time.time()

        output_tokens = []
        context = query
        chunks_processed = 0
        total_cost = 0.0

        if self.verbose:
            logger.info(f"Starting token-level cascade: {self.drafter.name} → {self.verifier.name}")

        while len(output_tokens) < max_tokens:
            chunks_processed += 1

            # PHASE 1: Draft next chunk
            draft_chunk = await self._draft_chunk(
                context,
                num_tokens=min(self.chunk_size, max_tokens - len(output_tokens)),
                temperature=temperature
            )

            if not draft_chunk:
                break

            # PHASE 2: Verify chunk token-by-token
            verification = await self._verify_chunk_tokenwise(
                draft_chunk,
                context
            )

            # PHASE 3: Append accepted tokens
            output_tokens.extend(verification.accepted_tokens)
            context += ''.join(verification.accepted_tokens)

            # Track stats
            self.stats["tokens_drafted"] += verification.total_drafted
            self.stats["tokens_accepted"] += verification.total_accepted
            self.stats["tokens_deferred"] += verification.total_deferred

            # Cost: drafter for draft + verifier for verification
            total_cost += self.drafter.cost * (verification.total_drafted / 1000)
            total_cost += self.verifier.cost * (verification.total_accepted / 1000)

            if self.verbose:
                logger.info(
                    f"Chunk {chunks_processed}: "
                    f"drafted={verification.total_drafted}, "
                    f"accepted={verification.total_accepted}, "
                    f"rate={verification.acceptance_rate:.1%}"
                )

            # PHASE 4: Check if we deferred
            if verification.deferred_at is not None:
                # Continue rest with verifier
                remaining_tokens = max_tokens - len(output_tokens)
                if remaining_tokens > 0:
                    completion = await self._complete_with_verifier(
                        context,
                        remaining_tokens,
                        temperature
                    )
                    output_tokens.extend(completion)
                    total_cost += self.verifier.cost * (len(completion) / 1000)
                    self.stats["tokens_deferred"] += len(completion)
                break

            # Check stopping conditions
            if self._is_complete(output_tokens):
                break

        self.stats["chunks_processed"] += chunks_processed

        latency = (time.time() - start_time) * 1000

        # Calculate speedup
        # Sequential would be: all tokens from verifier
        sequential_cost = self.verifier.cost * (len(output_tokens) / 1000)
        cost_saved = sequential_cost - total_cost

        sequential_latency = self.verifier.speed_ms * (len(output_tokens) / 100)
        speedup = sequential_latency / latency if latency > 0 else 1.0

        self.stats["total_speedup"] += speedup
        self.stats["total_cost_saved"] += cost_saved

        acceptance_rate = (
            self.stats["tokens_accepted"] / self.stats["tokens_drafted"]
            if self.stats["tokens_drafted"] > 0 else 0
        )

        if self.verbose:
            logger.info(
                f"Complete: {len(output_tokens)} tokens, "
                f"acceptance={acceptance_rate:.1%}, "
                f"speedup={speedup:.2f}x, "
                f"saved=${cost_saved:.4f}"
            )

        return SpeculativeResult(
            content=''.join(output_tokens),
            model_used=f"{self.drafter.name}+{self.verifier.name}",
            drafter_model=self.drafter.name,
            verifier_model=self.verifier.name,
            draft_accepted=(self.stats["tokens_accepted"] > 0),
            tokens_drafted=self.stats["tokens_drafted"],
            tokens_verified=len(output_tokens),
            tokens_deferred=self.stats["tokens_deferred"],
            tokens_accepted=self.stats["tokens_accepted"],
            draft_confidence=0.0,  # Not applicable for token-level
            verifier_confidence=0.0,
            total_cost=total_cost,
            latency_ms=latency,
            speedup=speedup,
            deferral_strategy=self.deferral_rule.strategy.value,
            acceptance_rate=acceptance_rate,
            chunks_processed=chunks_processed,
            metadata={
                "cost_saved": cost_saved,
                "sequential_cost": sequential_cost,
                "deferral_decisions": len(self.deferral_rule.decision_log)
            }
        )

    async def _draft_chunk(
            self,
            context: str,
            num_tokens: int,
            temperature: float
    ) -> List[DraftToken]:
        """
        Draft next chunk of tokens with logprobs.
        """
        provider = self.providers[self.drafter.provider]

        try:
            # Check if provider supports logprobs
            supports_logprobs = ProviderCapabilities.supports_logprobs(
                self.drafter.provider
            )

            result = await provider.complete(
                model=self.drafter.name,
                prompt=context,
                max_tokens=num_tokens,
                temperature=temperature,
                logprobs=supports_logprobs,
                top_logprobs=5 if supports_logprobs else None
            )

            # Parse response
            draft_tokens = []
            tokens = result.get('tokens', [])
            logprobs = result.get('logprobs', [])

            # If no logprobs, estimate from confidence
            if not logprobs:
                confidence = result.get('confidence', 0.8)
                logprobs = [math.log(confidence)] * len(tokens)

            for i, token in enumerate(tokens):
                logprob = logprobs[i] if i < len(logprobs) else math.log(0.5)
                draft_tokens.append(DraftToken(
                    token=token,
                    logprob=logprob,
                    probability=math.exp(logprob),
                    position=i
                ))

            return draft_tokens

        except Exception as e:
            logger.error(f"Draft error: {e}")
            return []

    async def _verify_chunk_tokenwise(
            self,
            draft_chunk: List[DraftToken],
            context: str
    ) -> VerificationResult:
        """
        Verify draft chunk token-by-token.

        This is the CORE of speculative cascading:
        Check each token individually, not the whole chunk.
        """
        accepted_tokens = []
        deferred_at = None
        current_context = context

        for draft in draft_chunk:
            # Get verifier's predictions for this position
            verifier_top_k = await self._get_verifier_predictions(
                current_context,
                top_k=20
            )

            # Apply flexible deferral rule
            should_defer, reason = self.deferral_rule.should_defer_token(
                draft_token=draft.token,
                draft_logprob=draft.logprob,
                verifier_top_k=verifier_top_k,
                position=draft.position
            )

            if should_defer:
                # Defer: use verifier's best token
                best_token = verifier_top_k[0].token
                accepted_tokens.append(best_token)
                deferred_at = draft.position

                if self.verbose:
                    logger.debug(
                        f"Deferred at position {draft.position}: "
                        f"'{draft.token}' → '{best_token}' ({reason})"
                    )
                break
            else:
                # Accept: use draft token
                accepted_tokens.append(draft.token)
                current_context += draft.token

        total_accepted = len([t for t in accepted_tokens if t])
        total_deferred = 1 if deferred_at is not None else 0

        return VerificationResult(
            accepted_tokens=accepted_tokens,
            deferred_at=deferred_at,
            total_drafted=len(draft_chunk),
            total_accepted=total_accepted - total_deferred,
            total_deferred=total_deferred,
            acceptance_rate=(total_accepted - total_deferred) / len(draft_chunk)
        )

    async def _get_verifier_predictions(
            self,
            context: str,
            top_k: int = 20
    ) -> List[TokenPrediction]:
        """
        Get verifier's top-k predictions for next token.
        """
        provider = self.providers[self.verifier.provider]

        try:
            supports_logprobs = ProviderCapabilities.supports_logprobs(
                self.verifier.provider
            )

            result = await provider.complete(
                model=self.verifier.name,
                prompt=context,
                max_tokens=1,  # Just next token
                temperature=0.0,  # Deterministic for verification
                logprobs=supports_logprobs,
                top_logprobs=top_k if supports_logprobs else None
            )

            predictions = []

            # Parse top logprobs
            top_logprobs = result.get('top_logprobs', [])
            if top_logprobs and len(top_logprobs) > 0:
                for token, logprob in top_logprobs[0].items():
                    predictions.append(TokenPrediction(
                        token=token,
                        logprob=logprob,
                        probability=math.exp(logprob)
                    ))
            else:
                # Fallback: just the generated token
                token = result.get('tokens', [''])[0]
                predictions.append(TokenPrediction(
                    token=token,
                    logprob=math.log(0.9),
                    probability=0.9
                ))

            # Sort by probability
            predictions.sort(key=lambda p: p.probability, reverse=True)
            return predictions

        except Exception as e:
            logger.error(f"Verifier prediction error: {e}")
            return [TokenPrediction(token='', logprob=math.log(0.5), probability=0.5)]

    async def _complete_with_verifier(
            self,
            context: str,
            num_tokens: int,
            temperature: float
    ) -> List[str]:
        """
        Complete remaining tokens with verifier only.
        Called after deferring.
        """
        provider = self.providers[self.verifier.provider]

        try:
            result = await provider.complete(
                model=self.verifier.name,
                prompt=context,
                max_tokens=num_tokens,
                temperature=temperature
            )

            return result.get('tokens', [])

        except Exception as e:
            logger.error(f"Verifier completion error: {e}")
            return []

    def _is_complete(self, tokens: List[str]) -> bool:
        """Check if generation is complete."""
        if not tokens:
            return False

        # Check for end tokens
        text = ''.join(tokens)
        end_markers = ['\n\n', '. ', '? ', '! ', '</s>', '<|endoftext|>']

        return any(text.endswith(marker) for marker in end_markers)

    def get_stats(self) -> Dict[str, Any]:
        """Get cascade statistics."""
        if self.stats["total_executions"] == 0:
            return self.stats

        return {
            **self.stats,
            "avg_acceptance_rate": (
                self.stats["tokens_accepted"] / self.stats["tokens_drafted"]
                if self.stats["tokens_drafted"] > 0 else 0
            ),
            "avg_speedup": self.stats["total_speedup"] / self.stats["total_executions"],
            "avg_chunks": self.stats["chunks_processed"] / self.stats["total_executions"],
            "total_cost_saved": self.stats["total_cost_saved"]
        }


class SpeculativeCascade:
    """
    LEGACY: Full-output speculative cascade (for backwards compatibility).

    Use TokenLevelSpeculativeCascade for true speculative cascading.
    """

    def __init__(
            self,
            drafter: ModelConfig,
            verifier: ModelConfig,
            providers: dict,
            deferral_rule: Optional[FlexibleDeferralRule] = None,
            verbose: bool = False
    ):
        # Delegate to token-level version
        self.token_cascade = TokenLevelSpeculativeCascade(
            drafter=drafter,
            verifier=verifier,
            providers=providers,
            deferral_rule=deferral_rule,
            verbose=verbose
        )

    async def execute(self, query: str, max_tokens: int = 4096, **kwargs) -> SpeculativeResult:
        """Execute via token-level cascade."""
        return await self.token_cascade.execute(query, max_tokens, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self.token_cascade.get_stats()