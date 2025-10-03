"""Test suite for complexity detection."""

import pytest
from cascadeflow.complexity import ComplexityDetector, QueryComplexity


class TestComplexityDetector:
    """Test complexity detection."""

    def test_trivial_math(self):
        detector = ComplexityDetector()
        complexity, confidence = detector.detect("What is 2+2?")
        assert complexity == QueryComplexity.TRIVIAL
        assert confidence > 0.9

    def test_trivial_fact(self):
        detector = ComplexityDetector()
        complexity, confidence = detector.detect("capital of France")
        assert complexity == QueryComplexity.TRIVIAL
        assert confidence > 0.9

    def test_simple_query(self):
        detector = ComplexityDetector()
        complexity, _ = detector.detect("Explain machine learning")
        assert complexity == QueryComplexity.SIMPLE

    def test_moderate_query(self):
        detector = ComplexityDetector()
        complexity, _ = detector.detect("Compare Python and JavaScript")
        assert complexity == QueryComplexity.MODERATE

    def test_hard_query(self):
        detector = ComplexityDetector()
        complexity, _ = detector.detect("Analyze the geopolitical implications of...")
        assert complexity == QueryComplexity.HARD

    def test_expert_query(self):
        detector = ComplexityDetector()
        complexity, _ = detector.detect("Implement a production-grade scalable API")
        assert complexity == QueryComplexity.EXPERT

    def test_stats(self):
        detector = ComplexityDetector()
        detector.detect("What is 2+2?")
        detector.detect("Explain AI")
        stats = detector.get_stats()
        assert stats["total_detected"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])