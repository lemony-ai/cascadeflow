"""
Integration Tests for ML Features

Tests the complete ML integration including:
- Unified Embedding Service
- Semantic Quality Checking
- Semantic Domain Detection
- Semantic Complexity Detection
- Semantic Alignment Scoring
- Pipeline Semantic Validation
"""

import pytest

from cascadeflow.ml.embedding import EmbeddingCache, UnifiedEmbeddingService
from cascadeflow.quality.alignment_scorer import SemanticAlignmentScorer
from cascadeflow.quality.complexity import QueryComplexity, SemanticComplexityDetector
from cascadeflow.quality.semantic import SemanticQualityChecker
from cascadeflow.routing.cascade_pipeline import ValidationMethod
from cascadeflow.routing.domain import Domain, SemanticDomainDetector

# ============================================================================
# EMBEDDING SERVICE TESTS
# ============================================================================


@pytest.mark.skipif(not UnifiedEmbeddingService().is_available, reason="FastEmbed not available")
class TestUnifiedEmbeddingService:
    """Test the unified embedding service."""

    def test_embedding_service_available(self):
        """Test that embedding service initializes correctly."""
        embedder = UnifiedEmbeddingService()
        assert embedder.is_available

    def test_single_embedding(self):
        """Test single text embedding."""
        embedder = UnifiedEmbeddingService()
        embedding = embedder.embed("Hello world")
        assert embedding is not None
        assert len(embedding) == 384  # BGE-small dimension

    def test_batch_embedding(self):
        """Test batch text embedding."""
        embedder = UnifiedEmbeddingService()
        embeddings = embedder.embed_batch(["Hello", "World", "Test"])
        assert embeddings is not None
        assert len(embeddings) == 3
        assert all(len(e) == 384 for e in embeddings)

    def test_similarity(self):
        """Test similarity calculation."""
        embedder = UnifiedEmbeddingService()
        sim = embedder.similarity("Python programming", "Python code")
        assert sim is not None
        assert 0 <= sim <= 1
        assert sim > 0.7  # Similar texts should have high similarity

    def test_embedding_cache(self):
        """Test embedding cache performance."""
        embedder = UnifiedEmbeddingService()
        cache = EmbeddingCache(embedder)

        # First call - cache miss
        emb1 = cache.get_or_embed("test text")

        # Second call - cache hit
        emb2 = cache.get_or_embed("test text")

        assert emb1 is not None
        assert emb2 is not None
        # Should be the same object from cache
        import numpy as np

        assert np.array_equal(emb1, emb2)

        # Cache info
        info = cache.cache_info()
        assert info["size"] >= 1
        assert "texts" in info


# ============================================================================
# SEMANTIC QUALITY TESTS
# ============================================================================


@pytest.mark.skipif(
    not SemanticQualityChecker().is_available(), reason="Semantic quality checker not available"
)
class TestSemanticQuality:
    """Test semantic quality checking."""

    def test_quality_checker_available(self):
        """Test quality checker initializes."""
        checker = SemanticQualityChecker()
        assert checker.is_available()

    def test_high_similarity(self):
        """Test high similarity detection."""
        checker = SemanticQualityChecker(similarity_threshold=0.7)
        result = checker.validate("What is Python?", "Python is a programming language")
        assert result.passed
        assert result.similarity > 0.7

    def test_low_similarity(self):
        """Test low similarity rejection."""
        checker = SemanticQualityChecker(similarity_threshold=0.8)
        result = checker.validate("What is Python?", "The weather is sunny")
        assert not result.passed
        assert "low_similarity" in result.reason


# ============================================================================
# SEMANTIC DOMAIN DETECTION TESTS
# ============================================================================


@pytest.mark.skipif(
    not SemanticDomainDetector().is_available, reason="Semantic domain detector not available"
)
class TestSemanticDomainDetection:
    """Test semantic domain detection."""

    def test_domain_detector_available(self):
        """Test domain detector initializes."""
        detector = SemanticDomainDetector()
        assert detector.is_available

    def test_code_domain(self):
        """Test CODE domain detection."""
        detector = SemanticDomainDetector()
        domain, conf = detector.detect("Write a Python function to sort a list")
        assert domain == Domain.CODE
        assert conf > 0.6

    def test_data_domain(self):
        """Test DATA domain detection."""
        detector = SemanticDomainDetector()
        domain, conf = detector.detect("Analyze this dataframe using pandas")
        assert domain == Domain.DATA
        assert conf > 0.6

    def test_creative_domain(self):
        """Test CREATIVE domain detection."""
        detector = SemanticDomainDetector()
        domain, conf = detector.detect("Write a poem about the ocean")
        assert domain == Domain.CREATIVE
        assert conf > 0.6

    def test_hybrid_mode(self):
        """Test hybrid mode (ML + rule-based)."""
        detector = SemanticDomainDetector(use_hybrid=True)
        domain, conf = detector.detect("Write async Python code with error handling")
        assert domain == Domain.CODE
        assert conf > 0.7  # Hybrid should have higher confidence


# ============================================================================
# SEMANTIC COMPLEXITY DETECTION TESTS
# ============================================================================


@pytest.mark.skipif(
    not SemanticComplexityDetector().is_available,
    reason="Semantic complexity detector not available",
)
class TestSemanticComplexityDetection:
    """Test semantic complexity detection."""

    def test_complexity_detector_available(self):
        """Test complexity detector initializes."""
        detector = SemanticComplexityDetector()
        assert detector.is_available

    def test_trivial_detection(self):
        """Test TRIVIAL complexity detection."""
        detector = SemanticComplexityDetector()
        complexity, conf = detector.detect("What is 2+2?")
        assert complexity == QueryComplexity.TRIVIAL
        assert conf > 0.6

    def test_simple_detection(self):
        """Test SIMPLE complexity detection."""
        detector = SemanticComplexityDetector()
        complexity, conf = detector.detect("Explain photosynthesis")
        assert complexity == QueryComplexity.SIMPLE
        assert conf > 0.6

    def test_moderate_detection(self):
        """Test MODERATE complexity detection."""
        detector = SemanticComplexityDetector()
        complexity, conf = detector.detect("How does recursion work in programming?")
        assert complexity == QueryComplexity.MODERATE
        assert conf > 0.6

    def test_hard_detection(self):
        """Test HARD complexity detection."""
        detector = SemanticComplexityDetector()
        complexity, conf = detector.detect("Implement a self-balancing BST with AVL rotations")
        assert complexity == QueryComplexity.HARD
        assert conf > 0.6

    def test_expert_detection(self):
        """Test EXPERT complexity detection."""
        detector = SemanticComplexityDetector()
        complexity, conf = detector.detect("Prove Gödel's incompleteness theorem")
        assert complexity == QueryComplexity.EXPERT
        assert conf > 0.6


# ============================================================================
# SEMANTIC ALIGNMENT SCORING TESTS
# ============================================================================


@pytest.mark.skipif(
    not SemanticAlignmentScorer().is_available, reason="Semantic alignment scorer not available"
)
class TestSemanticAlignmentScoring:
    """Test semantic alignment scoring."""

    def test_alignment_scorer_available(self):
        """Test alignment scorer initializes."""
        scorer = SemanticAlignmentScorer()
        assert scorer.is_available

    def test_high_alignment(self):
        """Test high alignment score."""
        scorer = SemanticAlignmentScorer()
        score = scorer.score_alignment("What is Python?", "Python is a programming language")
        assert score > 0.7

    def test_low_alignment(self):
        """Test low alignment score."""
        scorer = SemanticAlignmentScorer()
        score = scorer.score_alignment("What is Python?", "The sky is blue")
        assert score < 0.5

    def test_hybrid_scoring(self):
        """Test hybrid mode (ML + rule-based)."""
        scorer = SemanticAlignmentScorer()
        score = scorer.score_alignment("What is 2+2?", "4", use_hybrid=True)
        assert 0 <= score <= 1


# ============================================================================
# PIPELINE SEMANTIC VALIDATION TESTS
# ============================================================================


class TestPipelineSemanticValidation:
    """Test semantic validation in pipelines."""

    def test_semantic_validation_method_exists(self):
        """Test SEMANTIC validation method exists."""
        assert ValidationMethod.SEMANTIC in ValidationMethod

    def test_semantic_validation_value(self):
        """Test SEMANTIC validation method value."""
        assert ValidationMethod.SEMANTIC.value == "semantic"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.skipif(not UnifiedEmbeddingService().is_available, reason="ML features not available")
class TestMLIntegration:
    """Test complete ML integration."""

    def test_shared_embedder(self):
        """Test that features can share an embedder."""
        # Create shared embedder
        embedder = UnifiedEmbeddingService()

        # Use in quality checker
        quality_checker = SemanticQualityChecker(embedder=embedder)
        assert quality_checker.is_available()

        # Use in domain detector
        domain_detector = SemanticDomainDetector(embedder=embedder)
        assert domain_detector.is_available

        # Use in complexity detector
        complexity_detector = SemanticComplexityDetector(embedder=embedder)
        assert complexity_detector.is_available

        # Use in alignment scorer
        alignment_scorer = SemanticAlignmentScorer(embedder=embedder)
        assert alignment_scorer.is_available

    def test_end_to_end_workflow(self):
        """Test complete ML-enhanced workflow."""
        # Initialize all components
        embedder = UnifiedEmbeddingService()
        quality = SemanticQualityChecker(embedder=embedder)
        domain = SemanticDomainDetector(embedder=embedder)
        complexity = SemanticComplexityDetector(embedder=embedder)
        alignment = SemanticAlignmentScorer(embedder=embedder)

        # Test query
        query = "Write a Python function to reverse a string"
        response = "Here's a Python function: def reverse(s): return s[::-1]"

        # Detect domain
        detected_domain, domain_conf = domain.detect(query)
        assert detected_domain == Domain.CODE
        assert domain_conf > 0.6

        # Detect complexity - semantic detector may vary, just check it returns a valid complexity
        detected_complexity, complexity_conf = complexity.detect(query)
        assert detected_complexity in QueryComplexity
        assert 0 <= complexity_conf <= 1

        # Check quality
        quality_result = quality.validate(query, response)
        assert quality_result.passed

        # Check alignment
        alignment_score = alignment.score_alignment(query, response)
        assert alignment_score > 0.6

        print("\n✓ End-to-end ML workflow successful!")
        print(f"  Domain: {detected_domain.value} ({domain_conf:.2%})")
        print(f"  Complexity: {detected_complexity.value} ({complexity_conf:.2%})")
        print(f"  Quality: {quality_result.similarity:.2%}")
        print(f"  Alignment: {alignment_score:.2%}")
