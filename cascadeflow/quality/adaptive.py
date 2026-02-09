"""
Adaptive threshold learning for cascade quality decisions.

Tracks acceptance outcomes per domain and auto-adjusts confidence thresholds
to maintain a target acceptance rate while preserving quality. Uses FastEmbed
embeddings to cluster queries and learn per-cluster thresholds.

This is the self-learning layer for cascadeflow:
- Phase 1: Rolling-window acceptance-rate tracking per domain
- Phase 2: Embedding-based query clustering for finer-grained thresholds

Usage:
    >>> from cascadeflow.quality.adaptive import AdaptiveThresholdManager
    >>>
    >>> manager = AdaptiveThresholdManager(target_acceptance_rate=0.55)
    >>>
    >>> # Record outcomes as they happen
    >>> manager.record("code", confidence=0.72, accepted=True, verifier_agreed=True)
    >>> manager.record("code", confidence=0.45, accepted=False, verifier_agreed=None)
    >>>
    >>> # Get adjusted threshold for a domain
    >>> threshold = manager.get_threshold("code", base_threshold=0.50)
    >>> # Returns adjusted threshold (tighter or looser based on observed data)
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Attempt to load FastEmbed for Phase 2 clustering
try:
    from cascadeflow.ml.embedding import UnifiedEmbeddingService

    _HAS_EMBEDDINGS = True
except ImportError:
    _HAS_EMBEDDINGS = False


@dataclass
class OutcomeRecord:
    """Single acceptance outcome."""

    domain: str
    confidence: float
    accepted: bool
    verifier_agreed: Optional[bool]
    timestamp: float = field(default_factory=time.time)


class AdaptiveThresholdManager:
    """
    Self-learning threshold manager that auto-adjusts cascade confidence
    thresholds based on observed acceptance rates per domain.

    When acceptance rate for a domain drifts too high (>70%), thresholds
    are tightened to send more queries to the verifier (quality up, cost up).
    When acceptance rate drops too low (<40%), thresholds are relaxed to
    accept more drafts (quality down, cost down).

    The target sweet spot is 50-60% acceptance (research-backed from
    SmartSpec 2024 and CascadeFlow production data).

    Args:
        target_acceptance_rate: Desired acceptance rate (default: 0.55)
        window_size: Number of recent outcomes per domain (default: 200)
        adjustment_step: How much to adjust per cycle (default: 0.01)
        min_samples: Minimum samples before adjusting (default: 30)
        enable_embeddings: Use FastEmbed for query clustering (Phase 2)
    """

    def __init__(
        self,
        target_acceptance_rate: float = 0.55,
        window_size: int = 200,
        adjustment_step: float = 0.01,
        min_samples: int = 30,
        enable_embeddings: bool = False,
    ):
        self.target_rate = target_acceptance_rate
        self.window_size = window_size
        self.adjustment_step = adjustment_step
        self.min_samples = min_samples
        self.enable_embeddings = enable_embeddings and _HAS_EMBEDDINGS

        # Per-domain rolling windows
        self._windows: dict[str, deque[OutcomeRecord]] = {}

        # Per-domain threshold adjustments (additive, can be positive or negative)
        self._adjustments: dict[str, float] = {}

        # Statistics
        self._total_records = 0
        self._total_adjustments = 0

        # Phase 2: Embedding-based clustering
        self._embedder: Optional[Any] = None
        self._hard_query_embeddings: list[tuple[Any, str]] = []  # (vec, domain)
        self._max_hard_queries = 500

    def record(
        self,
        domain: str,
        confidence: float,
        accepted: bool,
        verifier_agreed: Optional[bool] = None,
        query: Optional[str] = None,
    ):
        """
        Record an acceptance outcome.

        Args:
            domain: Query domain (code, math, medical, etc.)
            confidence: Confidence score that was used for the decision
            accepted: Whether the draft was accepted
            verifier_agreed: If verifier was called, did it agree with draft?
            query: Optional query text for embedding-based learning
        """
        outcome = OutcomeRecord(
            domain=domain,
            confidence=confidence,
            accepted=accepted,
            verifier_agreed=verifier_agreed,
        )

        if domain not in self._windows:
            self._windows[domain] = deque(maxlen=self.window_size)
        self._windows[domain].append(outcome)
        self._total_records += 1

        # Phase 2: Store embeddings of queries where draft was rejected AND
        # verifier produced a better result (confirmed hard queries)
        if (
            self.enable_embeddings
            and not accepted
            and verifier_agreed is False
            and query
        ):
            self._store_hard_query(query, domain)

        # Auto-adjust every min_samples records per domain
        window = self._windows[domain]
        if len(window) >= self.min_samples and len(window) % self.min_samples == 0:
            self._adjust_threshold(domain)

    def get_threshold(self, domain: str, base_threshold: float) -> float:
        """
        Get the adjusted threshold for a domain.

        Args:
            domain: Query domain
            base_threshold: The static base threshold from QualityConfig

        Returns:
            Adjusted threshold (base + learned adjustment)
        """
        adjustment = self._adjustments.get(domain, 0.0)
        adjusted = base_threshold + adjustment
        # Clamp to reasonable range
        return max(0.20, min(0.90, adjusted))

    def is_likely_hard(self, query: str, threshold: float = 0.85) -> bool:
        """
        Phase 2: Check if a query is similar to previously hard queries.

        Uses embedding similarity to detect queries that historically needed
        the verifier. If similar, skip drafting entirely (save latency).

        Args:
            query: Query text
            threshold: Cosine similarity threshold (default: 0.85)

        Returns:
            True if query is similar to known hard queries
        """
        if not self.enable_embeddings or not self._hard_query_embeddings:
            return False

        embedder = self._get_embedder()
        if embedder is None:
            return False

        try:
            query_vec = embedder.embed(query)
            if query_vec is None:
                return False

            for stored_vec, _ in self._hard_query_embeddings:
                sim = embedder._cosine_similarity(query_vec, stored_vec)
                if sim >= threshold:
                    return True
        except Exception:
            pass

        return False

    def get_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        domain_stats = {}
        for domain, window in self._windows.items():
            accepted = sum(1 for o in window if o.accepted)
            total = len(window)
            rate = accepted / total if total > 0 else 0.0
            domain_stats[domain] = {
                "acceptance_rate": round(rate, 3),
                "samples": total,
                "adjustment": round(self._adjustments.get(domain, 0.0), 4),
            }

        return {
            "total_records": self._total_records,
            "total_adjustments": self._total_adjustments,
            "target_rate": self.target_rate,
            "domains": domain_stats,
            "hard_queries_stored": len(self._hard_query_embeddings),
            "embeddings_enabled": self.enable_embeddings,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _adjust_threshold(self, domain: str):
        """Auto-adjust threshold based on observed acceptance rate."""
        window = self._windows[domain]
        accepted = sum(1 for o in window if o.accepted)
        rate = accepted / len(window)

        current_adj = self._adjustments.get(domain, 0.0)

        if rate > self.target_rate + 0.10:
            # Too many accepted -- tighten (increase threshold)
            new_adj = current_adj + self.adjustment_step
            logger.info(
                f"[adaptive] {domain}: acceptance rate {rate:.0%} > target "
                f"{self.target_rate + 0.10:.0%}, tightening by +{self.adjustment_step}"
            )
        elif rate < self.target_rate - 0.10:
            # Too few accepted -- relax (decrease threshold)
            new_adj = current_adj - self.adjustment_step
            logger.info(
                f"[adaptive] {domain}: acceptance rate {rate:.0%} < target "
                f"{self.target_rate - 0.10:.0%}, relaxing by -{self.adjustment_step}"
            )
        else:
            return  # Within target band, no adjustment needed

        # Clamp adjustment to [-0.15, +0.15] to prevent runaway
        self._adjustments[domain] = max(-0.15, min(0.15, new_adj))
        self._total_adjustments += 1

    def _store_hard_query(self, query: str, domain: str):
        """Store embedding of a confirmed hard query for Phase 2."""
        embedder = self._get_embedder()
        if embedder is None:
            return
        try:
            vec = embedder.embed(query)
            if vec is not None:
                if len(self._hard_query_embeddings) >= self._max_hard_queries:
                    self._hard_query_embeddings.pop(0)  # FIFO eviction
                self._hard_query_embeddings.append((vec, domain))
        except Exception:
            pass

    def _get_embedder(self):
        """Lazy-initialize embedder."""
        if self._embedder is not None:
            return self._embedder
        if not _HAS_EMBEDDINGS:
            return None
        try:
            self._embedder = UnifiedEmbeddingService()
            if not self._embedder.is_available:
                self._embedder = None
        except Exception:
            self._embedder = None
        return self._embedder
