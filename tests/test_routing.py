"""Test semantic routing with sentence-transformers."""

import pytest
from cascadeflow.routing import SemanticRouter
from cascadeflow.config import ModelConfig


class TestSemanticRouter:

    def setup_method(self):
        self.router = SemanticRouter()

        # Create test models with domains
        self.models = [
            ModelConfig(
                name="codellama",
                provider="ollama",
                cost=0.0,
                domains=["code"],
                keywords=["python", "javascript", "debug", "bug"],
                description="Specialized code model"
            ),
            ModelConfig(
                name="mathstral",
                provider="ollama",
                cost=0.0,
                domains=["math"],
                keywords=["equation", "calculate", "algebra"],
                description="Mathematical reasoning model"
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                domains=["general"],
                keywords=["general", "versatile"],
                description="General purpose model"
            ),
        ]

    def test_router_availability(self):
        """Test if router is available (depends on sentence-transformers)."""
        # This will be True if sentence-transformers installed, False otherwise
        if self.router.is_available():
            assert self.router.model is not None
            print("\n✓ Semantic routing available")
        else:
            assert self.router.model is None
            print("\n⚠️ Semantic routing unavailable (sentence-transformers not installed)")

    @pytest.mark.skipif(
        not SemanticRouter().is_available(),
        reason="sentence-transformers not installed"
    )
    def test_precompute_embeddings(self):
        """Test embedding precomputation."""
        self.router.precompute_model_embeddings(self.models)

        assert len(self.router.model_embeddings) == 3
        assert "codellama" in self.router.model_embeddings
        assert "mathstral" in self.router.model_embeddings
        assert "gpt-4" in self.router.model_embeddings

    @pytest.mark.skipif(
        not SemanticRouter().is_available(),
        reason="sentence-transformers not installed"
    )
    def test_code_query_routing(self):
        """Test that code queries route to code model."""
        self.router.precompute_model_embeddings(self.models)

        matches = self.router.route(
            query="Help me debug this Python function",
            models=self.models,
            top_k=3
        )

        assert len(matches) > 0
        # Top match should be codellama
        top_model, similarity = matches[0]
        print(f"\nTop match: {top_model.name} (similarity: {similarity:.3f})")
        assert top_model.name == "codellama"
        assert similarity > 0.3

    @pytest.mark.skipif(
        not SemanticRouter().is_available(),
        reason="sentence-transformers not installed"
    )
    def test_math_query_routing(self):
        """Test that math queries route to math model."""
        self.router.precompute_model_embeddings(self.models)

        matches = self.router.route(
            query="Solve this quadratic equation",
            models=self.models,
            top_k=3
        )

        assert len(matches) > 0
        top_model, similarity = matches[0]
        print(f"\nTop match: {top_model.name} (similarity: {similarity:.3f})")
        # Should prefer mathstral
        assert top_model.name in ["mathstral", "gpt-4"]

    @pytest.mark.skipif(
        not SemanticRouter().is_available(),
        reason="sentence-transformers not installed"
    )
    def test_similarity_threshold(self):
        """Test similarity threshold filtering."""
        self.router.precompute_model_embeddings(self.models)

        # Very specific query - might not match any model well
        matches = self.router.route(
            query="xyzabc nonsense query that matches nothing",
            models=self.models,
            top_k=3,
            similarity_threshold=0.9  # Very high threshold
        )

        # Might return empty if no model exceeds threshold
        print(f"\nMatches for nonsense query: {len(matches)}")
        for model, sim in matches:
            print(f"  {model.name}: {sim:.3f}")

    @pytest.mark.skipif(
        not SemanticRouter().is_available(),
        reason="sentence-transformers not installed"
    )
    def test_get_model_similarity(self):
        """Test getting similarity for specific model."""
        self.router.precompute_model_embeddings(self.models)

        similarity = self.router.get_model_similarity(
            query="Fix this Python bug",
            model_name="codellama"
        )

        assert similarity is not None
        assert 0.0 <= similarity <= 1.0
        print(f"\nSimilarity to codellama: {similarity:.3f}")

    def test_fallback_when_unavailable(self):
        """Test graceful fallback when semantic routing unavailable."""
        # Create router but don't initialize embeddings
        router = SemanticRouter()

        if not router.is_available():
            # Should return empty list, not crash
            matches = router.route(
                query="any query",
                models=self.models,
                top_k=3
            )
            assert matches == []
            print("\n✓ Graceful fallback works")

    def test_stats(self):
        """Test getting router statistics."""
        if self.router.is_available():
            self.router.precompute_model_embeddings(self.models)

        stats = self.router.get_stats()

        assert "available" in stats
        assert "embedding_model" in stats
        assert stats["embedding_model"] == "all-MiniLM-L6-v2"
        print(f"\nRouter stats: {stats}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])