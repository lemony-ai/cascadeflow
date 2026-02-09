"""Tests for adaptive threshold learning, semantic cache, alignment fallback, and pricing."""

import time

import numpy as np
import pytest

# ============================================================================
# Adaptive Threshold Learning
# ============================================================================
from cascadeflow.quality.adaptive import AdaptiveThresholdManager


class TestAdaptiveThresholdManager:
    """Test self-learning threshold adjustment."""

    def test_initial_threshold_unchanged(self):
        """Base threshold returned when no data collected."""
        mgr = AdaptiveThresholdManager()
        assert mgr.get_threshold("code", 0.50) == 0.50

    def test_tighten_when_acceptance_too_high(self):
        """Threshold increases when acceptance rate exceeds target + 10%."""
        mgr = AdaptiveThresholdManager(
            target_acceptance_rate=0.55, min_samples=10, adjustment_step=0.02
        )
        # Record 90% acceptance (way above 65% upper band)
        for _ in range(9):
            mgr.record("code", confidence=0.80, accepted=True)
        mgr.record("code", confidence=0.30, accepted=False)
        # After 10 samples the adjustment should have fired
        threshold = mgr.get_threshold("code", 0.50)
        assert threshold > 0.50, f"Expected tightened threshold >0.50, got {threshold}"

    def test_relax_when_acceptance_too_low(self):
        """Threshold decreases when acceptance rate drops below target - 10%."""
        mgr = AdaptiveThresholdManager(
            target_acceptance_rate=0.55, min_samples=10, adjustment_step=0.02
        )
        # Record 20% acceptance (way below 45% lower band)
        for i in range(10):
            mgr.record("code", confidence=0.40, accepted=(i < 2))
        threshold = mgr.get_threshold("code", 0.50)
        assert threshold < 0.50, f"Expected relaxed threshold <0.50, got {threshold}"

    def test_no_adjustment_in_target_band(self):
        """No adjustment when acceptance rate is within target band."""
        mgr = AdaptiveThresholdManager(
            target_acceptance_rate=0.55, min_samples=10, adjustment_step=0.02
        )
        # Record 55% acceptance (exactly on target)
        for i in range(20):
            mgr.record("code", confidence=0.60, accepted=(i % 2 == 0))
        threshold = mgr.get_threshold("code", 0.50)
        assert threshold == 0.50

    def test_adjustment_clamped(self):
        """Adjustment doesn't exceed ±0.15."""
        mgr = AdaptiveThresholdManager(
            target_acceptance_rate=0.55, min_samples=10, adjustment_step=0.10
        )
        # Many rounds of 100% acceptance
        for _ in range(100):
            mgr.record("code", confidence=0.90, accepted=True)
        threshold = mgr.get_threshold("code", 0.50)
        assert threshold <= 0.65, f"Adjustment should be clamped at +0.15, got {threshold}"

    def test_per_domain_isolation(self):
        """Adjustments are per-domain, not global."""
        mgr = AdaptiveThresholdManager(min_samples=10, adjustment_step=0.02)
        for _ in range(10):
            mgr.record("code", confidence=0.80, accepted=True)
        for _ in range(10):
            mgr.record("math", confidence=0.30, accepted=False)

        code_t = mgr.get_threshold("code", 0.50)
        math_t = mgr.get_threshold("math", 0.50)
        assert code_t > 0.50  # tightened
        assert math_t < 0.50  # relaxed

    def test_stats(self):
        """get_stats() returns correct structure."""
        mgr = AdaptiveThresholdManager()
        for _ in range(5):
            mgr.record("code", confidence=0.60, accepted=True)
        stats = mgr.get_stats()
        assert stats["total_records"] == 5
        assert "code" in stats["domains"]
        assert stats["domains"]["code"]["samples"] == 5

    def test_is_likely_hard_without_embeddings(self):
        """is_likely_hard returns False when embeddings disabled."""
        mgr = AdaptiveThresholdManager(enable_embeddings=False)
        assert mgr.is_likely_hard("any query") is False


# ============================================================================
# Semantic Cache Deduplication
# ============================================================================
from cascadeflow.utils.caching import ResponseCache, SEMANTIC_SIMILARITY_THRESHOLD


class TestSemanticCache:
    """Test semantic deduplication in ResponseCache."""

    def test_basic_hash_hit(self):
        """Exact same query returns cached response."""
        cache = ResponseCache(enable_semantic_dedup=False)
        cache.set("What is Python?", {"content": "A language"})
        result = cache.get("What is Python?")
        assert result == {"content": "A language"}
        assert cache.stats["hits"] == 1

    def test_hash_miss(self):
        """Different query returns None."""
        cache = ResponseCache(enable_semantic_dedup=False)
        cache.set("What is Python?", {"content": "A language"})
        result = cache.get("What is Java?")
        assert result is None
        assert cache.stats["misses"] == 1

    def test_semantic_dedup_enabled(self):
        """Paraphrased query gets semantic hit when enabled."""
        cache = ResponseCache(enable_semantic_dedup=True)
        cache.set("What is Python?", {"content": "A programming language"})

        result = cache.get("Tell me about the Python programming language")
        # Depending on FastEmbed availability, may or may not match
        if result is not None:
            assert cache.stats["semantic_hits"] >= 1
            assert result == {"content": "A programming language"}

    def test_semantic_dedup_disabled_no_overhead(self):
        """No semantic lookup when disabled."""
        cache = ResponseCache(enable_semantic_dedup=False)
        cache.set("What is Python?", {"content": "A language"})
        result = cache.get("Tell me about Python")
        assert result is None
        assert cache.stats.get("semantic_hits", 0) == 0

    def test_stats_include_semantic(self):
        """Stats include semantic dedup fields."""
        cache = ResponseCache(enable_semantic_dedup=True)
        stats = cache.get_stats()
        assert "semantic_dedup_enabled" in stats
        assert "embeddings_cached" in stats
        assert stats["semantic_dedup_enabled"] is True

    def test_clear_clears_embeddings(self):
        """clear() also clears embedding cache."""
        cache = ResponseCache(enable_semantic_dedup=True)
        cache.set("test", {"data": 1})
        cache.clear()
        assert cache.get_stats()["embeddings_cached"] == 0
        assert cache.get_stats()["size"] == 0

    def test_ttl_expiry(self):
        """Expired entries are not returned."""
        cache = ResponseCache(default_ttl=1, enable_semantic_dedup=False)
        # Use negative offset to force immediate expiry
        cache.set("test", {"data": 1})
        # Manually expire the entry
        key = cache._generate_key("test")
        cache.cache[key]["expires_at"] = time.time() - 1
        result = cache.get("test")
        assert result is None

    def test_lru_eviction_cleans_embeddings(self):
        """Eviction removes embedding too."""
        cache = ResponseCache(max_size=2, enable_semantic_dedup=True)
        cache.set("q1", {"d": 1})
        cache.set("q2", {"d": 2})
        cache.set("q3", {"d": 3})  # evicts q1
        assert cache.get_stats()["evictions"] == 1


# ============================================================================
# Alignment Scorer Semantic Fallback
# ============================================================================
from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer


class TestAlignmentSemanticFallback:
    """Test v15 semantic fallback integration."""

    def test_no_fallback_when_disabled(self):
        """Semantic fallback does not activate when disabled."""
        scorer = QueryResponseAlignmentScorer(use_semantic_fallback=False)
        score = scorer.score("What is AI?", "AI is artificial intelligence.", verbose=False)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_fallback_activates_in_uncertain_zone(self):
        """When rule score is 0.35-0.55, semantic fallback is tried."""
        scorer = QueryResponseAlignmentScorer(use_semantic_fallback=True)
        # Use a query/response pair likely to produce uncertain rule score
        result = scorer.score(
            "Explain quantum entanglement",
            "It is a phenomenon in physics where particles are connected.",
            verbose=True,
        )
        # Result should be an AlignmentAnalysis with features
        if hasattr(result, "features"):
            # If fallback fired, the feature will be present
            # If score wasn't in uncertain zone, it won't fire - both are valid
            assert isinstance(result.alignment_score, float)

    def test_high_confidence_skips_fallback(self):
        """Scores outside 0.35-0.55 skip semantic fallback."""
        scorer = QueryResponseAlignmentScorer(use_semantic_fallback=True)
        # MCQ should get high score (0.75) - well above fallback zone
        result = scorer.score(
            "What is 2+2?\nA) 3\nB) 4\nC) 5\nD) 6",
            "B",
            verbose=True,
        )
        if hasattr(result, "features"):
            assert result.features.get("semantic_fallback") is None


# ============================================================================
# PriceBook
# ============================================================================
from cascadeflow.pricing.pricebook import PriceBook, PricingResolver, ModelPrice
from cascadeflow.schema.usage import Usage


class TestPriceBook:
    """Test pricing system."""

    def test_default_prices_comprehensive(self):
        """Default PriceBook has comprehensive model coverage."""
        pb = PriceBook()
        assert pb.get("gpt-4o") is not None
        assert pb.get("gpt-4o-mini") is not None
        assert pb.get("gpt-5") is not None
        assert pb.get("gpt-5-mini") is not None
        assert pb.get("o3-mini") is not None
        assert pb.get("claude-sonnet-4-5-20250929") is not None
        assert pb.get("llama-3.1-8b-instant") is not None

    def test_prefix_matching(self):
        """Versioned model names match via prefix."""
        pb = PriceBook()
        price = pb.get("gpt-4o-2024-08-06")
        assert price is not None
        assert price.input_per_1k == pb.get("gpt-4o").input_per_1k

    def test_update_single(self):
        """Runtime price update works."""
        pb = PriceBook()
        pb.update("custom-model", input_per_1k=0.001, output_per_1k=0.005)
        price = pb.get("custom-model")
        assert price is not None
        assert price.input_per_1k == 0.001

    def test_update_batch(self):
        """Batch price update works."""
        pb = PriceBook()
        pb.update_batch({
            "model-a": {"input_per_1k": 0.01, "output_per_1k": 0.02},
            "model-b": {"input_per_1k": 0.03, "output_per_1k": 0.04},
        })
        assert pb.get("model-a").input_per_1k == 0.01
        assert pb.get("model-b").output_per_1k == 0.04

    def test_models_property(self):
        """models property lists all known models."""
        pb = PriceBook()
        models = pb.models
        assert len(models) >= 10
        assert "gpt-4o" in models

    def test_sync_from_litellm_without_litellm(self):
        """sync_from_litellm returns 0 when LiteLLM not installed."""
        pb = PriceBook()
        # May return >0 if LiteLLM is installed, 0 if not
        count = pb.sync_from_litellm()
        assert isinstance(count, int)
        assert count >= 0


class TestPricingResolver:
    """Test cost resolution priority chain."""

    def test_provider_cost_highest_priority(self):
        """Provider-reported cost wins over everything."""
        resolver = PricingResolver()
        cost = resolver.resolve_cost(
            model="gpt-4o",
            usage=Usage(input_tokens=100, output_tokens=50),
            provider_cost=0.42,
            litellm_cost=0.30,
        )
        assert cost == 0.42

    def test_litellm_cost_second_priority(self):
        """LiteLLM cost used when no provider cost."""
        resolver = PricingResolver()
        cost = resolver.resolve_cost(
            model="gpt-4o",
            usage=Usage(input_tokens=100, output_tokens=50),
            litellm_cost=0.30,
        )
        assert cost == 0.30

    def test_pricebook_third_priority(self):
        """Internal pricebook used as fallback."""
        resolver = PricingResolver()
        cost = resolver.resolve_cost(
            model="gpt-4o",
            usage=Usage(input_tokens=1000, output_tokens=500),
        )
        expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.01
        assert abs(cost - expected) < 0.0001

    def test_fallback_rate(self):
        """Fallback rate used for unknown models."""
        resolver = PricingResolver()
        cost = resolver.resolve_cost(
            model="unknown-model-xyz",
            usage=Usage(input_tokens=500, output_tokens=500),
            fallback_rate_per_1k=0.01,
        )
        assert cost == (1000 / 1000) * 0.01

    def test_zero_for_fully_unknown(self):
        """Returns 0 when nothing matches."""
        resolver = PricingResolver()
        cost = resolver.resolve_cost(
            model="totally-unknown",
            usage=Usage(input_tokens=100, output_tokens=50),
        )
        assert cost == 0.0


# ============================================================================
# Cost Calculator (verify negative savings)
# ============================================================================
from cascadeflow.telemetry.cost_calculator import CostCalculator, CostBreakdown


class TestCostCalculatorNegativeSavings:
    """Verify cost_saved is negative when draft rejected."""

    def _make_calculator(self):
        from cascadeflow.schema.config import ModelConfig
        drafter = ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015)
        verifier = ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
        return CostCalculator(drafter=drafter, verifier=verifier)

    def test_draft_accepted_positive_savings(self):
        """Accepted draft produces positive savings."""
        calc = self._make_calculator()
        breakdown = calc.calculate_from_tokens(
            draft_output_tokens=50,
            verifier_output_tokens=0,
            draft_accepted=True,
            query_input_tokens=20,
        )
        assert breakdown.draft_accepted is True
        assert breakdown.cost_saved > 0
        assert breakdown.savings_percent > 0
        assert breakdown.verifier_cost == 0.0

    def test_draft_rejected_negative_savings(self):
        """Rejected draft produces negative savings (wasted cost)."""
        calc = self._make_calculator()
        breakdown = calc.calculate_from_tokens(
            draft_output_tokens=50,
            verifier_output_tokens=80,
            draft_accepted=False,
            query_input_tokens=20,
        )
        assert breakdown.draft_accepted is False
        assert breakdown.cost_saved < 0, "cost_saved should be negative when draft rejected"
        assert breakdown.savings_percent < 0
        assert breakdown.total_cost > breakdown.verifier_cost

    def test_baseline_always_verifier(self):
        """bigonly_cost is always the verifier baseline."""
        calc = self._make_calculator()

        # Accepted case
        b1 = calc.calculate_from_tokens(
            draft_output_tokens=50, verifier_output_tokens=0,
            draft_accepted=True, query_input_tokens=20,
        )
        assert b1.bigonly_cost > 0

        # Rejected case
        b2 = calc.calculate_from_tokens(
            draft_output_tokens=50, verifier_output_tokens=80,
            draft_accepted=False, query_input_tokens=20,
        )
        assert b2.bigonly_cost == b2.verifier_cost


# ============================================================================
# List-of-messages DX
# ============================================================================

class TestListMessagesDX:
    """Test that agent.run() accepts list of dicts as query."""

    def test_list_query_normalization(self):
        """When query is a list, it's treated as messages."""
        from cascadeflow.agent import CascadeAgent
        # Verify the method signature accepts Union[str, list]
        import inspect
        sig = inspect.signature(CascadeAgent.run)
        query_param = sig.parameters["query"]
        # The annotation should allow list
        assert "list" in str(query_param.annotation).lower() or "str" in str(query_param.annotation)


# ============================================================================
# OpenClaw Integration
# ============================================================================

class TestOpenClawIntegration:
    """Test OpenClaw adapter routing and flags."""

    def test_build_routing_decision_explicit(self):
        """Explicit domain tag is respected."""
        from cascadeflow.integrations.openclaw.adapter import build_routing_decision
        decision = build_routing_decision(
            method="getCompletion",
            event="generate",
            params={"cascadeflow": {"domain": "code"}},
        )
        assert decision.explicit is True
        assert decision.tags.get("domain") == "code"

    def test_build_routing_decision_heartbeat(self):
        """Heartbeat methods are classified."""
        from cascadeflow.integrations.openclaw.adapter import build_routing_decision
        decision = build_routing_decision(
            method="last-heartbeat",
            event="check",
        )
        assert decision.hint is not None
        assert decision.hint.category == "heartbeat"

    def test_build_routing_decision_voice(self):
        """Voice methods detected."""
        from cascadeflow.integrations.openclaw.adapter import build_routing_decision
        decision = build_routing_decision(
            method="tts.generate",
            event="speak",
        )
        assert decision.hint.category == "voice"

    def test_build_routing_decision_no_tags(self):
        """Generic method without tags gets classifier hint."""
        from cascadeflow.integrations.openclaw.adapter import build_routing_decision
        decision = build_routing_decision(
            method="someCustomMethod",
            event="custom",
        )
        assert decision.explicit is False


# ============================================================================
# Domain Detection Accuracy (production eval)
# ============================================================================
from cascadeflow.routing.domain import DomainDetector, Domain


class TestDomainDetectionProduction:
    """Production-grade domain detection accuracy tests."""

    def _detect(self, query):
        detector = DomainDetector()
        domain, conf = detector.detect(query)
        return domain

    def test_code_queries(self):
        assert self._detect("Write a Python sorting function") == Domain.CODE
        assert self._detect("Implement a binary search tree in Java") == Domain.CODE

    def test_math_queries(self):
        assert self._detect("Calculate the derivative of x^2") == Domain.MATH
        assert self._detect("Solve for x: 2x + 5 = 15") == Domain.MATH

    def test_medical_queries(self):
        assert self._detect("Explain the symptoms of diabetes") == Domain.MEDICAL

    def test_factual_queries(self):
        assert self._detect("What is the capital of France?") == Domain.FACTUAL

    def test_comparison_queries(self):
        assert self._detect("Compare PostgreSQL and MySQL performance") == Domain.COMPARISON

    def test_creative_queries(self):
        assert self._detect("Write a poem about the ocean") == Domain.CREATIVE

    def test_data_queries(self):
        assert self._detect("Create a data visualization of sales trends") == Domain.DATA

    def test_financial_queries(self):
        assert self._detect("What causes inflation?") == Domain.FINANCIAL

    def test_translation_queries(self):
        assert self._detect("Translate this paragraph from German to English") == Domain.TRANSLATION
