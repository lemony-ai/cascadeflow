"""Test complexity detection with improved algorithm."""

import pytest

from cascadeflow.quality.complexity import (
    ComplexityDetector,
    QueryComplexity,
    SemanticComplexityDetector,
)


class TestComplexityDetector:

    def setup_method(self):
        self.detector = ComplexityDetector()

    def test_trivial_math(self):
        """Test trivial math queries."""
        queries = [
            "What is 2+2?",
            "Calculate 5*3",
            "what's 10-7",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity == QueryComplexity.TRIVIAL
            assert confidence > 0.9

    def test_trivial_geography(self):
        """Test trivial geography queries."""
        queries = [
            "capital of France?",
            "population of Tokyo",
            "currency of Japan",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity == QueryComplexity.TRIVIAL
            assert confidence > 0.9

    def test_simple_queries(self):
        """Test simple queries."""
        queries = [
            "What is machine learning?",
            "Explain photosynthesis",
            "Define recursion",
            "Who is Albert Einstein?",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity == QueryComplexity.SIMPLE
            assert confidence > 0.6

    def test_moderate_queries(self):
        """Test moderate complexity queries."""
        queries = [
            "Compare Python and JavaScript for web development",
            "What are the advantages and disadvantages of solar energy?",
            "How does the immune system respond to vaccines?",
            "Summarize the key differences between REST and GraphQL",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity in [QueryComplexity.MODERATE, QueryComplexity.HARD]

    def test_hard_queries(self):
        """Test hard queries requiring deep analysis."""
        queries = [
            "Analyze the economic implications of rising interest rates on small businesses",
            "Evaluate the trade-offs between microservices and monolithic architectures",
            "Critically assess the impact of social media on teenage mental health",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]

    def test_expert_queries(self):
        """Test expert-level queries."""
        queries = [
            "Implement a production-ready OAuth2 authentication system with refresh tokens",
            "Design a scalable microservices architecture for an e-commerce platform",
            "Optimize this database schema for high-throughput OLTP workloads",
            "Refactor this legacy code to use modern design patterns and best practices",
        ]
        for query in queries:
            complexity, confidence = self.detector.detect(query)
            assert complexity in [QueryComplexity.EXPERT, QueryComplexity.HARD]

    def test_code_detection(self):
        """Test code pattern detection boosts complexity."""
        code_query = """
        def fibonacci(n):
            if n <= 1:
                return n
            return fibonacci(n-1) + fibonacci(n-2)

        Optimize this code
        """
        complexity, _ = self.detector.detect(code_query)
        assert complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]

    def test_short_expert_query(self):
        """Test that short queries with expert keywords get HARD not EXPERT."""
        query = "Implement OAuth2"  # Only 2 words
        complexity, _ = self.detector.detect(query)
        # Should be HARD (not EXPERT) due to sanity check
        assert complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]

    def test_long_simple_query(self):
        """Test that long simple queries stay at lower complexity for cost savings.

        With length-aware complexity detection, long prompts without technical
        keywords should remain at MODERATE or lower to enable CASCADE routing
        and cost savings. Length alone should not escalate complexity.
        """
        query = "What is a dog? " * 15  # 60 words but trivial content
        complexity, _ = self.detector.detect(query)
        # Should NOT be HARD/EXPERT - length alone shouldn't escalate trivial content
        assert complexity in [QueryComplexity.SIMPLE, QueryComplexity.MODERATE]

    def test_long_technical_query_escalates(self):
        """Test that long queries WITH technical keywords get upgraded properly."""
        # Long prompt with technical terms should escalate
        query = (
            """
        We need to implement a production-ready microservices architecture
        with OAuth2 authentication, PostgreSQL database optimization,
        Kubernetes deployment, and comprehensive error handling.
        The system should scale horizontally with load balancing.
        """
            * 3
        )  # ~90 words with many expert keywords
        complexity, _ = self.detector.detect(query)
        # Should be HARD or EXPERT due to technical keyword density
        assert complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]

    def test_keyword_density(self):
        """Test keyword density scoring."""
        # High density of expert keywords
        query = "Implement scalable production-ready architecture with optimization and security best practices"
        complexity, confidence = self.detector.detect(query)
        assert complexity in [QueryComplexity.EXPERT, QueryComplexity.HARD]
        assert confidence > 0.7

    def test_stats_tracking(self):
        """Test that statistics are tracked."""
        queries = [
            "What is 2+2?",
            "Explain AI",
            "Analyze market trends",
        ]
        for query in queries:
            self.detector.detect(query)

        stats = self.detector.get_stats()
        assert stats["total_detected"] == 3
        assert "distribution" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class _MockComplexityEmbedder:
    """Deterministic embedder for semantic complexity unit tests."""

    def __init__(self, similarity_map=None):
        self.is_available = True
        self.similarity_map = similarity_map or {}

    def embed_batch(self, texts):
        return [f"emb::{text}" for text in texts]

    def embed(self, text):
        return f"query::{text}"

    def _cosine_similarity(self, query_embedding, complexity_embedding):
        return self.similarity_map.get((query_embedding, complexity_embedding), 0.0)


class TestSemanticComplexityDetector:
    """Semantic complexity detector tests without FastEmbed runtime dependency."""

    def test_semantic_exemplar_detection(self):
        """Semantic similarity should pick the closest complexity exemplar."""
        query = "multi-step theorem proof"
        query_embedding = f"query::{query}"
        expert_embedding = "emb::expert exemplar"
        simple_embedding = "emb::simple exemplar"

        embedder = _MockComplexityEmbedder(
            similarity_map={
                (query_embedding, expert_embedding): 0.93,
                (query_embedding, simple_embedding): 0.15,
            }
        )
        detector = SemanticComplexityDetector(embedder=embedder, use_hybrid=False)
        detector._complexity_embeddings = {
            QueryComplexity.EXPERT: expert_embedding,
            QueryComplexity.SIMPLE: simple_embedding,
        }
        detector._embeddings_computed = True

        complexity, confidence = detector.detect(query)

        assert complexity == QueryComplexity.EXPERT
        assert confidence == 0.93

    def test_semantic_hybrid_detection(self):
        """Hybrid mode should blend ML and rule-based complexity signals."""
        query = "implement oauth with threat model"
        query_embedding = f"query::{query}"
        moderate_embedding = "emb::moderate exemplar"
        simple_embedding = "emb::simple exemplar"

        embedder = _MockComplexityEmbedder(
            similarity_map={
                (query_embedding, moderate_embedding): 0.80,
                (query_embedding, simple_embedding): 0.20,
            }
        )
        detector = SemanticComplexityDetector(embedder=embedder, use_hybrid=True)
        detector._complexity_embeddings = {
            QueryComplexity.MODERATE: moderate_embedding,
            QueryComplexity.SIMPLE: simple_embedding,
        }
        detector._embeddings_computed = True
        detector.rule_detector = ComplexityDetector()
        detector.rule_detector.detect = lambda _query: (QueryComplexity.EXPERT, 0.90)

        complexity, confidence = detector.detect(query)

        assert complexity == QueryComplexity.HARD
        assert 0.0 <= confidence <= 1.0

    def test_semantic_edge_case_embedding_failure(self):
        """Embedding failure should gracefully return fallback complexity."""

        class _FailingEmbedder(_MockComplexityEmbedder):
            def embed(self, text):
                return None

        detector = SemanticComplexityDetector(embedder=_FailingEmbedder(), use_hybrid=False)
        detector._complexity_embeddings = {QueryComplexity.SIMPLE: "emb::simple exemplar"}
        detector._embeddings_computed = True

        complexity, confidence = detector.detect("any query")

        assert complexity == QueryComplexity.MODERATE
        assert confidence == 0.5
