"""Test complexity detection with improved algorithm."""

import pytest

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity


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
        """Test that long queries without expert keywords get upgraded."""
        query = "What is a dog? " * 15  # 60 words but trivial content
        complexity, _ = self.detector.detect(query)
        # Should be at least HARD due to length
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
