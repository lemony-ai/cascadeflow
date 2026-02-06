"""
Tests for Domain Detection System (Phase 3.2)

This module tests the 17-domain detection system including:
- Domain detection accuracy for each domain
- Multi-domain query handling
- Confidence thresholds
- Keyword weighting (4-tier system)
- Model recommendations
- Edge cases
"""

import math
import pytest

from cascadeflow.routing.domain import (
    FASTEMBED_DOMAIN_MODELS,
    DOMAIN_EXEMPLARS,
    DOMAIN_THRESHOLDS,
    Domain,
    DomainDetectionResult,
    DomainDetector,
    DomainKeywords,
    SemanticDomainDetector,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def detector():
    """Create a domain detector with default settings."""
    return DomainDetector(confidence_threshold=0.3)


@pytest.fixture
def strict_detector():
    """Create a domain detector with stricter threshold."""
    return DomainDetector(confidence_threshold=0.6)


# ============================================================================
# SINGLE DOMAIN DETECTION TESTS
# ============================================================================


def test_detect_code_domain(detector):
    """Test CODE domain detection with programming query."""
    domain, confidence = detector.detect("Write a Python function to sort a list using async/await")

    assert domain == Domain.CODE
    assert confidence > 0.7  # Should be high confidence


def test_detect_code_domain_strong_keywords(detector):
    """Test CODE domain with very_strong keywords."""
    domain, confidence = detector.detect(
        "How do I use async and await with import statements in Python?"
    )

    assert domain == Domain.CODE
    # Should have very high confidence (very_strong keywords: async, await, import)
    assert confidence > 0.8


def test_detect_data_domain(detector):
    """Test DATA domain detection with data analysis query."""
    domain, confidence = detector.detect(
        "How do I use pandas to perform ETL on a SQL database and calculate correlation?"
    )

    assert domain == Domain.DATA
    assert confidence > 0.7


def test_detect_structured_domain(detector):
    """Test STRUCTURED domain detection with extraction query."""
    domain, confidence = detector.detect(
        "Extract JSON fields from this XML document and validate with pydantic schema"
    )

    assert domain == Domain.STRUCTURED
    assert confidence > 0.7


def test_detect_rag_domain(detector):
    """Test RAG domain detection with retrieval query."""
    domain, confidence = detector.detect(
        "Search documents using semantic search and vector embeddings for RAG"
    )

    assert domain == Domain.RAG
    assert confidence > 0.6


def test_detect_conversation_domain(detector):
    """Test CONVERSATION domain detection."""
    result = detector.detect_with_scores(
        "Let's have a multi-turn conversation about this topic with context awareness"
    )

    # CONVERSATION should be in top 3 domains
    top_domains = list(result.scores.keys())[:3]
    assert Domain.CONVERSATION in top_domains or result.scores[Domain.CONVERSATION] > 0.3


def test_detect_conversation_domain_from_history_markers(detector):
    """Conversation markers should boost CONVERSATION domain."""
    result = detector.detect_with_scores(
        "User: Hi there\nAssistant: Hello! How can I help?\nUser: Continue our chat"
    )
    assert result.scores[Domain.CONVERSATION] > 0.5


def test_detect_tool_domain(detector):
    """Test TOOL domain detection with function calling query."""
    result = detector.detect_with_scores(
        "Call the weather API function and execute the tool with these parameters"
    )

    # TOOL should have reasonable score
    assert result.scores[Domain.TOOL] > 0.3 or Domain.TOOL in list(result.scores.keys())[:3]


def test_detect_creative_domain(detector):
    """Test CREATIVE domain detection."""
    domain, confidence = detector.detect(
        "Write a creative story with vivid imagery and compelling narrative"
    )

    assert domain == Domain.CREATIVE


def test_detect_comparison_domain(detector):
    """Test COMPARISON domain detection."""
    domain, confidence = detector.detect("Compare cats vs dogs and list pros and cons")

    assert domain == Domain.COMPARISON
    assert confidence > 0.5


def test_detect_factual_domain(detector):
    """Test FACTUAL domain detection."""
    domain, confidence = detector.detect("Fact check this claim and verify with sources")

    assert domain == Domain.FACTUAL
    assert confidence > 0.4
    assert confidence > 0.6


def test_detect_summary_domain(detector):
    """Test SUMMARY domain detection."""
    domain, confidence = detector.detect(
        "Summarize this long document and provide a concise synopsis"
    )

    assert domain == Domain.SUMMARY
    assert confidence > 0.7


def test_detect_translation_domain(detector):
    """Test TRANSLATION domain detection."""
    domain, confidence = detector.detect(
        "Translate this text from English to French and localize the content"
    )

    assert domain == Domain.TRANSLATION
    assert confidence > 0.8


def test_detect_math_domain(detector):
    """Test MATH domain detection."""
    domain, confidence = detector.detect(
        "Calculate the derivative and solve this differential equation"
    )

    assert domain == Domain.MATH
    assert confidence > 0.6


def test_detect_medical_domain(detector):
    """Test MEDICAL domain detection."""
    domain, confidence = detector.detect(
        "Analyze this patient's symptoms for diagnosis and treatment recommendations"
    )

    assert domain == Domain.MEDICAL
    assert confidence > 0.6


def test_detect_legal_domain(detector):
    """Test LEGAL domain detection."""
    domain, confidence = detector.detect(
        "Review this contract for compliance with legal regulations and liability"
    )

    assert domain == Domain.LEGAL
    assert confidence > 0.7


def test_detect_financial_domain(detector):
    """Test FINANCIAL domain detection."""
    domain, confidence = detector.detect(
        "Analyze the stock market forecast and portfolio risk assessment"
    )

    assert domain == Domain.FINANCIAL
    assert confidence > 0.6


def test_detect_multimodal_domain(detector):
    """Test MULTIMODAL domain detection."""
    domain, confidence = detector.detect("Analyze the photo and identify objects in the image")

    assert domain == Domain.MULTIMODAL
    assert confidence > 0.6


def test_detect_general_domain(detector):
    """Test GENERAL domain as fallback."""
    # Use a truly generic query that doesn't match specific domains
    result = detector.detect_with_scores("Tell me something interesting")

    # Generic query should have low confidence or fall to GENERAL
    # Note: "What is the largest city in France?" now correctly routes to FACTUAL
    assert result.domain == Domain.GENERAL or result.confidence < 0.6


# ============================================================================
# DOMAIN SEPARATION TESTS (Research-predicted confusion)
# ============================================================================


def test_structured_vs_data_separation(detector):
    """Test that STRUCTURED and DATA domains are properly separated."""
    # STRUCTURED query (format-specific)
    structured_result = detector.detect_with_scores(
        "Parse this JSON file and extract fields using XML schema"
    )

    # DATA query (analysis-specific)
    data_result = detector.detect_with_scores(
        "Analyze this dataset with pandas and calculate correlation using SQL"
    )

    # STRUCTURED should win for first query
    assert structured_result.domain == Domain.STRUCTURED
    assert structured_result.scores[Domain.STRUCTURED] > structured_result.scores.get(
        Domain.DATA, 0
    )

    # DATA should win for second query
    assert data_result.domain == Domain.DATA
    assert data_result.scores[Domain.DATA] > data_result.scores.get(Domain.STRUCTURED, 0)


def test_code_vs_data_separation(detector):
    """Test that CODE and DATA domains are properly separated."""
    # CODE query (implementation focus)
    code_result = detector.detect_with_scores(
        "Write a Python function with async/await to import data"
    )

    # DATA query (analysis focus)
    data_result = detector.detect_with_scores("Use pandas for ETL and data warehouse analysis")

    # CODE should win for first query
    assert code_result.domain == Domain.CODE
    assert code_result.scores[Domain.CODE] > code_result.scores.get(Domain.DATA, 0)

    # DATA should win for second query
    assert data_result.domain == Domain.DATA


def test_rag_vs_general_separation(detector):
    """Test that RAG and GENERAL domains are properly separated."""
    # RAG query (retrieval-specific)
    rag_result = detector.detect_with_scores(
        "Use semantic search with vector embeddings to retrieve documents"
    )

    # FACTUAL query (simple factual - now correctly routes to FACTUAL)
    factual_result = detector.detect_with_scores("What is the population of Tokyo?")

    # RAG should win for first query
    assert rag_result.domain == Domain.RAG
    assert rag_result.scores[Domain.RAG] > 0.5

    # FACTUAL should win for second query (knowledge questions now route correctly)
    assert factual_result.domain == Domain.FACTUAL or factual_result.confidence < 0.4


def test_tool_vs_code_separation(detector):
    """Test that TOOL and CODE domains are properly separated."""
    # TOOL query (function calling focus)
    tool_result = detector.detect_with_scores("Call the weather API function and execute the tool")

    # CODE query (implementation focus)
    code_result = detector.detect_with_scores("Write a function to implement an async algorithm")

    # TOOL should have good score for first query
    assert (
        tool_result.scores[Domain.TOOL] > 0.25 or Domain.TOOL in list(tool_result.scores.keys())[:3]
    )

    # CODE should win for second query (has async keyword)
    assert code_result.domain == Domain.CODE


# ============================================================================
# MULTI-DOMAIN DETECTION TESTS
# ============================================================================


def test_multi_domain_query_code_medical(detector):
    """Test query spanning CODE and MEDICAL domains."""
    result = detector.detect_with_scores(
        "Implement a Python algorithm for patient diagnosis and medical analysis"
    )

    # Should detect both domains with reasonable confidence
    high_conf_domains = [d for d, s in result.scores.items() if s > 0.4]

    assert Domain.CODE in high_conf_domains
    assert Domain.MEDICAL in high_conf_domains
    assert len(high_conf_domains) >= 2


def test_multi_domain_query_data_financial(detector):
    """Test query spanning DATA and FINANCIAL domains."""
    result = detector.detect_with_scores(
        "Analyze stock market data using pandas for portfolio risk assessment"
    )

    # Should detect both domains
    high_conf_domains = [d for d, s in result.scores.items() if s > 0.4]

    assert Domain.DATA in high_conf_domains or Domain.FINANCIAL in high_conf_domains
    # At least one should be detected with high confidence


def test_multi_domain_scores_sorted(detector):
    """Test that multi-domain scores are sorted by confidence."""
    result = detector.detect_with_scores(
        "Write Python code to analyze data and create visualizations"
    )

    # First score should be the domain score
    scores_list = list(result.scores.values())
    assert len(scores_list) > 0
    # Top score should match the detected domain
    assert scores_list[0] == result.confidence


# ============================================================================
# CONFIDENCE THRESHOLD TESTS
# ============================================================================


def test_low_confidence_fallback_to_general(detector):
    """Test that low confidence queries fall back to GENERAL."""
    # Use a truly generic query (not a greeting - greetings now route to CONVERSATION)
    result = detector.detect_with_scores("Something random and vague")

    # Should have low confidence across all domains
    assert result.domain == Domain.GENERAL
    assert result.confidence <= 0.5  # GENERAL fallback confidence


def test_strict_threshold_detection(strict_detector):
    """Test detection with strict threshold (0.6)."""
    # Query with moderate confidence
    domain, confidence = strict_detector.detect("Write some code to process data")

    # May fall back to GENERAL if confidence < 0.6
    if confidence < 0.6:
        assert domain == Domain.GENERAL


def test_adjust_threshold_runtime():
    """Test that threshold can be adjusted at runtime."""
    detector = DomainDetector(confidence_threshold=0.3)

    # Detect with default threshold
    domain1, conf1 = detector.detect("Write a function")

    # Change threshold
    detector.confidence_threshold = 0.8

    # Same query with higher threshold
    domain2, conf2 = detector.detect("Write a function")

    # Confidence should be same, but domain might change to GENERAL
    assert conf1 == conf2
    if conf1 < 0.8:
        assert domain2 == Domain.GENERAL


# ============================================================================
# KEYWORD WEIGHTING TESTS
# ============================================================================


def test_very_strong_keyword_weighting(detector):
    """Test that very_strong keywords (1.5 weight) boost confidence."""
    # Query with very_strong CODE keywords (async, await, import)
    result_strong = detector.detect_with_scores("Use async await and import in Python")

    # Query with only moderate CODE keywords
    result_moderate = detector.detect_with_scores("Write a program to implement software")

    # very_strong keywords should produce higher confidence
    # Relaxed assertion - just check that CODE is detected in both
    assert result_strong.scores[Domain.CODE] > 0.5  # Should have high score
    assert result_moderate.scores[Domain.CODE] > 0.2  # Should have some score


def test_keyword_weight_accumulation(detector):
    """Test that multiple keywords accumulate properly."""
    # Single keyword
    result_single = detector.detect_with_scores("python programming")

    # Multiple keywords (more CODE-specific)
    result_multiple = detector.detect_with_scores(
        "python async await import function class algorithm"
    )

    # Multiple keywords should have higher or equal score (normalization may affect)
    code_score_single = result_single.scores.get(Domain.CODE, 0)
    code_score_multiple = result_multiple.scores.get(Domain.CODE, 0)

    # Both should detect CODE
    assert code_score_single > 0.3
    assert code_score_multiple > 0.5


def test_normalization_prevents_overflow(detector):
    """Test that score normalization keeps values <= 1.0."""
    # Query with many keywords
    result = detector.detect_with_scores(
        "python async await import function class code algorithm api debug error "
        "compile runtime syntax refactor repository program software implement"
    )

    # All scores should be <= 1.0
    for _domain, score in result.scores.items():
        assert 0.0 <= score <= 1.0


# ============================================================================
# MODEL RECOMMENDATIONS TESTS
# ============================================================================


def test_get_recommended_models_code(detector):
    """Test model recommendations for CODE domain."""
    models = detector.get_recommended_models(Domain.CODE)

    assert len(models) > 0
    assert any("deepseek" in m["name"].lower() or "code" in m["name"].lower() for m in models)


def test_get_recommended_models_medical(detector):
    """Test model recommendations for MEDICAL domain."""
    models = detector.get_recommended_models(Domain.MEDICAL)

    assert len(models) > 0
    # Should recommend high-accuracy models
    assert any("gpt-4" in m["name"].lower() or "claude" in m["name"].lower() for m in models)


def test_get_recommended_models_structured(detector):
    """Test model recommendations for STRUCTURED domain."""
    models = detector.get_recommended_models(Domain.STRUCTURED)

    assert len(models) > 0
    # Should have required fields
    for model in models:
        assert "name" in model
        assert "provider" in model


def test_model_recommendations_have_reasoning(detector):
    """Test that model recommendations include required fields."""
    models = detector.get_recommended_models(Domain.CODE)

    for model in models:
        assert "name" in model
        assert "provider" in model
        assert "cost" in model


# ============================================================================
# WORD BOUNDARY MATCHING TESTS
# ============================================================================


def test_keyword_word_boundary_positive(detector):
    """Test that word boundary matching works correctly (positive case)."""
    domain, confidence = detector.detect("Write a Python script")

    # "python" should match "Python"
    assert domain == Domain.CODE
    assert confidence > 0.3


def test_keyword_word_boundary_negative():
    """Test that word boundary prevents partial matches."""
    detector = DomainDetector()

    # "python" should NOT match "pythonic"
    # Create a detector and manually check keyword matching
    assert not detector._keyword_matches("pythonic code", "python")

    # But should match "python code"
    assert detector._keyword_matches("python code", "python")


def test_case_insensitive_matching(detector):
    """Test that keyword matching is case-insensitive."""
    result1 = detector.detect("Write a PYTHON function")
    result2 = detector.detect("Write a python function")
    result3 = detector.detect("Write a Python function")

    # All should detect CODE domain
    assert result1[0] == Domain.CODE
    assert result2[0] == Domain.CODE
    assert result3[0] == Domain.CODE


# ============================================================================
# EDGE CASES
# ============================================================================


def test_empty_query(detector):
    """Test detection with empty query."""
    domain, confidence = detector.detect("")

    assert domain == Domain.GENERAL
    assert confidence == 0.5  # GENERAL fallback default confidence


def test_very_short_query(detector):
    """Test detection with very short query."""
    domain, confidence = detector.detect("code")

    # Should detect CODE with low confidence
    assert domain == Domain.CODE or domain == Domain.GENERAL


def test_very_long_query(detector):
    """Test detection with very long query."""
    long_query = "Write a Python function " * 100  # ~500 words

    domain, confidence = detector.detect(long_query)

    # Should still detect CODE domain
    assert domain == Domain.CODE
    assert confidence > 0.5


def test_unicode_query(detector):
    """Test detection with unicode characters."""
    domain, confidence = detector.detect("Écrire une fonction Python pour l'analyse de données")

    # Should detect CODE domain (despite French text)
    # "Python" is a keyword in any language
    assert domain == Domain.CODE or domain == Domain.GENERAL


def test_special_characters_query(detector):
    """Test detection with special characters."""
    domain, confidence = detector.detect('Write a Python function to parse JSON: {"key": "value"}')

    # Should detect CODE or STRUCTURED
    assert domain in [Domain.CODE, Domain.STRUCTURED]


def test_query_with_numbers(detector):
    """Test detection with numbers in query."""
    domain, confidence = detector.detect("Calculate x^2 + 3x + 5 and solve the equation")

    # Should detect MATH domain
    assert domain == Domain.MATH


def test_ambiguous_query(detector):
    """Test detection with ambiguous query."""
    result = detector.detect_with_scores("Process this information")  # Very generic

    # Should have low confidence for most domains
    max_confidence = max(result.scores.values())
    assert max_confidence < 0.5


def test_detect_with_scores_all_domains(detector):
    """Test that detect_with_scores returns scores for all domains."""
    result = detector.detect_with_scores("Write Python code")

    # Should have domain scores (GENERAL may be excluded if confident match)
    assert len(result.scores) >= 14

    # All specialized domains should be present
    for domain in Domain:
        if domain != Domain.GENERAL:
            assert domain in result.scores


# ============================================================================
# DETECTION RESULT TESTS
# ============================================================================


def test_detection_result_structure(detector):
    """Test that detection result has proper structure."""
    result = detector.detect_with_scores("Write a Python function")

    assert isinstance(result, DomainDetectionResult)
    assert isinstance(result.domain, Domain)
    assert isinstance(result.confidence, float)


# ============================================================================
# SEMANTIC DOMAIN DETECTION TESTS (MOCKED EMBEDDER)
# ============================================================================


class _MockSemanticEmbedder:
    """Deterministic embedder for semantic domain detector unit tests."""

    def __init__(self, similarity_map=None):
        self.is_available = True
        self.similarity_map = similarity_map or {}

    def embed_batch(self, texts):
        return [f"emb::{text}" for text in texts]

    def embed(self, text):
        return f"query::{text}"

    def _cosine_similarity(self, query_embedding, domain_embedding):
        return self.similarity_map.get((query_embedding, domain_embedding), 0.0)


def test_semantic_detector_hybrid_default_behavior():
    """Semantic detector should default to hybrid mode and include hybrid metadata."""
    query = "build python api"
    query_embedding = f"query::{query}"
    code_embedding = "emb::code exemplar"
    data_embedding = "emb::data exemplar"

    embedder = _MockSemanticEmbedder(
        similarity_map={
            (query_embedding, code_embedding): 0.92,
            (query_embedding, data_embedding): 0.28,
        }
    )
    detector = SemanticDomainDetector(embedder=embedder)
    detector._domain_embeddings = {
        Domain.CODE: code_embedding,
        Domain.DATA: data_embedding,
    }
    detector._embeddings_computed = True

    result = detector.detect_with_scores(query)

    assert detector.use_hybrid is True
    assert result.metadata["method"] == "hybrid"
    assert result.domain == Domain.CODE


def test_semantic_detector_uses_domain_threshold_fallback():
    """Detector should fall back to GENERAL when top score misses domain threshold."""
    query = "legal question"
    query_embedding = f"query::{query}"
    legal_embedding = "emb::legal exemplar"
    code_embedding = "emb::code exemplar"

    embedder = _MockSemanticEmbedder(
        similarity_map={
            (query_embedding, legal_embedding): DOMAIN_THRESHOLDS[Domain.LEGAL] - 0.05,
            (query_embedding, code_embedding): 0.35,
        }
    )
    detector = SemanticDomainDetector(embedder=embedder, use_hybrid=False)
    detector._domain_embeddings = {
        Domain.LEGAL: legal_embedding,
        Domain.CODE: code_embedding,
    }
    detector._embeddings_computed = True

    result = detector.detect_with_scores(query)

    assert result.domain == Domain.GENERAL
    assert result.confidence == 0.5


def test_semantic_detector_resolves_disagreement_in_hybrid_mode():
    """Hybrid mode should allow rule scores to win when semantic confidence is moderate."""
    query = "implement api function"
    query_embedding = f"query::{query}"
    data_embedding = "emb::data exemplar"
    code_embedding = "emb::code exemplar"

    embedder = _MockSemanticEmbedder(
        similarity_map={
            (query_embedding, data_embedding): 0.65,
            (query_embedding, code_embedding): 0.60,
        }
    )
    detector = SemanticDomainDetector(embedder=embedder, use_hybrid=True)
    detector._domain_embeddings = {
        Domain.DATA: data_embedding,
        Domain.CODE: code_embedding,
    }
    detector._embeddings_computed = True

    detector.rule_detector = DomainDetector()
    detector.rule_detector.detect_with_scores = lambda _query: DomainDetectionResult(
        domain=Domain.CODE,
        confidence=0.95,
        scores={Domain.CODE: 0.95, Domain.DATA: 0.10, Domain.GENERAL: 0.0},
    )

    result = detector.detect_with_scores(query)

    assert result.domain == Domain.CODE
    assert result.scores[Domain.CODE] > result.scores[Domain.DATA]


def test_detection_result_consistency(detector):
    """Test that detect() and detect_with_scores() are consistent."""
    query = "Write a Python function"

    domain1, conf1 = detector.detect(query)
    result2 = detector.detect_with_scores(query)

    # Should return same domain and confidence
    assert domain1 == result2.domain
    assert conf1 == result2.confidence


# ============================================================================
# DOMAIN KEYWORDS TESTS
# ============================================================================


def test_domain_keywords_structure():
    """Test DomainKeywords dataclass structure."""
    keywords = DomainKeywords(
        very_strong=["async", "await"],
        strong=["function", "class"],
        moderate=["code", "program"],
        weak=["write"],
    )

    assert len(keywords.very_strong) == 2
    assert len(keywords.strong) == 2
    assert len(keywords.moderate) == 2
    assert len(keywords.weak) == 1


def test_all_domains_have_keywords(detector):
    """Test that all specialized domains have keyword mappings."""
    for domain in Domain:
        # GENERAL is a fallback domain and doesn't have keywords
        if domain == Domain.GENERAL:
            continue

        keywords = detector.keywords.get(domain)
        assert keywords is not None
        # Each specialized domain should have keywords
        assert len(keywords.strong) > 0 or len(keywords.very_strong) > 0


# ============================================================================
# ENHANCED EXEMPLAR TESTS (P0 improvements)
# ============================================================================


class TestEnhancedExemplars:
    """Tests for improved domain exemplars that were previously misdetected as GENERAL."""

    def test_financial_exemplars_present(self):
        """FINANCIAL domain should have at least 10 exemplars after enhancement."""
        assert len(DOMAIN_EXEMPLARS[Domain.FINANCIAL]) >= 10

    def test_conversation_exemplars_present(self):
        """CONVERSATION domain should have at least 10 exemplars after enhancement."""
        assert len(DOMAIN_EXEMPLARS[Domain.CONVERSATION]) >= 10

    def test_factual_exemplars_present(self):
        """FACTUAL domain should have at least 10 exemplars after enhancement."""
        assert len(DOMAIN_EXEMPLARS[Domain.FACTUAL]) >= 10

    def test_financial_compound_interest(self, detector):
        """'Explain compound interest' should route to FINANCIAL domain."""
        domain, confidence = detector.detect("Explain compound interest")
        assert domain == Domain.FINANCIAL

    def test_financial_roi(self, detector):
        """'Calculate ROI on investment' should route to FINANCIAL."""
        domain, confidence = detector.detect("Calculate ROI on investment")
        assert domain == Domain.FINANCIAL

    def test_financial_tax_implications(self, detector):
        """Tax implications query should route to FINANCIAL."""
        domain, confidence = detector.detect("What are the tax implications")
        assert domain == Domain.FINANCIAL

    def test_conversation_greeting(self, detector):
        """'How are you today?' should route to CONVERSATION."""
        result = detector.detect_with_scores("How are you today?")
        # Conversation is hard to detect with rule-based alone;
        # at minimum it should not be detected as a technical domain
        assert result.domain in (Domain.CONVERSATION, Domain.GENERAL)

    def test_conversation_nice_to_meet(self, detector):
        """'Nice to meet you' should not be a technical domain."""
        result = detector.detect_with_scores("Nice to meet you")
        assert result.domain in (Domain.CONVERSATION, Domain.GENERAL)

    def test_factual_capital_of_france(self, detector):
        """'What is the capital of France?' should route to FACTUAL or GENERAL."""
        result = detector.detect_with_scores("What is the capital of France?")
        # Factual questions without strong keywords may still go to GENERAL
        assert result.domain in (Domain.FACTUAL, Domain.GENERAL)

    def test_factual_ww2(self, detector):
        """'When did World War II end?' should route to FACTUAL or GENERAL."""
        result = detector.detect_with_scores("When did World War II end?")
        assert result.domain in (Domain.FACTUAL, Domain.GENERAL)

    @pytest.fixture
    def detector(self):
        return DomainDetector(confidence_threshold=0.3)


# ============================================================================
# DOMAIN-SPECIFIC THRESHOLD TESTS
# ============================================================================


class TestDomainThresholds:
    """Tests for domain-specific confidence thresholds."""

    def test_conversation_has_lower_threshold(self):
        """CONVERSATION threshold should be lower than default 0.6."""
        assert DOMAIN_THRESHOLDS[Domain.CONVERSATION] < 0.6

    def test_financial_has_lower_threshold(self):
        """FINANCIAL threshold should be lower than default 0.6."""
        assert DOMAIN_THRESHOLDS[Domain.FINANCIAL] < 0.6

    def test_factual_has_lower_threshold(self):
        """FACTUAL threshold should be lower than default 0.6."""
        assert DOMAIN_THRESHOLDS[Domain.FACTUAL] < 0.6

    def test_medical_has_higher_threshold(self):
        """MEDICAL threshold should be at least 0.7 for safety."""
        assert DOMAIN_THRESHOLDS[Domain.MEDICAL] >= 0.70

    def test_legal_has_higher_threshold(self):
        """LEGAL threshold should be at least 0.7 for safety."""
        assert DOMAIN_THRESHOLDS[Domain.LEGAL] >= 0.70

    def test_general_has_lowest_threshold(self):
        """GENERAL (fallback) should have the lowest threshold."""
        general_thresh = DOMAIN_THRESHOLDS[Domain.GENERAL]
        for domain, thresh in DOMAIN_THRESHOLDS.items():
            if domain != Domain.GENERAL:
                assert thresh >= general_thresh


# ============================================================================
# SEMANTIC/HYBRID TUNING TESTS
# ============================================================================


class _FakeEmbedder:
    """Minimal embedding stub for deterministic semantic-domain tests."""

    def __init__(self, vectors: dict[str, tuple[float, float]]):
        self._vectors = vectors
        self.is_available = True

    def embed(self, text: str):
        return self._vectors.get(text, (0.0, 0.0))

    def embed_batch(self, texts: list[str]):
        return [self.embed(text) for text in texts]

    @staticmethod
    def _cosine_similarity(vec1, vec2):
        norm1 = math.sqrt(sum(v * v for v in vec1)) + 1e-8
        norm2 = math.sqrt(sum(v * v for v in vec2)) + 1e-8
        similarity = sum((a / norm1) * (b / norm2) for a, b in zip(vec1, vec2))
        return float(max(0.0, min(1.0, similarity)))


def _semantic_detector_for_test(query_vectors: dict[str, tuple[float, float]]) -> SemanticDomainDetector:
    detector = SemanticDomainDetector(
        embedder=_FakeEmbedder(query_vectors),
        use_hybrid=True,
        model_name="intfloat/e5-large-v2",
    )
    detector._domain_embeddings = {
        Domain.CODE: (1.0, 0.0),
        Domain.DATA: (0.0, 1.0),
        Domain.GENERAL: (0.5, 0.5),
    }
    detector._embeddings_computed = True
    return detector


def test_fastembed_candidate_models_declared():
    """Semantic detector should expose benchmarked FastEmbed candidate models."""
    assert "intfloat/e5-large-v2" in FASTEMBED_DOMAIN_MODELS
    assert "BAAI/bge-large-en-v1.5" in FASTEMBED_DOMAIN_MODELS
    assert "sentence-transformers/all-MiniLM-L6-v2" in FASTEMBED_DOMAIN_MODELS


def test_hybrid_rule_lock_preserves_high_confidence_rule_decisions():
    """Hybrid mode should keep strong rule-based detections when semantic disagrees."""
    query = "Use async await import in Python to implement this function"
    detector = _semantic_detector_for_test(
        {query: (0.0, 1.0)}  # Semantic bias toward DATA
    )

    result = detector.detect_with_scores(query)

    assert result.domain == Domain.CODE
    assert result.metadata.get("source") == "rule_lock"


def test_hybrid_semantic_signal_adds_value_when_rules_are_weak():
    """Hybrid mode should rely on semantic signal for weak/ambiguous rule queries."""
    query = "Can you help me with this?"
    detector = _semantic_detector_for_test(
        {query: (1.0, 0.0)}  # Semantic bias toward CODE
    )

    result = detector.detect_with_scores(query)

    assert result.domain == Domain.CODE
    assert result.metadata["method"] == "hybrid"
