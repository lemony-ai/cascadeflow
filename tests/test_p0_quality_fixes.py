"""Tests for P0 quality improvement fixes.

Covers:
1. Enhanced complexity detection via COMPLEXITY_SIGNALS
2. Trivial-mode bypass removal in QualityValidator
3. Forced escalation in cascade for hard/expert queries
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cascadeflow.quality.complexity import ComplexityDetector, QueryComplexity
from cascadeflow.quality.quality import QualityConfig, QualityValidator


# ============================================================================
# 1. COMPLEXITY SIGNAL DETECTION
# ============================================================================


class TestComplexitySignals:
    """Test the new COMPLEXITY_SIGNALS-based boosting."""

    def setup_method(self):
        self.detector = ComplexityDetector()

    # -- proof_required signals --

    def test_prove_sqrt2_irrational(self):
        """'Prove sqrt(2) is irrational' must be HARD or EXPERT."""
        complexity, confidence = self.detector.detect("Prove sqrt(2) is irrational")
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)
        assert confidence >= 0.80

    def test_prove_by_contradiction(self):
        complexity, _ = self.detector.detect(
            "Prove by contradiction that there are infinitely many primes"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    def test_derive_equation(self):
        complexity, _ = self.detector.detect(
            "Derive the Euler-Lagrange equation from the principle of least action"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    def test_show_that(self):
        complexity, _ = self.detector.detect(
            "Show that every bounded monotonic sequence converges"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    # -- mathematical signals --

    def test_irrational_proof(self):
        complexity, _ = self.detector.detect(
            "Prove that the square root of 3 is irrational"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    def test_convergence_divergence(self):
        complexity, _ = self.detector.detect(
            "Determine whether the series converges or diverges"
        )
        assert complexity in (
            QueryComplexity.MODERATE,
            QueryComplexity.HARD,
            QueryComplexity.EXPERT,
        )

    # -- implementation signals --

    def test_from_scratch(self):
        complexity, _ = self.detector.detect(
            "Build a neural network from scratch in Python"
        )
        # "from scratch" alone (implementation signal) boosts to at least MODERATE;
        # combined with expert keywords like "neural network" it may reach HARD+
        assert complexity in (
            QueryComplexity.MODERATE,
            QueryComplexity.HARD,
            QueryComplexity.EXPERT,
        )

    def test_production_ready(self):
        complexity, _ = self.detector.detect(
            "Write a production-ready REST API with authentication"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    def test_thread_safe(self):
        complexity, _ = self.detector.detect(
            "Implement a thread-safe queue in C++"
        )
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

    # -- combined signals → EXPERT --

    def test_proof_plus_mathematical_is_expert(self):
        """Two signal categories should push to EXPERT."""
        complexity, confidence = self.detector.detect(
            "Prove that sqrt(2) is irrational using a proof by contradiction"
        )
        assert complexity == QueryComplexity.EXPERT
        assert confidence >= 0.85

    def test_derive_plus_implementation(self):
        complexity, _ = self.detector.detect(
            "Derive and implement from scratch a lock-free concurrent hash table"
        )
        assert complexity == QueryComplexity.EXPERT

    # -- metadata includes signals --

    def test_signals_in_metadata(self):
        _, _, metadata = self.detector.detect(
            "Prove sqrt(2) is irrational", return_metadata=True
        )
        assert "complexity_signals" in metadata
        assert "proof_required" in metadata["complexity_signals"]
        assert "signal_boost" in metadata
        assert metadata["signal_boost"] >= 2.0

    # -- trivial queries still stay trivial --

    def test_trivial_unaffected(self):
        complexity, _ = self.detector.detect("What is 2+2?")
        assert complexity == QueryComplexity.TRIVIAL

    def test_simple_unaffected(self):
        complexity, _ = self.detector.detect("What is machine learning?")
        assert complexity == QueryComplexity.SIMPLE


# ============================================================================
# 2. TRIVIAL-MODE BYPASS REMOVAL
# ============================================================================


class TestTrivialBypassRemoval:
    """Validate that trivial complexity no longer auto-passes all checks."""

    def setup_method(self):
        self.validator = QualityValidator(config=QualityConfig.for_cascade())

    def test_trivial_good_response_passes(self):
        """A correct trivial answer still passes."""
        result = self.validator.validate(
            draft_content="Paris",
            query="What is the capital of France?",
            confidence=0.90,
            complexity="trivial",
        )
        assert result.passed is True

    def test_trivial_hedging_response_fails(self):
        """A trivial answer full of severe uncertainty markers should fail."""
        result = self.validator.validate(
            draft_content="I don't know, I'm not sure, I cannot provide this information. "
            "I apologize but I'm uncertain about this.",
            query="What is 2+2?",
            confidence=0.90,
            complexity="trivial",
        )
        # Should fail the acceptable_hedging check due to severe markers
        assert result.checks.get("acceptable_hedging") is False

    def test_trivial_hallucination_detected(self):
        """Hallucination detection still runs for trivial queries."""
        result = self.validator.validate(
            draft_content=(
                "According to studies show that 2+2 equals 5. "
                "It is well-known that all math is relative. "
                "Scientists confirm prove this is always true."
            ),
            query="What is 2+2?",
            confidence=0.90,
            complexity="trivial",
        )
        # Should detect hallucination risk
        assert result.checks.get("low_hallucination_risk") is False

    def test_trivial_still_checks_confidence(self):
        """Confidence check still applies to trivial queries."""
        result = self.validator.validate(
            draft_content="4",
            query="What is 2+2?",
            confidence=0.01,
            complexity="trivial",
        )
        assert result.checks.get("confidence") is False

    def test_trivial_mode_flag_still_set(self):
        """The trivial_mode detail flag is still set for tracking."""
        result = self.validator.validate(
            draft_content="4",
            query="What is 2+2?",
            confidence=0.90,
            complexity="trivial",
        )
        assert result.details.get("trivial_mode") is True


# ============================================================================
# 3. FORCED ESCALATION IN CASCADE
# ============================================================================


class TestForcedEscalation:
    """Test that expert queries always escalate and hard queries escalate
    unless quality_score >= 0.85."""

    def _make_cascade(self):
        """Create a WholeResponseCascade with mock providers."""
        from cascadeflow.core.cascade import WholeResponseCascade
        from cascadeflow.schema.config import ModelConfig

        drafter = ModelConfig(
            name="mock-drafter",
            provider="custom",
            cost=0.001,
            speed_ms=100,
        )
        verifier = ModelConfig(
            name="mock-verifier",
            provider="custom",
            cost=0.01,
            speed_ms=500,
        )

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(
            return_value={
                "content": "Mock response",
                "confidence": 0.95,
                "tokens_used": 50,
                "logprobs": None,
                "tool_calls": None,
            }
        )
        providers = {"custom": mock_provider}

        cascade = WholeResponseCascade(
            drafter=drafter,
            verifier=verifier,
            providers=providers,
            quality_config=QualityConfig.for_cascade(),
        )
        return cascade

    def test_expert_always_rejected(self):
        """Expert complexity should always force escalation (reject draft)."""
        cascade = self._make_cascade()
        # Call _should_accept_draft with expert complexity
        draft_result = {
            "content": "A comprehensive proof using mathematical induction...",
            "confidence": 0.99,
        }
        passed, validation_result, complexity = cascade._should_accept_draft(
            draft_result,
            query="Prove Gödel's incompleteness theorem",
            complexity_hint="expert",
        )
        assert passed is False
        reason = getattr(validation_result, "reason", "")
        assert "forced_escalation_expert" in reason

    def test_hard_rejected_when_low_quality(self):
        """Hard complexity with quality < 0.85 should force escalation."""
        cascade = self._make_cascade()
        draft_result = {
            "content": "The analysis shows several important factors...",
            "confidence": 0.80,
        }
        passed, validation_result, complexity = cascade._should_accept_draft(
            draft_result,
            query="Analyze the implications of quantum computing on cryptography",
            complexity_hint="hard",
        )
        assert passed is False
        reason = getattr(validation_result, "reason", "")
        assert "forced_escalation_hard" in reason

    def test_simple_not_force_escalated(self):
        """Simple complexity should not be force-escalated."""
        cascade = self._make_cascade()
        draft_result = {
            "content": "Machine learning is a subset of AI that allows systems to learn from data.",
            "confidence": 0.90,
        }
        passed, validation_result, complexity = cascade._should_accept_draft(
            draft_result,
            query="What is machine learning?",
            complexity_hint="simple",
        )
        # Should pass (not force-escalated) as it's simple with good confidence
        assert passed is True

    def test_moderate_not_force_escalated(self):
        """Moderate complexity should not be force-escalated."""
        cascade = self._make_cascade()
        draft_result = {
            "content": (
                "REST uses resources and HTTP methods while GraphQL uses a single endpoint "
                "with a query language. REST is simpler for basic CRUD operations, "
                "while GraphQL is better for complex nested data requirements."
            ),
            "confidence": 0.85,
        }
        passed, validation_result, complexity = cascade._should_accept_draft(
            draft_result,
            query="Compare REST and GraphQL",
            complexity_hint="moderate",
        )
        # Should pass - moderate is not force-escalated
        assert passed is True


# ============================================================================
# 4. END-TO-END: Complexity → Quality → Escalation
# ============================================================================


class TestEndToEndQualityFlow:
    """Test the full flow: complexity detection → quality validation → escalation."""

    def test_proof_query_detected_and_escalated(self):
        """A proof query should be detected as hard+ and forced to escalate."""
        detector = ComplexityDetector()
        complexity, confidence = detector.detect("Prove sqrt(2) is irrational")

        # Complexity detection should classify this as HARD or EXPERT
        assert complexity in (QueryComplexity.HARD, QueryComplexity.EXPERT)

        # Validator with this complexity should still validate properly
        validator = QualityValidator(config=QualityConfig.for_cascade())
        result = validator.validate(
            draft_content="sqrt(2) is irrational because it can't be expressed as a fraction.",
            query="Prove sqrt(2) is irrational",
            confidence=0.75,
            complexity=complexity.value,
        )
        # The response is shallow for a proof - quality score should reflect that
        assert result.score < 1.0

    def test_trivial_query_still_works(self):
        """Trivial queries should still be classified and validated correctly."""
        detector = ComplexityDetector()
        complexity, _ = detector.detect("What is 2+2?")
        assert complexity == QueryComplexity.TRIVIAL

        validator = QualityValidator(config=QualityConfig.for_cascade())
        result = validator.validate(
            draft_content="4",
            query="What is 2+2?",
            confidence=0.95,
            complexity=complexity.value,
        )
        assert result.passed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
