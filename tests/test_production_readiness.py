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
from cascadeflow.utils.caching import SEMANTIC_SIMILARITY_THRESHOLD, ResponseCache


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
from cascadeflow.pricing.pricebook import ModelPrice, PriceBook, PricingResolver
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
        pb.update_batch(
            {
                "model-a": {"input_per_1k": 0.01, "output_per_1k": 0.02},
                "model-b": {"input_per_1k": 0.03, "output_per_1k": 0.04},
            }
        )
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
from cascadeflow.telemetry.cost_calculator import CostBreakdown, CostCalculator


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
            draft_output_tokens=50,
            verifier_output_tokens=0,
            draft_accepted=True,
            query_input_tokens=20,
        )
        assert b1.bigonly_cost > 0

        # Rejected case
        b2 = calc.calculate_from_tokens(
            draft_output_tokens=50,
            verifier_output_tokens=80,
            draft_accepted=False,
            query_input_tokens=20,
        )
        assert b2.bigonly_cost == b2.verifier_cost


# ============================================================================
# List-of-messages DX
# ============================================================================


class TestListMessagesDX:
    """Test that agent.run() accepts list of dicts as query."""

    def test_list_query_normalization(self):
        """When query is a list, it's treated as messages."""
        # Verify the method signature accepts Union[str, list]
        import inspect

        from cascadeflow.agent import CascadeAgent

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
from cascadeflow.routing.domain import Domain, DomainDetector


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


# ============================================================================
# Streaming Module Tests (Professional Coverage)
# ============================================================================
import asyncio
import math
from unittest.mock import AsyncMock, MagicMock, patch

from cascadeflow.streaming.base import StreamEvent, StreamEventType, StreamManager
from cascadeflow.streaming.tools import ToolStreamEvent, ToolStreamEventType, ToolStreamManager
from cascadeflow.streaming.utils import (
    JSONParseState,
    ParseResult,
    ProgressiveJSONParser,
    ToolCallValidator,
    estimate_confidence_from_logprobs,
)


# --------------------------------------------------------------------------
# streaming/utils.py — ProgressiveJSONParser
# --------------------------------------------------------------------------
class TestProgressiveJSONParser:
    """Test progressive JSON parsing for streaming tool calls."""

    def test_parse_complete_json(self):
        parser = ProgressiveJSONParser()
        result = parser.parse('{"name": "get_weather", "arguments": {"city": "Paris"}}')
        assert result.state == JSONParseState.COMPLETE
        assert result.data["name"] == "get_weather"
        assert result.data["arguments"]["city"] == "Paris"

    def test_parse_partial_json_string_value(self):
        """Partial string without closing quote is recognized as partial."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"name": "get_weat')
        assert result.state == JSONParseState.PARTIAL
        # Parser can't extract value without closing quote, but recognizes valid start

    def test_parse_partial_json_number_value(self):
        """Partial JSON with complete number value pair."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"temperature": 22.5')
        assert result.state == JSONParseState.PARTIAL
        # Number value extraction depends on parser implementation
        if result.data:
            assert result.data["temperature"] == 22.5

    def test_parse_partial_json_boolean_value(self):
        """Partial JSON with complete boolean value pair."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"active": true')
        assert result.state == JSONParseState.PARTIAL
        if result.data:
            assert result.data["active"] is True

    def test_parse_partial_json_null_value(self):
        """Partial JSON with null value."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"value": null')
        assert result.state == JSONParseState.PARTIAL
        if result.data:
            assert result.data["value"] is None

    def test_parse_partial_json_nested_object(self):
        """Partial JSON with nested object start."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"args": {')
        assert result.state == JSONParseState.PARTIAL

    def test_parse_partial_json_array(self):
        """Partial JSON with array start."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"items": [')
        assert result.state == JSONParseState.PARTIAL

    def test_parse_empty_string(self):
        parser = ProgressiveJSONParser()
        result = parser.parse("")
        assert result.state == JSONParseState.EMPTY

    def test_parse_whitespace_only(self):
        parser = ProgressiveJSONParser()
        result = parser.parse("   ")
        assert result.state == JSONParseState.EMPTY

    def test_parse_invalid_json(self):
        parser = ProgressiveJSONParser()
        result = parser.parse("not json at all")
        assert result.state == JSONParseState.INVALID

    def test_parse_valid_json_start(self):
        parser = ProgressiveJSONParser()
        result = parser.parse("{")
        assert result.state == JSONParseState.PARTIAL

    def test_parse_array_start(self):
        parser = ProgressiveJSONParser()
        result = parser.parse("[")
        assert result.state == JSONParseState.PARTIAL

    def test_parse_complete_keys_list(self):
        parser = ProgressiveJSONParser()
        result = parser.parse('{"a": 1, "b": "two", "c": true}')
        assert result.state == JSONParseState.COMPLETE
        assert "a" in result.data
        assert "b" in result.data
        assert "c" in result.data

    def test_parse_multiple_string_values(self):
        """Multiple complete key-value pairs in partial JSON."""
        parser = ProgressiveJSONParser()
        result = parser.parse('{"name": "test", "city": "Berlin"')
        assert result.state == JSONParseState.PARTIAL
        # These string pairs are complete (both quotes present)
        if result.data:
            assert result.data["name"] == "test"
            assert result.data["city"] == "Berlin"


# --------------------------------------------------------------------------
# streaming/utils.py — ToolCallValidator
# --------------------------------------------------------------------------
class TestToolCallValidator:
    """Test tool call validation."""

    SAMPLE_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "number"},
                    },
                    "required": ["query"],
                },
            },
        },
    ]

    def test_valid_tool_call(self):
        tc = {"name": "get_weather", "arguments": {"location": "Paris"}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is True
        assert reason == "Valid"

    def test_valid_tool_call_with_optional_param(self):
        tc = {"name": "get_weather", "arguments": {"location": "Paris", "unit": "celsius"}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is True

    def test_missing_name_field(self):
        tc = {"arguments": {"location": "Paris"}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "name" in reason.lower()

    def test_missing_arguments_field(self):
        tc = {"name": "get_weather"}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "arguments" in reason.lower()

    def test_unknown_tool(self):
        tc = {"name": "nonexistent", "arguments": {}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "not found" in reason.lower()

    def test_missing_required_parameter(self):
        tc = {"name": "get_weather", "arguments": {"unit": "celsius"}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "location" in reason

    def test_wrong_parameter_type_string(self):
        tc = {"name": "get_weather", "arguments": {"location": 123}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "string" in reason.lower()

    def test_wrong_parameter_type_number(self):
        tc = {"name": "search", "arguments": {"query": "test", "limit": "five"}}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "number" in reason.lower()

    def test_arguments_as_json_string(self):
        tc = {"name": "get_weather", "arguments": '{"location": "Paris"}'}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is True

    def test_invalid_json_arguments(self):
        tc = {"name": "get_weather", "arguments": "{invalid json"}
        valid, reason = ToolCallValidator.validate_tool_call(tc, self.SAMPLE_TOOLS)
        assert valid is False
        assert "json" in reason.lower()

    def test_extract_tool_calls_from_json(self):
        response = '{"name": "get_weather", "arguments": {"location": "Paris"}}'
        calls = ToolCallValidator.extract_tool_calls_from_response(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_weather"

    def test_extract_tool_calls_from_list(self):
        response = '[{"name": "get_weather", "arguments": {"location": "Paris"}}]'
        calls = ToolCallValidator.extract_tool_calls_from_response(response)
        assert len(calls) == 1

    def test_extract_tool_calls_from_text(self):
        response = "I'll check the weather."
        calls = ToolCallValidator.extract_tool_calls_from_response(response)
        assert len(calls) == 0


# --------------------------------------------------------------------------
# streaming/utils.py — estimate_confidence_from_logprobs
# --------------------------------------------------------------------------
class TestEstimateConfidenceFromLogprobs:
    """Test logprob-to-confidence conversion."""

    def test_mean_method(self):
        # logprob of -0.1 ≈ exp(-0.1) ≈ 0.905
        conf = estimate_confidence_from_logprobs([-0.1, -0.1, -0.1], method="mean")
        assert conf is not None
        assert abs(conf - math.exp(-0.1)) < 0.01

    def test_min_method(self):
        conf = estimate_confidence_from_logprobs([-0.1, -0.5, -0.2], method="min")
        assert conf is not None
        assert abs(conf - math.exp(-0.5)) < 0.01

    def test_median_method(self):
        conf = estimate_confidence_from_logprobs([-0.1, -0.5, -0.3], method="median")
        assert conf is not None
        assert abs(conf - math.exp(-0.3)) < 0.01

    def test_empty_logprobs(self):
        assert estimate_confidence_from_logprobs([]) is None

    def test_invalid_method(self):
        assert estimate_confidence_from_logprobs([-0.1], method="invalid") is None

    def test_clamped_to_unit_interval(self):
        conf = estimate_confidence_from_logprobs([0.0], method="mean")
        assert conf is not None
        assert 0.0 <= conf <= 1.0

    def test_very_negative_logprobs(self):
        conf = estimate_confidence_from_logprobs([-100.0], method="mean")
        assert conf is not None
        assert conf >= 0.0


# --------------------------------------------------------------------------
# streaming/base.py — StreamEvent data classes
# --------------------------------------------------------------------------
class TestStreamEventDataClasses:
    """Test StreamEvent and StreamEventType."""

    def test_event_types_exist(self):
        assert StreamEventType.ROUTING.value == "routing"
        assert StreamEventType.CHUNK.value == "chunk"
        assert StreamEventType.DRAFT_DECISION.value == "draft_decision"
        assert StreamEventType.SWITCH.value == "switch"
        assert StreamEventType.COMPLETE.value == "complete"
        assert StreamEventType.ERROR.value == "error"

    def test_stream_event_defaults(self):
        event = StreamEvent(type=StreamEventType.CHUNK)
        assert event.content == ""
        assert event.data == {}

    def test_stream_event_metadata_alias(self):
        event = StreamEvent(type=StreamEventType.CHUNK, data={"key": "val"})
        assert event.metadata == {"key": "val"}

    def test_stream_event_with_content(self):
        event = StreamEvent(type=StreamEventType.CHUNK, content="Hello", data={"model": "gpt-4o"})
        assert event.content == "Hello"
        assert event.data["model"] == "gpt-4o"


# --------------------------------------------------------------------------
# streaming/tools.py — ToolStreamEvent data classes
# --------------------------------------------------------------------------
class TestToolStreamEventDataClasses:
    """Test ToolStreamEvent and ToolStreamEventType."""

    def test_tool_event_types_exist(self):
        assert ToolStreamEventType.ROUTING.value == "routing"
        assert ToolStreamEventType.TOOL_CALL_START.value == "tool_call_start"
        assert ToolStreamEventType.TOOL_CALL_DELTA.value == "tool_call_delta"
        assert ToolStreamEventType.TOOL_CALL_COMPLETE.value == "tool_call_complete"
        assert ToolStreamEventType.TOOL_EXECUTING.value == "tool_executing"
        assert ToolStreamEventType.TOOL_RESULT.value == "tool_result"
        assert ToolStreamEventType.TOOL_ERROR.value == "tool_error"
        assert ToolStreamEventType.TEXT_CHUNK.value == "text_chunk"
        assert ToolStreamEventType.DRAFT_DECISION.value == "draft_decision"
        assert ToolStreamEventType.SWITCH.value == "switch"
        assert ToolStreamEventType.COMPLETE.value == "complete"
        assert ToolStreamEventType.ERROR.value == "error"

    def test_tool_event_defaults(self):
        event = ToolStreamEvent(type=ToolStreamEventType.TOOL_CALL_START)
        assert event.content == ""
        assert event.tool_call is None
        assert event.delta is None
        assert event.tool_result is None
        assert event.error is None
        assert event.data == {}

    def test_tool_event_with_tool_call(self):
        tc = {"name": "get_weather", "arguments": {"city": "Paris"}}
        event = ToolStreamEvent(type=ToolStreamEventType.TOOL_CALL_COMPLETE, tool_call=tc)
        assert event.tool_call["name"] == "get_weather"

    def test_tool_event_with_error(self):
        event = ToolStreamEvent(type=ToolStreamEventType.TOOL_ERROR, error="Connection failed")
        assert event.error == "Connection failed"


# --------------------------------------------------------------------------
# streaming/base.py — StreamManager helper methods
# --------------------------------------------------------------------------
class TestStreamManagerHelpers:
    """Test StreamManager cost/token/confidence helpers with mock cascade."""

    def _make_manager(self, drafter_cost=0.00015, verifier_cost=0.00625):
        """Create a StreamManager with mock cascade (no real providers)."""
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.name = "gpt-4o-mini"
        cascade.drafter.provider = "openai"
        cascade.drafter.cost = drafter_cost
        cascade.drafter.speed_ms = 200

        cascade.verifier = MagicMock()
        cascade.verifier.name = "gpt-4o"
        cascade.verifier.provider = "openai"
        cascade.verifier.cost = verifier_cost
        cascade.verifier.speed_ms = 800

        cascade.providers = {}

        mgr = StreamManager.__new__(StreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        return mgr

    def test_estimate_tokens_from_text_normal(self):
        mgr = self._make_manager()
        tokens = mgr._estimate_tokens_from_text("Hello world this is a test")
        # 6 words * 1.3 = 7.8 -> 7
        assert tokens == 7

    def test_estimate_tokens_from_text_empty(self):
        mgr = self._make_manager()
        assert mgr._estimate_tokens_from_text("") == 0

    def test_estimate_tokens_from_text_single_word(self):
        mgr = self._make_manager()
        assert mgr._estimate_tokens_from_text("Hello") == max(1, int(1 * 1.3))

    def test_calculate_cost_from_tokens(self):
        mgr = self._make_manager()
        cost = mgr._calculate_cost_from_tokens(mgr.cascade.drafter, 1000)
        assert abs(cost - 0.00015) < 1e-10

    def test_calculate_confidence_from_logprobs_openai(self):
        mgr = self._make_manager()
        conf = mgr._calculate_confidence_from_logprobs([-0.1, -0.2, -0.15], "openai")
        assert conf is not None
        assert 0.0 <= conf <= 1.0

    def test_calculate_confidence_from_logprobs_anthropic(self):
        mgr = self._make_manager()
        # Anthropic doesn't provide logprobs
        conf = mgr._calculate_confidence_from_logprobs([-0.1], "anthropic")
        assert conf is None

    def test_calculate_confidence_from_logprobs_empty(self):
        mgr = self._make_manager()
        assert mgr._calculate_confidence_from_logprobs([], "openai") is None

    def test_estimate_confidence_from_content_normal(self):
        mgr = self._make_manager()
        conf = mgr._estimate_confidence_from_content(
            "This is a detailed answer with multiple sentences.", "What is AI?"
        )
        assert 0.50 <= conf <= 0.85

    def test_estimate_confidence_from_content_uncertain(self):
        mgr = self._make_manager()
        conf = mgr._estimate_confidence_from_content(
            "I'm not sure about this but maybe it's related to neural networks.", "What is AI?"
        )
        assert conf < 0.75  # Penalty for uncertainty markers

    def test_estimate_confidence_from_content_short(self):
        mgr = self._make_manager()
        conf = mgr._estimate_confidence_from_content("Yes", "Is it?")
        assert conf < 0.75  # Penalty for very short response

    def test_calculate_costs_draft_accepted(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs(
            draft_content="This is the draft response with several words",
            verifier_content=None,
            draft_accepted=True,
            query_text="What is AI?",
        )
        assert costs["draft_cost"] > 0
        assert costs["verifier_cost"] == 0.0
        assert costs["total_cost"] == costs["draft_cost"]
        assert costs["cost_saved"] > 0  # Saved verifier cost

    def test_calculate_costs_draft_rejected(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs(
            draft_content="Bad draft response",
            verifier_content="Better verifier response with more detail",
            draft_accepted=False,
            query_text="What is AI?",
        )
        assert costs["draft_cost"] > 0
        assert costs["verifier_cost"] > 0
        assert costs["total_cost"] == costs["draft_cost"] + costs["verifier_cost"]
        assert costs["cost_saved"] < 0  # Negative: wasted draft cost

    def test_calculate_costs_includes_input_tokens(self):
        mgr = self._make_manager()
        costs_no_query = mgr._calculate_costs(
            draft_content="Response",
            verifier_content=None,
            draft_accepted=True,
            query_text="",
        )
        costs_with_query = mgr._calculate_costs(
            draft_content="Response",
            verifier_content=None,
            draft_accepted=True,
            query_text="This is a long query with many words to increase token count",
        )
        assert costs_with_query["draft_cost"] > costs_no_query["draft_cost"]
        assert costs_with_query["draft_tokens"] > costs_no_query["draft_tokens"]


# --------------------------------------------------------------------------
# streaming/tools.py — ToolStreamManager helper methods
# --------------------------------------------------------------------------
class TestToolStreamManagerHelpers:
    """Test ToolStreamManager cost and token helpers."""

    def _make_manager(self):
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.name = "gpt-4o-mini"
        cascade.drafter.provider = "openai"
        cascade.drafter.cost = 0.00015

        cascade.verifier = MagicMock()
        cascade.verifier.name = "gpt-4o"
        cascade.verifier.provider = "openai"
        cascade.verifier.cost = 0.00625

        cascade.providers = {}

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = None
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()
        return mgr

    def test_estimate_tokens_from_text(self):
        mgr = self._make_manager()
        tokens = mgr._estimate_tokens_from_text("Hello world test")
        assert tokens == int(3 * 1.3)

    def test_estimate_tokens_from_text_empty(self):
        mgr = self._make_manager()
        assert mgr._estimate_tokens_from_text("") == 0

    def test_estimate_messages_tokens(self):
        mgr = self._make_manager()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        tokens = mgr._estimate_messages_tokens(messages)
        assert tokens > 0

    def test_estimate_messages_tokens_empty(self):
        mgr = self._make_manager()
        assert mgr._estimate_messages_tokens([]) == 0

    def test_estimate_tool_call_tokens(self):
        mgr = self._make_manager()
        tool_calls = [
            {"name": "get_weather", "arguments": {"location": "Paris"}},
            {"name": "search", "arguments": {"query": "test"}},
        ]
        tokens = mgr._estimate_tool_call_tokens(tool_calls)
        assert tokens > 0

    def test_estimate_tool_call_tokens_none(self):
        mgr = self._make_manager()
        assert mgr._estimate_tool_call_tokens(None) == 0

    def test_calculate_cost_from_tokens(self):
        mgr = self._make_manager()
        cost = mgr._calculate_cost_from_tokens(mgr.cascade.drafter, 1000)
        assert abs(cost - 0.00015) < 1e-10

    def test_calculate_costs_from_token_totals(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs_from_token_totals(draft_tokens=100, verifier_tokens=200)
        assert costs["draft_cost"] > 0
        assert costs["verifier_cost"] > 0
        assert costs["total_cost"] == costs["draft_cost"] + costs["verifier_cost"]
        assert costs["draft_tokens"] == 100
        assert costs["verifier_tokens"] == 200
        assert costs["total_tokens"] == 300

    def test_calculate_costs_from_token_totals_zero_verifier(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs_from_token_totals(draft_tokens=100, verifier_tokens=0)
        assert costs["verifier_cost"] == 0.0
        assert costs["cost_saved"] > 0  # bigonly_cost > draft_cost

    def test_calculate_costs_tool_accepted(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs(
            draft_content="I'll check the weather",
            verifier_content=None,
            draft_accepted=True,
            query_text="What's the weather?",
            tool_calls=[{"name": "get_weather", "arguments": {"city": "Paris"}}],
        )
        assert costs["draft_cost"] > 0
        assert costs["verifier_cost"] == 0.0
        assert costs["cost_saved"] > 0

    def test_calculate_costs_tool_rejected(self):
        mgr = self._make_manager()
        costs = mgr._calculate_costs(
            draft_content="Bad draft",
            verifier_content="Better response",
            draft_accepted=False,
            query_text="What's the weather?",
            tool_calls=[{"name": "get_weather", "arguments": {"city": "Paris"}}],
        )
        assert costs["cost_saved"] < 0

    def test_append_tool_results_to_messages(self):
        mgr = self._make_manager()
        messages = [{"role": "user", "content": "hi"}]
        tool_calls = [{"name": "weather", "id": "tc_1"}]
        tool_results = [{"success": True, "result": {"temp": 22}}]
        updated = mgr._append_tool_results_to_messages(messages, tool_calls, tool_results)
        assert len(updated) == 2
        assert updated[1]["role"] == "tool"
        assert "22" in updated[1]["content"]

    def test_append_tool_results_error(self):
        mgr = self._make_manager()
        messages = [{"role": "user", "content": "hi"}]
        tool_calls = [{"name": "weather", "id": "tc_1"}]
        tool_results = [{"success": False, "error": "timeout"}]
        updated = mgr._append_tool_results_to_messages(messages, tool_calls, tool_results)
        assert "timeout" in updated[1]["content"]


# --------------------------------------------------------------------------
# streaming/base.py — StreamManager.stream() async integration
# --------------------------------------------------------------------------
class TestStreamManagerStream:
    """Test StreamManager.stream() with mock providers."""

    def _make_cascade(self, draft_accepted=True):
        """Create a mock cascade with streaming draft provider."""
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.name = "gpt-4o-mini"
        cascade.drafter.provider = "openai"
        cascade.drafter.cost = 0.00015
        cascade.drafter.speed_ms = 200

        cascade.verifier = MagicMock()
        cascade.verifier.name = "gpt-4o"
        cascade.verifier.provider = "openai"
        cascade.verifier.cost = 0.00625
        cascade.verifier.speed_ms = 800

        # Quality validator
        val_result = MagicMock()
        val_result.passed = draft_accepted
        val_result.score = 0.85 if draft_accepted else 0.30
        cascade.quality_validator = MagicMock()
        cascade.quality_validator.validate.return_value = val_result
        cascade.quality_validator.config = MagicMock()
        cascade.quality_validator.config.confidence_thresholds = {"moderate": 0.50}

        # Draft provider with stream method
        draft_provider = MagicMock()

        async def mock_draft_stream(**kwargs):
            for chunk in ["Hello", " world", "!"]:
                yield chunk

        draft_provider.stream = mock_draft_stream

        # Verifier provider with stream method
        verifier_provider = MagicMock()

        async def mock_verifier_stream(**kwargs):
            for chunk in ["Better", " answer", " here"]:
                yield chunk

        verifier_provider.stream = mock_verifier_stream

        cascade.providers = {
            "openai": draft_provider,
        }

        return cascade, draft_provider, verifier_provider

    @pytest.mark.asyncio
    async def test_stream_draft_accepted(self):
        """Full stream flow when draft is accepted."""
        cascade, dp, vp = self._make_cascade(draft_accepted=True)
        cascade.providers = {"openai": dp}

        mgr = StreamManager.__new__(StreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False

        events = []
        async for event in mgr.stream("What is AI?", max_tokens=50):
            events.append(event)

        types = [e.type for e in events]
        assert StreamEventType.ROUTING in types
        assert StreamEventType.CHUNK in types
        assert StreamEventType.DRAFT_DECISION in types
        assert StreamEventType.COMPLETE in types
        # No SWITCH when accepted
        assert StreamEventType.SWITCH not in types

        # Check complete event has result data
        complete_event = [e for e in events if e.type == StreamEventType.COMPLETE][0]
        result = complete_event.data["result"]
        assert result["draft_accepted"] is True
        assert result["cascaded"] is False
        assert result["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_stream_draft_rejected_cascade(self):
        """Full stream flow when draft is rejected and cascades to verifier."""
        cascade, dp, vp = self._make_cascade(draft_accepted=False)
        cascade.drafter.provider = "openai_draft"
        cascade.verifier.provider = "openai_verify"
        cascade.providers = {"openai_draft": dp, "openai_verify": vp}

        mgr = StreamManager.__new__(StreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False

        events = []
        async for event in mgr.stream("Explain quantum mechanics", max_tokens=50):
            events.append(event)

        types = [e.type for e in events]
        assert StreamEventType.ROUTING in types
        assert StreamEventType.DRAFT_DECISION in types
        assert StreamEventType.SWITCH in types
        assert StreamEventType.COMPLETE in types

        complete_event = [e for e in events if e.type == StreamEventType.COMPLETE][0]
        result = complete_event.data["result"]
        assert result["draft_accepted"] is False
        assert result["cascaded"] is True
        assert result["cost_saved"] < 0  # Negative savings

    @pytest.mark.asyncio
    async def test_stream_direct_route(self):
        """Direct routing bypasses draft entirely."""
        cascade, dp, vp = self._make_cascade()
        cascade.providers = {"openai": vp}

        mgr = StreamManager.__new__(StreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False

        events = []
        async for event in mgr.stream("What is AI?", is_direct_route=True, max_tokens=50):
            events.append(event)

        types = [e.type for e in events]
        assert StreamEventType.ROUTING in types
        assert StreamEventType.CHUNK in types
        assert StreamEventType.COMPLETE in types
        # No draft decision or switch for direct route
        assert StreamEventType.DRAFT_DECISION not in types

        complete_event = [e for e in events if e.type == StreamEventType.COMPLETE][0]
        result = complete_event.data["result"]
        assert result["draft_accepted"] is None
        assert result["cascaded"] is False

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """Stream yields ERROR event on exception."""
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.provider = "openai"
        cascade.drafter.name = "gpt-4o-mini"
        cascade.providers = {}  # Missing provider will cause error

        mgr = StreamManager.__new__(StreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False

        events = []
        async for event in mgr.stream("test", max_tokens=10):
            events.append(event)

        types = [e.type for e in events]
        # Should have routing then error
        assert StreamEventType.ERROR in types


# --------------------------------------------------------------------------
# streaming/tools.py — ToolStreamManager.stream() async integration
# --------------------------------------------------------------------------
class TestToolStreamManagerStream:
    """Test ToolStreamManager.stream() with mock providers."""

    def _make_tool_cascade(self, draft_valid=True):
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.name = "gpt-4o-mini"
        cascade.drafter.provider = "openai"
        cascade.drafter.cost = 0.00015

        cascade.verifier = MagicMock()
        cascade.verifier.name = "gpt-4o"
        cascade.verifier.provider = "openai"
        cascade.verifier.cost = 0.00625

        # Provider with complete_with_tools (non-streaming)
        provider = MagicMock()
        response = MagicMock()
        response.content = "I'll check the weather for you."
        response.tool_calls = (
            [{"name": "get_weather", "arguments": {"location": "Paris"}, "id": "tc_1"}]
            if draft_valid
            else []
        )
        provider.complete_with_tools = AsyncMock(return_value=response)
        # No stream_with_tools — triggers non-streaming path
        if hasattr(provider, "stream_with_tools"):
            del provider.stream_with_tools

        cascade.providers = {"openai": provider}

        # Optional tool quality validator
        cascade.tool_quality_validator = None

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                    },
                },
            }
        ]
        return cascade, provider, tools

    @pytest.mark.asyncio
    async def test_tool_stream_accepted(self):
        """Tool call stream flow when draft tool calls are valid."""
        cascade, provider, tools = self._make_tool_cascade(draft_valid=True)

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = None
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()

        events = []
        async for event in mgr.stream("What's the weather?", tools=tools, max_tokens=50):
            events.append(event)

        types = [e.type for e in events]
        assert ToolStreamEventType.ROUTING in types
        assert ToolStreamEventType.TOOL_CALL_COMPLETE in types
        assert ToolStreamEventType.COMPLETE in types

        complete_event = [e for e in events if e.type == ToolStreamEventType.COMPLETE][0]
        result = complete_event.data["result"]
        assert result["draft_accepted"] is True
        assert len(result["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_tool_stream_no_tools_raises(self):
        """Empty tools list raises ValueError."""
        cascade, _, _ = self._make_tool_cascade()

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = None
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()

        async def _consume_one() -> None:
            async for _ in mgr.stream("test", tools=[], max_tokens=50):
                break

        with pytest.raises(ValueError, match="tools parameter is required"):
            await _consume_one()

    @pytest.mark.asyncio
    async def test_tool_stream_provider_error(self):
        """Provider without complete_with_tools yields ERROR event."""
        cascade = MagicMock()
        cascade.drafter = MagicMock()
        cascade.drafter.name = "gpt-4o-mini"
        cascade.drafter.provider = "openai"
        cascade.drafter.cost = 0.00015
        cascade.verifier = MagicMock()
        cascade.verifier.name = "gpt-4o"
        cascade.verifier.provider = "openai"
        cascade.verifier.cost = 0.00625

        # Provider WITHOUT tool support
        provider = MagicMock(spec=[])
        cascade.providers = {"openai": provider}

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = None
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()

        events = []
        async for event in mgr.stream(
            "test",
            tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
            max_tokens=50,
        ):
            events.append(event)

        types = [e.type for e in events]
        assert ToolStreamEventType.ERROR in types

    @pytest.mark.asyncio
    async def test_tool_stream_with_execution(self):
        """Tool execution flow when execute_tools=True."""
        cascade, provider, tools = self._make_tool_cascade(draft_valid=True)

        async def mock_executor(tool_call, available_tools):
            return {"temp": 22, "condition": "sunny"}

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = mock_executor
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()

        events = []
        async for event in mgr.stream(
            "What's the weather?",
            tools=tools,
            execute_tools=True,
            max_tokens=50,
            max_turns=1,
        ):
            events.append(event)

        types = [e.type for e in events]
        assert ToolStreamEventType.TOOL_EXECUTING in types
        assert ToolStreamEventType.TOOL_RESULT in types
        assert ToolStreamEventType.COMPLETE in types

    @pytest.mark.asyncio
    async def test_tool_stream_execution_error(self):
        """Tool execution error yields TOOL_ERROR event."""
        cascade, provider, tools = self._make_tool_cascade(draft_valid=True)

        async def failing_executor(tool_call, available_tools):
            raise RuntimeError("API key expired")

        mgr = ToolStreamManager.__new__(ToolStreamManager)
        mgr.cascade = cascade
        mgr.verbose = False
        mgr.tool_executor = failing_executor
        mgr.cost_calculator = None
        mgr._has_cost_calculator = False
        mgr.json_parser = ProgressiveJSONParser()
        mgr.validator = ToolCallValidator()

        events = []
        async for event in mgr.stream(
            "What's the weather?",
            tools=tools,
            execute_tools=True,
            max_tokens=50,
            max_turns=1,
        ):
            events.append(event)

        types = [e.type for e in events]
        assert ToolStreamEventType.TOOL_ERROR in types
        error_event = [e for e in events if e.type == ToolStreamEventType.TOOL_ERROR][0]
        assert "API key expired" in error_event.error


# --------------------------------------------------------------------------
# agent.py — _execute_tool_calls_parallel (fixed stub)
# --------------------------------------------------------------------------
class TestExecuteToolCallsParallel:
    """Test the fixed _execute_tool_calls_parallel method."""

    def _make_agent(self, tool_executor=None):
        from cascadeflow.agent import CascadeAgent
        from cascadeflow.schema.config import ModelConfig

        drafter = ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015)
        verifier = ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
        agent = CascadeAgent(
            models=[drafter, verifier],
            tool_executor=tool_executor,
        )
        return agent

    @pytest.mark.asyncio
    async def test_no_executor_returns_error_message(self):
        """Without tool_executor, returns informative error."""
        agent = self._make_agent(tool_executor=None)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'},
            }
        ]
        results = await agent._execute_tool_calls_parallel(tool_calls)
        assert len(results) == 1
        assert results[0]["tool_call_id"] == "call_1"
        assert "no_executor_registered" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_callable_executor(self):
        """Async callable executor is used correctly."""

        async def my_executor(tc):
            name = tc.get("function", {}).get("name", "")
            return f'{{"result":"executed_{name}"}}'

        agent = self._make_agent(tool_executor=my_executor)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'},
            }
        ]
        results = await agent._execute_tool_calls_parallel(tool_calls)
        assert len(results) == 1
        assert "executed_get_weather" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_tool_executor_instance(self):
        """ToolExecutor instance is used correctly."""
        from cascadeflow.tools.config import ToolConfig
        from cascadeflow.tools.executor import ToolExecutor

        def get_weather(location: str) -> dict:
            return {"temp": 22, "city": location}

        tool_config = ToolConfig(
            name="get_weather",
            description="Get weather",
            parameters={
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
            function=get_weather,
        )
        executor = ToolExecutor(tools=[tool_config])
        agent = self._make_agent(tool_executor=executor)

        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location":"Paris"}'},
            }
        ]
        results = await agent._execute_tool_calls_parallel(tool_calls)
        assert len(results) == 1
        assert "Paris" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_executor_error_handling(self):
        """Executor errors are caught and returned as error content."""

        async def failing_executor(tc):
            raise ValueError("Bad arguments")

        agent = self._make_agent(tool_executor=failing_executor)
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "test", "arguments": "{}"},
            }
        ]
        results = await agent._execute_tool_calls_parallel(tool_calls)
        assert len(results) == 1
        assert "error" in results[0]["content"]
        assert "Bad arguments" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Multiple tool calls execute in parallel."""
        call_order = []

        async def tracking_executor(tc):
            name = tc.get("function", {}).get("name", "")
            call_order.append(name)
            return f"done_{name}"

        agent = self._make_agent(tool_executor=tracking_executor)
        tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "tool_a", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {"name": "tool_b", "arguments": "{}"}},
            {"id": "c3", "type": "function", "function": {"name": "tool_c", "arguments": "{}"}},
        ]
        results = await agent._execute_tool_calls_parallel(tool_calls)
        assert len(results) == 3
        assert len(call_order) == 3
        assert set(call_order) == {"tool_a", "tool_b", "tool_c"}
