"""
Optional Semantic ML Quality Validation

This module provides ML-based quality validation using embeddings for semantic
similarity checking. It's completely optional and gracefully degrades if
dependencies (fastembed) are not installed.

Key Features:
- Semantic similarity between query and response
- Optional toxicity detection
- Zero-config (auto-downloads models on first use)
- Lightweight (FastEmbed uses ONNX models)
- Graceful degradation

Example:
    >>> from cascadeflow.quality.semantic import SemanticQualityChecker
    >>>
    >>> # Initialize (downloads model on first use)
    >>> checker = SemanticQualityChecker()
    >>>
    >>> if checker.is_available():
    ...     # Check semantic similarity
    ...     similarity = checker.check_similarity(
    ...         query="What is machine learning?",
    ...         response="Machine learning is a subset of AI..."
    ...     )
    ...     print(f"Similarity: {similarity:.2%}")
    ...
    ...     # Check for toxic content
    ...     is_toxic, score = checker.check_toxicity(
    ...         "Your response text here"
    ...     )
    ...     if is_toxic:
    ...         print(f"Toxic content detected (score: {score:.2f})")
"""

import logging
from dataclasses import dataclass
from typing import Optional

try:
    from ..ml.embedding import EmbeddingCache, UnifiedEmbeddingService

    HAS_ML_MODULE = True
except ImportError:
    HAS_ML_MODULE = False
    UnifiedEmbeddingService = None
    EmbeddingCache = None

logger = logging.getLogger(__name__)


@dataclass
class SemanticQualityResult:
    """Result of semantic quality check.

    Attributes:
        similarity: Semantic similarity score (0-1)
        is_toxic: Whether content is toxic
        toxicity_score: Toxicity score (0-1, higher = more toxic)
        passed: Whether quality check passed
        reason: Optional failure reason
        metadata: Additional check metadata
    """

    similarity: float
    is_toxic: bool
    toxicity_score: float
    passed: bool
    reason: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SemanticQualityChecker:
    """
    Optional ML-based quality validation using embeddings.

    Uses FastEmbed for fast, lightweight semantic similarity checking.
    Completely optional - gracefully degrades if dependencies not installed.

    Installation:
        pip install fastembed

    The FastEmbed library will auto-download the embedding model (~40MB)
    on first use. Subsequent uses are fast.

    Attributes:
        model: FastEmbed embedding model (None if not available)
        available: Whether semantic checking is available
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        similarity_threshold: float = 0.5,
        toxicity_threshold: float = 0.7,
        embedder: Optional["UnifiedEmbeddingService"] = None,
        use_cache: bool = True,
    ):
        """
        Initialize semantic quality checker.

        Args:
            model_name: Embedding model to use (default: BGE-small, ~40MB)
            similarity_threshold: Minimum similarity score to pass (default: 0.5)
            toxicity_threshold: Maximum toxicity score to pass (default: 0.7)
            embedder: Optional UnifiedEmbeddingService (creates new if None)
            use_cache: Whether to use embedding caching (default: True)
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.toxicity_threshold = toxicity_threshold
        self.use_cache = use_cache

        # Use provided embedder or create new one
        if embedder is not None:
            self.embedder = embedder
        elif HAS_ML_MODULE:
            self.embedder = UnifiedEmbeddingService(model_name=model_name)
        else:
            self.embedder = None

        # Create cache if requested
        if self.use_cache and self.embedder and self.embedder.is_available:
            self.cache = EmbeddingCache(self.embedder)
        else:
            self.cache = None

        # Legacy compatibility
        self.model = self.embedder
        self.available = self.embedder.is_available if self.embedder else False

        if self.available:
            logger.info("✓ Semantic quality checking enabled (UnifiedEmbeddingService)")
        else:
            logger.warning("⚠️ ML module not available. Semantic quality checking unavailable.")
            logger.warning("Install with: pip install fastembed")

    def is_available(self) -> bool:
        """Check if semantic quality checking is available."""
        return self.available

    def check_similarity(
        self,
        query: str,
        response: str,
        threshold: Optional[float] = None,
    ) -> float:
        """
        Check semantic similarity between query and response.

        Uses cosine similarity of embeddings to measure how well the
        response aligns with the query semantically.

        Args:
            query: Original query text
            response: Generated response text
            threshold: Optional custom threshold (uses default if None)

        Returns:
            Similarity score (0-1, higher = more similar)

        Raises:
            RuntimeError: If semantic checking not available
        """
        if not self.is_available():
            raise RuntimeError(
                "Semantic checking not available. Install fastembed: " "pip install fastembed"
            )

        # Use cache if available for better performance
        if self.cache:
            similarity = self.cache.similarity(query, response)
        else:
            # Fallback to direct embedder
            similarity = self.embedder.similarity(query, response)

        return float(similarity) if similarity is not None else 0.0

    def check_toxicity(
        self,
        text: str,
        threshold: Optional[float] = None,
    ) -> tuple[bool, float]:
        """
        Check if text contains toxic content.

        Uses keyword-based heuristics (FastEmbed doesn't have toxicity model).
        For production, consider using a dedicated toxicity API like
        Perspective API or OpenAI Moderation.

        Args:
            text: Text to check
            threshold: Optional custom threshold (uses default if None)

        Returns:
            Tuple of (is_toxic, toxicity_score)
        """
        if not self.is_available():
            raise RuntimeError("Semantic checking not available")

        # Simple keyword-based toxicity check
        # For production, use Perspective API or OpenAI Moderation
        toxic_keywords = [
            "hate",
            "kill",
            "violent",
            "racist",
            "sexist",
            # Add more as needed
        ]

        text_lower = text.lower()
        toxic_count = sum(1 for keyword in toxic_keywords if keyword in text_lower)

        toxicity_score = min(1.0, toxic_count * 0.3)  # Scale to 0-1
        is_toxic = toxicity_score > (threshold or self.toxicity_threshold)

        return is_toxic, toxicity_score

    def validate(
        self,
        query: str,
        response: str,
        check_toxicity: bool = True,
    ) -> SemanticQualityResult:
        """
        Run full semantic quality validation.

        Combines similarity and toxicity checks into single validation.

        Args:
            query: Original query text
            response: Generated response text
            check_toxicity: Whether to check for toxic content (default: True)

        Returns:
            SemanticQualityResult with all check results
        """
        if not self.is_available():
            return SemanticQualityResult(
                similarity=0.0,
                is_toxic=False,
                toxicity_score=0.0,
                passed=False,
                reason="semantic_checking_unavailable",
                metadata={"available": False},
            )

        # Check similarity
        similarity = self.check_similarity(query, response)

        # Check toxicity
        is_toxic = False
        toxicity_score = 0.0
        if check_toxicity:
            is_toxic, toxicity_score = self.check_toxicity(response)

        # Determine if passed
        passed = similarity >= self.similarity_threshold and not is_toxic

        reason = None
        if not passed:
            if similarity < self.similarity_threshold:
                reason = f"low_similarity ({similarity:.2f} < {self.similarity_threshold})"
            elif is_toxic:
                reason = f"toxic_content (score: {toxicity_score:.2f})"

        return SemanticQualityResult(
            similarity=similarity,
            is_toxic=is_toxic,
            toxicity_score=toxicity_score,
            passed=passed,
            reason=reason,
            metadata={
                "model": self.model_name,
                "similarity_threshold": self.similarity_threshold,
                "toxicity_threshold": self.toxicity_threshold,
            },
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def check_semantic_quality(
    query: str,
    response: str,
    similarity_threshold: float = 0.5,
    check_toxicity: bool = True,
) -> Optional[SemanticQualityResult]:
    """
    Convenience function for one-off semantic quality checks.

    Creates a checker instance and runs validation. Returns None if
    semantic checking is not available.

    Args:
        query: Original query text
        response: Generated response text
        similarity_threshold: Minimum similarity to pass
        check_toxicity: Whether to check for toxic content

    Returns:
        SemanticQualityResult or None if unavailable

    Example:
        >>> result = check_semantic_quality(
        ...     query="What is AI?",
        ...     response="AI stands for Artificial Intelligence..."
        ... )
        >>> if result and result.passed:
        ...     print("Quality check passed!")
    """
    checker = SemanticQualityChecker(similarity_threshold=similarity_threshold)

    if not checker.is_available():
        return None

    return checker.validate(query, response, check_toxicity=check_toxicity)
