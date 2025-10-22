"""
Semantic routing for intelligent query-to-model matching.

Uses sentence-transformers for embedding-based similarity matching.
Gracefully falls back to keyword routing if dependencies unavailable.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SemanticRouter:
    """
    Semantic routing using embeddings.

    Uses sentence-transformers to match queries to models via semantic similarity.
    Falls back to keyword routing if sentence-transformers not available.

    Example:
        >>> router = SemanticRouter()
        >>> if router.is_available():
        >>>     best_models = router.route(query, models, top_k=3)
    """

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        """
        Initialize semantic router.

        Args:
            embedding_model: Sentence-transformers model name
                           (default: all-MiniLM-L6-v2, ~80MB, fast)
        """
        self.embedding_model_name = embedding_model
        self.model = None
        self.model_embeddings: dict[str, np.ndarray] = {}
        self._available = False

        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(embedding_model)
            self._available = True
            logger.info(f"✓ Semantic routing enabled with {embedding_model}")
        except ImportError:
            logger.warning(
                "⚠️ sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            logger.warning("Falling back to keyword-based routing")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
            logger.warning("Falling back to keyword-based routing")

    def is_available(self) -> bool:
        """Check if semantic routing is available."""
        return self._available

    def precompute_model_embeddings(self, models: list[any]):
        """
        Precompute embeddings for model capabilities.

        Creates semantic embeddings from model metadata (name, domains,
        keywords, description) for fast similarity matching.

        Args:
            models: List of ModelConfig objects
        """
        if not self.is_available():
            logger.debug("Semantic routing unavailable, skipping embedding precomputation")
            return

        for model in models:
            # Build capability text from model metadata
            capability_parts = [model.name]

            # Add domains
            if hasattr(model, "domains") and model.domains:
                capability_parts.extend(model.domains)

            # Add keywords if available
            if hasattr(model, "keywords") and model.keywords:
                capability_parts.extend(model.keywords)

            # Add description if available
            if hasattr(model, "description") and model.description:
                capability_parts.append(model.description)

            capability_text = " ".join(capability_parts)

            # Compute and store embedding
            try:
                self.model_embeddings[model.name] = self.model.encode(
                    capability_text, show_progress_bar=False, convert_to_numpy=True
                )
            except Exception as e:
                logger.warning(f"Failed to encode model {model.name}: {e}")

        logger.info(f"Precomputed embeddings for {len(self.model_embeddings)} models")

    def route(
        self, query: str, models: list[any], top_k: int = 3, similarity_threshold: float = 0.3
    ) -> list[tuple[any, float]]:
        """
        Route query to best models using semantic similarity.

        Args:
            query: User query
            models: List of ModelConfig objects
            top_k: Number of top models to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of (model, similarity_score) tuples, sorted by similarity
            Returns empty list if semantic routing unavailable
        """
        if not self.is_available():
            logger.debug("Semantic routing unavailable for this query")
            return []

        if not self.model_embeddings:
            logger.warning("No model embeddings precomputed")
            return []

        try:
            # Encode query
            query_embedding = self.model.encode(
                query, show_progress_bar=False, convert_to_numpy=True
            )

            # Calculate similarities
            similarities = []
            for model in models:
                if model.name not in self.model_embeddings:
                    logger.debug(f"No embedding for model {model.name}")
                    continue

                model_embedding = self.model_embeddings[model.name]

                # Cosine similarity
                similarity = self._cosine_similarity(query_embedding, model_embedding)

                if similarity >= similarity_threshold:
                    similarities.append((model, float(similarity)))

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Return top-k
            top_matches = similarities[:top_k]

            if top_matches:
                logger.debug(
                    f"Semantic routing: top match {top_matches[0][0].name} "
                    f"(similarity: {top_matches[0][1]:.3f})"
                )
            else:
                logger.debug(f"No models above similarity threshold {similarity_threshold}")

            return top_matches

        except Exception as e:
            logger.error(f"Error during semantic routing: {e}")
            return []

    def get_model_similarity(self, query: str, model_name: str) -> Optional[float]:
        """
        Get similarity score between query and specific model.

        Args:
            query: User query
            model_name: Name of model to check

        Returns:
            Similarity score (0-1) or None if unavailable
        """
        if not self.is_available():
            return None

        if model_name not in self.model_embeddings:
            return None

        try:
            query_embedding = self.model.encode(
                query, show_progress_bar=False, convert_to_numpy=True
            )

            model_embedding = self.model_embeddings[model_name]
            similarity = self._cosine_similarity(query_embedding, model_embedding)

            return float(similarity)

        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return None

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        # Handle edge cases
        if a is None or b is None:
            return 0.0

        # Normalize vectors
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if a_norm == 0 or b_norm == 0:
            return 0.0

        # Cosine similarity
        similarity = np.dot(a, b) / (a_norm * b_norm)

        # Clamp to [0, 1] (sometimes numerical errors cause slight overflow)
        similarity = np.clip(similarity, 0.0, 1.0)

        return float(similarity)

    def clear_cache(self):
        """Clear precomputed embeddings (useful if models change)."""
        self.model_embeddings.clear()
        logger.info("Cleared model embedding cache")

    def get_stats(self) -> dict:
        """Get routing statistics."""
        return {
            "available": self._available,
            "embedding_model": self.embedding_model_name,
            "cached_models": len(self.model_embeddings),
            "model_names": list(self.model_embeddings.keys()),
        }


class HybridRouter:
    """
    Hybrid router combining semantic and keyword-based routing.

    Uses semantic routing when available, falls back to keyword matching,
    and can blend both approaches for better results.
    """

    def __init__(
        self,
        semantic_router: Optional[SemanticRouter] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        """
        Initialize hybrid router.

        Args:
            semantic_router: SemanticRouter instance (creates if None)
            semantic_weight: Weight for semantic similarity (0-1)
            keyword_weight: Weight for keyword matching (0-1)
        """
        self.semantic_router = semantic_router or SemanticRouter()
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

        # Normalize weights
        total = semantic_weight + keyword_weight
        if total > 0:
            self.semantic_weight /= total
            self.keyword_weight /= total

    def route(
        self,
        query: str,
        models: list[any],
        query_domains: Optional[list[str]] = None,
        top_k: int = 3,
    ) -> list[tuple[any, float]]:
        """
        Route using hybrid approach.

        Combines semantic similarity with keyword/domain matching.

        Args:
            query: User query
            models: List of ModelConfig objects
            query_domains: Detected domains (e.g., ["code", "math"])
            top_k: Number of models to return

        Returns:
            List of (model, combined_score) tuples
        """
        scores = {}

        # 1. Get semantic scores
        if self.semantic_router.is_available():
            semantic_matches = self.semantic_router.route(query, models, top_k=len(models))
            for model, similarity in semantic_matches:
                scores[model.name] = self.semantic_weight * similarity

        # 2. Add keyword/domain scores
        for model in models:
            keyword_score = self._keyword_match_score(model, query, query_domains)

            if model.name in scores:
                scores[model.name] += self.keyword_weight * keyword_score
            else:
                scores[model.name] = self.keyword_weight * keyword_score

        # 3. Sort and return top-k
        sorted_models = [(model, scores.get(model.name, 0.0)) for model in models]
        sorted_models.sort(key=lambda x: x[1], reverse=True)

        return sorted_models[:top_k]

    def _keyword_match_score(
        self, model: any, query: str, query_domains: Optional[list[str]] = None
    ) -> float:
        """
        Calculate keyword-based match score.

        Args:
            model: ModelConfig object
            query: User query
            query_domains: Detected domains

        Returns:
            Match score (0-1)
        """
        score = 0.0
        query_lower = query.lower()

        # Domain matching (strongest signal)
        if query_domains and hasattr(model, "domains") and model.domains:
            domain_matches = len(set(query_domains) & set(model.domains))
            if domain_matches > 0:
                score += 0.6 * (domain_matches / len(query_domains))

        # Keyword matching
        if hasattr(model, "keywords") and model.keywords:
            keyword_matches = sum(1 for kw in model.keywords if kw.lower() in query_lower)
            if keyword_matches > 0:
                score += 0.3 * min(1.0, keyword_matches / 3)

        # Model name matching (weak signal)
        if hasattr(model, "name"):
            model_name_lower = model.name.lower()
            # Check for model name mentions in query
            if model_name_lower in query_lower:
                score += 0.1

        return min(1.0, score)


# Convenience function
def create_router(strategy: str = "semantic", **kwargs) -> Optional[SemanticRouter]:
    """
    Create a router based on strategy.

    Args:
        strategy: "semantic", "keyword", or "hybrid"
        **kwargs: Additional arguments for router

    Returns:
        Router instance or None for keyword-only
    """
    if strategy == "semantic":
        return SemanticRouter(**kwargs)
    elif strategy == "hybrid":
        return HybridRouter(**kwargs)
    elif strategy == "keyword":
        return None  # Use keyword routing in execution.py
    else:
        logger.warning(f"Unknown routing strategy: {strategy}, using semantic")
        return SemanticRouter(**kwargs)
