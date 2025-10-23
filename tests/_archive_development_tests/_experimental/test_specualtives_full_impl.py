"""
Test suite for Token-Level Speculative Cascades.

Tests all 4 deferral strategies and validates paper compliance.
"""

import math
from typing import Any

import pytest
from cascadeflow.config import ModelConfig
from cascadeflow.speculative import (
    DeferralStrategy,
    FlexibleDeferralRule,
    ProviderCapabilities,
    TokenLevelSpeculativeCascade,
    TokenPrediction,
)


# Mock Provider for Testing
class MockProvider:
    """Mock provider that returns predictable logprobs."""

    def __init__(self, name: str, quality: str = "good"):
        self.name = name
        self.quality = quality

    async def complete(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.7,
        logprobs: bool = False,
        top_logprobs: int = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Return mock completion with logprobs."""

        if self.quality == "good":
            tokens = ["The", " answer", " is", " correct", "."]
            logprobs_list = [math.log(0.9)] * len(tokens)
            confidence = 0.9

            if top_logprobs:
                # Return top-k predictions
                top_logprobs_data = [
                    {"The": math.log(0.9), "A": math.log(0.05), "An": math.log(0.03)}
                ]
            else:
                top_logprobs_data = []

        elif self.quality == "poor":
            tokens = ["Maybe", " possibly", " perhaps", " maybe", "?"]
            logprobs_list = [math.log(0.4)] * len(tokens)
            confidence = 0.4
            top_logprobs_data = []

        else:  # medium
            tokens = ["The", " solution", " could", " be", " this", "."]
            logprobs_list = [math.log(0.7)] * len(tokens)
            confidence = 0.7
            top_logprobs_data = []

        # Limit to max_tokens
        tokens = tokens[:max_tokens]
        logprobs_list = logprobs_list[:max_tokens]

        return {
            "content": "".join(tokens),
            "tokens": tokens,
            "logprobs": logprobs_list if logprobs else [],
            "confidence": confidence,
            "top_logprobs": top_logprobs_data,
        }


class TestFlexibleDeferralRule:
    """Test deferral strategies."""

    def test_confidence_threshold_strategy(self):
        """Test CONFIDENCE_THRESHOLD strategy."""
        rule = FlexibleDeferralRule(
            strategy=DeferralStrategy.CONFIDENCE_THRESHOLD, confidence_threshold=0.7
        )

        verifier_preds = [
            TokenPrediction("answer", math.log(0.9), 0.9),
            TokenPrediction("solution", math.log(0.05), 0.05),
        ]

        # High confidence draft: should accept
        defer, reason = rule.should_defer_token(
            draft_token="answer",
            draft_logprob=math.log(0.85),
            verifier_top_k=verifier_preds,
            position=0,
        )
        assert not defer, "Should accept high confidence draft"

        # Low confidence draft: should defer
        defer, reason = rule.should_defer_token(
            draft_token="maybe",
            draft_logprob=math.log(0.5),
            verifier_top_k=verifier_preds,
            position=1,
        )
        assert defer, "Should defer low confidence draft"

    def test_comparative_strategy(self):
        """Test COMPARATIVE strategy."""
        rule = FlexibleDeferralRule(strategy=DeferralStrategy.COMPARATIVE, comparative_delta=0.15)

        # Verifier much better: should defer
        verifier_preds = [
            TokenPrediction("correct", math.log(0.95), 0.95),
            TokenPrediction("answer", math.log(0.03), 0.03),
        ]

        defer, reason = rule.should_defer_token(
            draft_token="answer",
            draft_logprob=math.log(0.7),  # Gap = 0.95 - 0.7 = 0.25
            verifier_top_k=verifier_preds,
            position=0,
        )
        assert defer, "Should defer when verifier significantly better"

        # Similar confidence: should accept
        verifier_preds = [
            TokenPrediction("answer", math.log(0.75), 0.75),
            TokenPrediction("solution", math.log(0.2), 0.2),
        ]

        defer, reason = rule.should_defer_token(
            draft_token="answer",
            draft_logprob=math.log(0.7),  # Gap = 0.75 - 0.7 = 0.05
            verifier_top_k=verifier_preds,
            position=0,
        )
        assert not defer, "Should accept when confidence similar"

    def test_token_list_strategy(self):
        """Test TOKEN_LIST strategy (most powerful from paper)."""
        rule = FlexibleDeferralRule(
            strategy=DeferralStrategy.TOKEN_LIST, top_k=5, min_probability=0.01
        )

        verifier_preds = [
            TokenPrediction("answer", math.log(0.5), 0.5),
            TokenPrediction("solution", math.log(0.3), 0.3),
            TokenPrediction("response", math.log(0.1), 0.1),
            TokenPrediction("reply", math.log(0.05), 0.05),
            TokenPrediction("output", math.log(0.03), 0.03),
            TokenPrediction("result", math.log(0.01), 0.01),
        ]

        # Draft in top-5: should accept
        defer, reason = rule.should_defer_token(
            draft_token="solution",  # 2nd in list
            draft_logprob=math.log(0.6),
            verifier_top_k=verifier_preds,
            position=0,
        )
        assert not defer, "Should accept token in top-k"

        # Draft not in top-5: should defer
        defer, reason = rule.should_defer_token(
            draft_token="result",  # 6th in list
            draft_logprob=math.log(0.6),
            verifier_top_k=verifier_preds,
            position=0,
        )
        assert defer, "Should defer token not in top-k"

    def test_cost_benefit_strategy(self):
        """Test COST_BENEFIT strategy."""
        rule = FlexibleDeferralRule(
            strategy=DeferralStrategy.COST_BENEFIT, cost_benefit_threshold=0.5
        )

        # High quality gain, low rejection cost: should defer
        verifier_preds = [
            TokenPrediction("excellent", math.log(0.95), 0.95),
            TokenPrediction("good", math.log(0.4), 0.4),
        ]

        defer, reason = rule.should_defer_token(
            draft_token="good",
            draft_logprob=math.log(0.4),  # Low confidence = low cost to reject
            verifier_top_k=verifier_preds,
            position=0,
        )
        # quality_gain = 0.95 - 0.4 = 0.55
        # rejection_cost = 0.4
        # benefit_ratio = 0.55 / 0.4 = 1.375 >= 0.5
        assert defer, "Should defer when benefit ratio high"

        # Low quality gain, high rejection cost: should accept
        verifier_preds = [
            TokenPrediction("answer", math.log(0.88), 0.88),
            TokenPrediction("solution", math.log(0.1), 0.1),
        ]

        defer, reason = rule.should_defer_token(
            draft_token="answer",
            draft_logprob=math.log(0.85),  # High confidence = high cost to reject
            verifier_top_k=verifier_preds,
            position=0,
        )
        # quality_gain = 0.88 - 0.85 = 0.03
        # rejection_cost = 0.85
        # benefit_ratio = 0.03 / 0.85 = 0.035 < 0.5
        assert not defer, "Should accept when benefit ratio low"


class TestTokenLevelSpeculativeCascade:
    """Test token-level cascade execution."""

    @pytest.fixture
    def mock_providers(self):
        """Create mock providers."""
        return {
            "openai": MockProvider("openai", quality="good"),
            "anthropic": MockProvider("anthropic", quality="good"),
        }

    @pytest.fixture
    def drafter_config(self):
        """Small/fast drafter model."""
        return ModelConfig(
            name="gpt-3.5-turbo", provider="openai", cost=0.0005, speed_ms=50, quality_score=0.7
        )

    @pytest.fixture
    def verifier_config(self):
        """Large/slow verifier model."""
        return ModelConfig(
            name="gpt-4", provider="openai", cost=0.03, speed_ms=500, quality_score=0.95
        )

    @pytest.mark.asyncio
    async def test_basic_execution(self, mock_providers, drafter_config, verifier_config):
        """Test basic cascade execution."""
        cascade = TokenLevelSpeculativeCascade(
            drafter=drafter_config, verifier=verifier_config, providers=mock_providers, chunk_size=5
        )

        result = await cascade.execute(query="What is 2+2?", max_tokens=20)

        assert result.content != ""
        assert result.tokens_drafted > 0
        assert result.acceptance_rate >= 0
        assert result.speedup > 0
        assert result.chunks_processed > 0

    @pytest.mark.asyncio
    async def test_token_list_strategy(self, mock_providers, drafter_config, verifier_config):
        """Test TOKEN_LIST strategy accepts good tokens."""
        rule = FlexibleDeferralRule(strategy=DeferralStrategy.TOKEN_LIST, top_k=10)

        cascade = TokenLevelSpeculativeCascade(
            drafter=drafter_config,
            verifier=verifier_config,
            providers=mock_providers,
            deferral_rule=rule,
            chunk_size=5,
        )

        result = await cascade.execute(query="Explain photosynthesis", max_tokens=15)

        # Should have some accepted tokens
        assert result.tokens_accepted > 0, "TOKEN_LIST should accept some tokens"

        # Acceptance rate should be reasonable
        assert 0 <= result.acceptance_rate <= 1.0

    @pytest.mark.asyncio
    async def test_chunked_processing(self, mock_providers, drafter_config, verifier_config):
        """Test chunked processing iterates correctly."""
        cascade = TokenLevelSpeculativeCascade(
            drafter=drafter_config,
            verifier=verifier_config,
            providers=mock_providers,
            chunk_size=5,
            verbose=True,
        )

        result = await cascade.execute(query="Write a short story", max_tokens=25)

        # Should process multiple chunks
        assert result.chunks_processed >= 1

        # Should generate requested tokens
        assert result.tokens_verified > 0

    @pytest.mark.asyncio
    async def test_deferral_continues_with_verifier(
        self, mock_providers, drafter_config, verifier_config
    ):
        """Test that deferral continues with verifier."""
        # Use low confidence threshold to force deferral
        rule = FlexibleDeferralRule(
            strategy=DeferralStrategy.CONFIDENCE_THRESHOLD,
            confidence_threshold=0.95,  # Very high threshold
        )

        cascade = TokenLevelSpeculativeCascade(
            drafter=drafter_config,
            verifier=verifier_config,
            providers=mock_providers,
            deferral_rule=rule,
            chunk_size=3,
        )

        result = await cascade.execute(query="Test query", max_tokens=15)

        # Should have deferred some tokens
        assert result.tokens_deferred > 0, "Should defer with high threshold"

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, mock_providers, drafter_config, verifier_config):
        """Test statistics are tracked correctly."""
        cascade = TokenLevelSpeculativeCascade(
            drafter=drafter_config, verifier=verifier_config, providers=mock_providers
        )

        # Run multiple executions
        for _ in range(3):
            await cascade.execute(query="Test", max_tokens=10)

        stats = cascade.get_stats()

        assert stats["total_executions"] == 3
        assert stats["tokens_drafted"] > 0
        assert stats["tokens_accepted"] >= 0
        assert stats["chunks_processed"] > 0
        assert "avg_acceptance_rate" in stats
        assert "avg_speedup" in stats


class TestProviderCapabilities:
    """Test provider capability detection."""

    def test_logprobs_support_detection(self):
        """Test logprobs support detection."""
        assert ProviderCapabilities.supports_logprobs("openai")
        assert ProviderCapabilities.supports_logprobs("anthropic")
        assert ProviderCapabilities.supports_logprobs("groq")
        assert not ProviderCapabilities.supports_logprobs("ollama")
        assert not ProviderCapabilities.supports_logprobs("replicate")

    def test_fallback_strategy_selection(self):
        """Test automatic strategy selection."""
        # Both support logprobs: use TOKEN_LIST
        strategy = ProviderCapabilities.get_fallback_strategy("openai", "anthropic")
        assert strategy == DeferralStrategy.TOKEN_LIST

        # Only verifier supports: use COMPARATIVE
        strategy = ProviderCapabilities.get_fallback_strategy("ollama", "openai")
        assert strategy == DeferralStrategy.COMPARATIVE

        # Neither supports: use CONFIDENCE_THRESHOLD
        strategy = ProviderCapabilities.get_fallback_strategy("ollama", "replicate")
        assert strategy == DeferralStrategy.CONFIDENCE_THRESHOLD


@pytest.mark.benchmark
class TestBenchmarks:
    """Benchmark tests matching Google's experiments."""

    @pytest.mark.asyncio
    async def test_gsm8k_math_problem(self):
        """
        Test on GSM8K-style math problem.

        From paper: "Mary has 30 sheep. She gets 1 kg of milk from
        half of them and 2 kg of milk from the other half every day.
        How much milk does she collect every day?"
        """
        # This would need real models to test properly
        # Placeholder for benchmark structure
        pass

    @pytest.mark.asyncio
    async def test_speedup_vs_baseline(self):
        """
        Test speedup vs. baseline.

        Expected from paper: 2-3x speedup
        """
        # Benchmark structure
        pass

    @pytest.mark.asyncio
    async def test_quality_preservation(self):
        """
        Test quality is preserved.

        Expected: Equal or better quality than pure large model
        """
        # Benchmark structure
        pass


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
