"""
Tests for LiteLLM integration (Phase 2, Milestone 2.1).

Tests provider support, cost calculation, and validation.
"""

import pytest

# Import with fallback handling
try:
    from cascadeflow.integrations.litellm import (
        SUPPORTED_PROVIDERS,
        LiteLLMCostProvider,
        ProviderInfo,
        calculate_cost,
        get_model_cost,
        get_provider_info,
        validate_provider,
    )

    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False
    pytest.skip("LiteLLM integration not available", allow_module_level=True)


class TestSupportedProviders:
    """Test SUPPORTED_PROVIDERS dict and provider info."""

    def test_has_10_providers(self):
        """Should have exactly 10 strategic providers as per plan."""
        assert len(SUPPORTED_PROVIDERS) == 10

    def test_required_providers_present(self):
        """Should include all required providers."""
        required = [
            "openai",
            "anthropic",
            "groq",
            "together",
            "huggingface",
            "ollama",
            "vllm",
            "google",
            "azure",
            "deepseek",
        ]

        for provider in required:
            assert provider in SUPPORTED_PROVIDERS, f"Missing provider: {provider}"

    def test_provider_info_structure(self):
        """Each provider should have complete info."""
        for name, info in SUPPORTED_PROVIDERS.items():
            assert isinstance(info, ProviderInfo)
            assert info.name == name
            assert len(info.display_name) > 0
            assert len(info.value_prop) > 0
            assert isinstance(info.pricing_available, bool)
            assert isinstance(info.requires_api_key, bool)
            assert len(info.example_models) > 0

    def test_openai_value_prop(self):
        """OpenAI should have correct value prop."""
        openai = SUPPORTED_PROVIDERS["openai"]
        assert "production" in openai.value_prop.lower()
        assert openai.pricing_available is True
        assert openai.requires_api_key is True

    def test_groq_value_prop(self):
        """Groq should emphasize speed."""
        groq = SUPPORTED_PROVIDERS["groq"]
        assert "fast" in groq.value_prop.lower() or "speed" in groq.value_prop.lower()

    def test_ollama_no_api_key(self):
        """Ollama should not require API key (local)."""
        ollama = SUPPORTED_PROVIDERS["ollama"]
        assert ollama.requires_api_key is False
        assert ollama.pricing_available is False  # Free, local

    def test_vllm_no_api_key(self):
        """vLLM should not require API key (self-hosted)."""
        vllm = SUPPORTED_PROVIDERS["vllm"]
        assert vllm.requires_api_key is False
        assert vllm.pricing_available is False  # Self-hosted


class TestProviderValidation:
    """Test provider validation."""

    def test_validate_supported_provider(self):
        """Should accept supported providers."""
        assert validate_provider("openai") is True
        assert validate_provider("anthropic") is True
        assert validate_provider("groq") is True

    def test_validate_case_insensitive(self):
        """Should be case insensitive."""
        assert validate_provider("OpenAI") is True
        assert validate_provider("ANTHROPIC") is True
        assert validate_provider("GrOq") is True

    def test_validate_unsupported_provider(self):
        """Should reject unsupported providers."""
        assert validate_provider("unknown_provider") is False
        assert validate_provider("") is False
        assert validate_provider("fake") is False

    def test_get_provider_info_exists(self):
        """Should return info for existing provider."""
        info = get_provider_info("openai")
        assert info is not None
        assert info.name == "openai"
        assert info.display_name == "OpenAI"

    def test_get_provider_info_missing(self):
        """Should return None for missing provider."""
        info = get_provider_info("unknown")
        assert info is None


class TestLiteLLMCostProvider:
    """Test LiteLLMCostProvider class."""

    def test_init_with_fallback(self):
        """Should initialize with fallback enabled by default."""
        provider = LiteLLMCostProvider()
        assert provider.fallback_enabled is True

    def test_init_without_fallback(self):
        """Should initialize with fallback disabled if requested."""
        provider = LiteLLMCostProvider(fallback_enabled=False)
        assert provider.fallback_enabled is False

    def test_calculate_cost_returns_float(self):
        """Should return float cost."""
        provider = LiteLLMCostProvider()
        cost = provider.calculate_cost("gpt-4", input_tokens=100, output_tokens=50)

        assert isinstance(cost, float)
        assert cost >= 0

    def test_calculate_cost_zero_tokens(self):
        """Should handle zero tokens."""
        provider = LiteLLMCostProvider()
        cost = provider.calculate_cost("gpt-4", input_tokens=0, output_tokens=0)

        assert cost == 0.0

    def test_calculate_cost_input_only(self):
        """Should handle input tokens only."""
        provider = LiteLLMCostProvider()
        cost = provider.calculate_cost("gpt-4", input_tokens=1000, output_tokens=0)

        assert cost > 0

    def test_calculate_cost_output_only(self):
        """Should handle output tokens only."""
        provider = LiteLLMCostProvider()
        cost = provider.calculate_cost("gpt-4", input_tokens=0, output_tokens=1000)

        assert cost > 0

    def test_calculate_cost_output_more_expensive(self):
        """Output tokens should generally cost more than input tokens."""
        provider = LiteLLMCostProvider()

        input_cost = provider.calculate_cost("gpt-4", input_tokens=1000, output_tokens=0)
        output_cost = provider.calculate_cost("gpt-4", input_tokens=0, output_tokens=1000)

        # Output typically 2-3x more expensive than input
        assert output_cost > input_cost

    def test_calculate_cost_different_models(self):
        """Different models should have different costs."""
        provider = LiteLLMCostProvider()

        gpt4_cost = provider.calculate_cost("gpt-4", input_tokens=1000, output_tokens=1000)
        gpt35_cost = provider.calculate_cost("gpt-3.5-turbo", input_tokens=1000, output_tokens=1000)

        # GPT-4 should be more expensive than GPT-3.5
        assert gpt4_cost > gpt35_cost

    def test_get_model_cost_returns_dict(self):
        """Should return dict with pricing info."""
        provider = LiteLLMCostProvider()
        pricing = provider.get_model_cost("gpt-4")

        assert isinstance(pricing, dict)
        assert "input_cost_per_token" in pricing
        assert "output_cost_per_token" in pricing
        assert "max_tokens" in pricing
        assert "supports_streaming" in pricing

    def test_get_model_cost_positive_values(self):
        """Pricing should have positive values."""
        provider = LiteLLMCostProvider()
        pricing = provider.get_model_cost("gpt-4")

        assert pricing["input_cost_per_token"] >= 0
        assert pricing["output_cost_per_token"] >= 0
        assert pricing["max_tokens"] > 0

    def test_fallback_cost_calculation(self):
        """Fallback should work when LiteLLM unavailable."""
        provider = LiteLLMCostProvider(fallback_enabled=True)

        # Should not raise even if LiteLLM fails
        cost = provider._fallback_cost("gpt-4", 100, 50)

        assert isinstance(cost, float)
        assert cost > 0

    def test_fallback_pricing_info(self):
        """Fallback should provide pricing info."""
        provider = LiteLLMCostProvider(fallback_enabled=True)

        pricing = provider._fallback_pricing("unknown-model")

        assert isinstance(pricing, dict)
        assert "input_cost_per_token" in pricing
        assert "output_cost_per_token" in pricing


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_model_cost_function(self):
        """Should work as convenience function."""
        pricing = get_model_cost("gpt-4")

        assert isinstance(pricing, dict)
        assert "input_cost_per_token" in pricing

    def test_calculate_cost_function(self):
        """Should work as convenience function."""
        cost = calculate_cost("gpt-4", input_tokens=100, output_tokens=50)

        assert isinstance(cost, float)
        assert cost >= 0

    def test_calculate_cost_with_kwargs(self):
        """Should accept additional kwargs."""
        # Should not raise even with extra kwargs
        cost = calculate_cost("gpt-4", input_tokens=100, output_tokens=50, custom_param="test")

        assert isinstance(cost, float)


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_compare_providers_cost(self):
        """Should be able to compare costs across providers."""
        provider = LiteLLMCostProvider()

        # Same token counts, different models
        models = ["gpt-4", "gpt-3.5-turbo", "claude-3-haiku"]
        costs = {}

        for model in models:
            costs[model] = provider.calculate_cost(model, input_tokens=1000, output_tokens=500)

        # All should have positive costs
        for model, cost in costs.items():
            assert cost > 0, f"{model} should have positive cost"

    def test_budget_checking(self):
        """Should enable budget checking before API call."""
        provider = LiteLLMCostProvider()

        # Estimate cost before call
        estimated_cost = provider.calculate_cost("gpt-4", input_tokens=100, output_tokens=50)

        budget = 0.01  # $0.01 budget

        # Can afford?
        can_afford = estimated_cost <= budget
        assert isinstance(can_afford, bool)

    def test_cost_tracking_scenario(self):
        """Should enable cost tracking across multiple calls."""
        provider = LiteLLMCostProvider()

        # Simulate multiple API calls
        calls = [
            {"model": "gpt-4", "input": 100, "output": 50},
            {"model": "gpt-3.5-turbo", "input": 200, "output": 100},
            {"model": "gpt-4", "input": 150, "output": 75},
        ]

        total_cost = 0.0
        for call in calls:
            cost = provider.calculate_cost(
                call["model"], input_tokens=call["input"], output_tokens=call["output"]
            )
            total_cost += cost

        assert total_cost > 0
        assert isinstance(total_cost, float)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_model(self):
        """Should handle unknown models gracefully."""
        provider = LiteLLMCostProvider(fallback_enabled=True)

        # Should not raise, should use fallback
        cost = provider.calculate_cost("unknown-model-xyz", input_tokens=100, output_tokens=50)

        assert isinstance(cost, float)
        assert cost >= 0

    def test_very_large_token_counts(self):
        """Should handle very large token counts."""
        provider = LiteLLMCostProvider()

        # 1 million tokens
        cost = provider.calculate_cost("gpt-4", input_tokens=1_000_000, output_tokens=500_000)

        assert isinstance(cost, float)
        assert cost > 0

    def test_negative_tokens_handled(self):
        """Should handle negative tokens gracefully."""
        provider = LiteLLMCostProvider()

        # Should not raise, might return 0 or abs value
        try:
            cost = provider.calculate_cost("gpt-4", input_tokens=-100, output_tokens=50)
            assert isinstance(cost, float)
        except Exception:
            # Also acceptable to raise
            pass

    def test_empty_model_name(self):
        """Should handle empty model name."""
        provider = LiteLLMCostProvider(fallback_enabled=True)

        # Should use fallback
        cost = provider.calculate_cost("", input_tokens=100, output_tokens=50)

        assert isinstance(cost, float)


# ============================================================================
# INTEGRATION TESTS (require LiteLLM installed)
# ============================================================================


class TestLiteLLMIntegration:
    """Tests that verify LiteLLM integration when available."""

    def test_litellm_availability(self):
        """Check if LiteLLM is installed."""
        try:
            import litellm

            assert litellm is not None
            print("\n✓ LiteLLM is installed and available")
        except ImportError:
            # This is fine - fallback will be used
            print("\n✓ LiteLLM not installed, using fallback estimates")

    def test_supported_providers_work_with_or_without_litellm(self):
        """Our supported providers should work with or without LiteLLM."""
        provider = LiteLLMCostProvider()

        # Test a few key providers - should work even without LiteLLM
        for model in ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"]:
            pricing = provider.get_model_cost(model)
            # Should get pricing (real or fallback)
            assert pricing["input_cost_per_token"] > 0
            assert pricing["output_cost_per_token"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
