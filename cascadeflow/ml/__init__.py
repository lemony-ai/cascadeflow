"""
ML Module for cascadeflow

Optional machine learning components for enhanced quality validation,
domain detection, and complexity analysis.

All ML features:
- Are completely OPTIONAL (graceful degradation)
- Require `fastembed` package (pip install fastembed)
- Use lightweight ONNX models (~40MB)
- Provide better accuracy than rule-based
- Add ~25-50ms latency (optimized)

Components:
- UnifiedEmbeddingService: Single embedding model for all tasks
- EmbeddingCache: Request-scoped caching for performance

Example:
    >>> from cascadeflow.ml import UnifiedEmbeddingService
    >>>
    >>> # Initialize (lazy loads model)
    >>> embedder = UnifiedEmbeddingService()
    >>>
    >>> if embedder.is_available:
    ...     similarity = embedder.similarity("query", "response")
    ...     print(f"Similarity: {similarity:.2%}")
"""

from .embedding import (
    UnifiedEmbeddingService,
    EmbeddingCache,
)

__all__ = [
    "UnifiedEmbeddingService",
    "EmbeddingCache",
]

__version__ = "0.7.0"  # ML integration
