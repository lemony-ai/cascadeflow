"""
Tests for reasoning model support across all providers.

Tests auto-detection, cost calculation, and parameter handling for:
- OpenAI o1/o3 models
- Anthropic Claude 3.7 extended thinking
"""

import pytest

from cascadeflow.providers.anthropic import (
    AnthropicProvider,
)
from cascadeflow.providers.anthropic import (
    get_reasoning_model_info as get_anthropic_reasoning_model_info,
)
from cascadeflow.providers.ollama import (
    OllamaProvider,
)
from cascadeflow.providers.ollama import (
    get_reasoning_model_info as get_ollama_reasoning_model_info,
)
from cascadeflow.providers.openai import (
    OpenAIProvider,
)
from cascadeflow.providers.openai import (
    get_reasoning_model_info as get_openai_reasoning_model_info,
)
from cascadeflow.providers.vllm import (
    VLLMProvider,
)
from cascadeflow.providers.vllm import (
    get_reasoning_model_info as get_vllm_reasoning_model_info,
)


class TestReasoningModelDetection:
    """Test auto-detection of OpenAI reasoning models and their capabilities."""

    def test_o1_preview_detection(self):
        """Test o1-preview is detected as reasoning model."""
        info = get_openai_reasoning_model_info("o1-preview")
        assert info.is_reasoning is True
        assert info.supports_streaming is True
        assert info.supports_tools is False
        assert info.supports_system_messages is False
        assert info.supports_reasoning_effort is False
        assert info.requires_max_completion_tokens is False

    def test_o1_mini_detection(self):
        """Test o1-mini is detected as reasoning model."""
        info = get_openai_reasoning_model_info("o1-mini")
        assert info.is_reasoning is True
        assert info.supports_streaming is True
        assert info.supports_tools is False
        assert info.supports_system_messages is False

    def test_o1_2024_12_17_detection(self):
        """Test o1-2024-12-17 is detected as reasoning model."""
        info = get_openai_reasoning_model_info("o1-2024-12-17")
        assert info.is_reasoning is True
        assert info.supports_streaming is False
        assert info.supports_tools is False
        assert info.supports_system_messages is False
        assert info.supports_reasoning_effort is True
        assert info.requires_max_completion_tokens is True

    def test_o1_base_detection(self):
        """Test o1 (base) is detected as reasoning model."""
        info = get_openai_reasoning_model_info("o1")
        assert info.is_reasoning is True
        assert info.supports_reasoning_effort is True

    def test_o3_mini_detection(self):
        """Test o3-mini is detected as reasoning model."""
        info = get_openai_reasoning_model_info("o3-mini")
        assert info.is_reasoning is True
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is False
        assert info.supports_reasoning_effort is True

    def test_gpt4o_not_reasoning(self):
        """Test gpt-4o is NOT detected as reasoning model."""
        info = get_openai_reasoning_model_info("gpt-4o")
        assert info.is_reasoning is False
        assert info.supports_tools is True
        assert info.supports_system_messages is True

    def test_case_insensitive_detection(self):
        """Test model detection is case-insensitive."""
        info_lower = get_openai_reasoning_model_info("o1-mini")
        info_upper = get_openai_reasoning_model_info("O1-MINI")
        assert info_lower.is_reasoning == info_upper.is_reasoning
        assert info_lower.supports_tools == info_upper.supports_tools


class TestReasoningModelCost:
    """Test cost calculation for reasoning models."""

    def test_o1_preview_cost(self):
        """Test o1-preview cost calculation."""
        provider = OpenAIProvider(api_key="test")
        # Input: 1000 tokens at $0.015/1K = $0.015
        # Output: 2000 tokens at $0.060/1K = $0.120
        # Total: $0.135
        cost = provider.estimate_cost(
            tokens=3000, model="o1-preview", prompt_tokens=1000, completion_tokens=2000
        )
        assert abs(cost - 0.135) < 0.0001

    def test_o1_mini_cost(self):
        """Test o1-mini cost calculation."""
        provider = OpenAIProvider(api_key="test")
        # Input: 1000 tokens at $0.003/1K = $0.003
        # Output: 2000 tokens at $0.012/1K = $0.024
        # Total: $0.027
        cost = provider.estimate_cost(
            tokens=3000, model="o1-mini", prompt_tokens=1000, completion_tokens=2000
        )
        assert abs(cost - 0.027) < 0.0001

    def test_o1_2024_12_17_cost(self):
        """Test o1-2024-12-17 cost calculation."""
        provider = OpenAIProvider(api_key="test")
        cost = provider.estimate_cost(
            tokens=3000, model="o1-2024-12-17", prompt_tokens=1000, completion_tokens=2000
        )
        # Same pricing as o1-preview
        assert abs(cost - 0.135) < 0.0001

    def test_o3_mini_cost(self):
        """Test o3-mini cost calculation."""
        provider = OpenAIProvider(api_key="test")
        # Input: 1000 tokens at $0.001/1K = $0.001
        # Output: 2000 tokens at $0.005/1K = $0.010
        # Total: $0.011
        cost = provider.estimate_cost(
            tokens=3000, model="o3-mini", prompt_tokens=1000, completion_tokens=2000
        )
        assert abs(cost - 0.011) < 0.0001

    def test_versioned_model_prefix_matching(self):
        """Test prefix matching for versioned models."""
        provider = OpenAIProvider(api_key="test")
        # Should match 'o1-preview' prefix
        cost = provider.estimate_cost(
            tokens=3000, model="o1-preview-2025-01-15", prompt_tokens=1000, completion_tokens=2000
        )
        assert abs(cost - 0.135) < 0.0001

    def test_case_insensitive_cost_calculation(self):
        """Test cost calculation is case-insensitive."""
        provider = OpenAIProvider(api_key="test")
        cost_lower = provider.estimate_cost(
            tokens=3000, model="o1-mini", prompt_tokens=1000, completion_tokens=2000
        )
        cost_upper = provider.estimate_cost(
            tokens=3000, model="O1-MINI", prompt_tokens=1000, completion_tokens=2000
        )
        assert abs(cost_lower - cost_upper) < 0.0001

    def test_zero_tokens_cost(self):
        """Test cost calculation with zero tokens."""
        provider = OpenAIProvider(api_key="test")
        cost = provider.estimate_cost(
            tokens=0, model="o1-mini", prompt_tokens=0, completion_tokens=0
        )
        assert cost == 0

    def test_large_token_count_scaling(self):
        """Test cost calculation scales linearly for large token counts."""
        provider = OpenAIProvider(api_key="test")
        cost = provider.estimate_cost(
            tokens=3000000, model="o1-mini", prompt_tokens=1000000, completion_tokens=2000000
        )
        # Should scale linearly: (1M / 1K) * 0.003 + (2M / 1K) * 0.012 = 3 + 24 = 27
        assert abs(cost - 27.0) < 0.001


class TestReasoningModelPricing:
    """Test comprehensive pricing for all supported models."""

    @pytest.mark.parametrize(
        ("model", "input_price", "output_price"),
        [
            # GPT-5 series (only base model, others use prefix matching)
            ("gpt-5", 0.00125, 0.010),
            # GPT-4o series
            ("gpt-4o", 0.0025, 0.010),
            # O1 series (reasoning)
            ("o1-preview", 0.015, 0.060),
            ("o1-mini", 0.003, 0.012),
            ("o1", 0.015, 0.060),
            ("o1-2024-12-17", 0.015, 0.060),
            # O3 series (reasoning)
            ("o3-mini", 0.001, 0.005),
            # GPT-4 series
            ("gpt-4-turbo", 0.010, 0.030),
            ("gpt-4", 0.030, 0.060),
            # GPT-3.5 series
            ("gpt-3.5-turbo", 0.0005, 0.0015),
        ],
    )
    def test_model_pricing(self, model, input_price, output_price):
        """Test pricing for all supported models."""
        provider = OpenAIProvider(api_key="test")
        cost = provider.estimate_cost(
            tokens=2000, model=model, prompt_tokens=1000, completion_tokens=1000
        )
        expected_cost = (1000 / 1000) * input_price + (1000 / 1000) * output_price
        assert abs(cost - expected_cost) < 0.000001


class TestBackwardCompatibility:
    """Test that reasoning model support doesn't break existing functionality."""

    def test_non_reasoning_models_unchanged(self):
        """Test that non-reasoning models still work correctly."""
        provider = OpenAIProvider(api_key="test")
        cost = provider.estimate_cost(
            tokens=3000, model="gpt-3.5-turbo", prompt_tokens=1000, completion_tokens=2000
        )
        # gpt-3.5-turbo: input $0.0005/1K, output $0.0015/1K
        # 1000 * 0.0005 + 2000 * 0.0015 = 0.0005 + 0.003 = 0.0035
        assert abs(cost - 0.0035) < 0.0001

    def test_provider_initialization(self):
        """Test provider can be initialized with reasoning models."""
        provider = OpenAIProvider(api_key="test")
        assert provider is not None


class TestReasoningModelInfo:
    """Test the ReasoningModelInfo dataclass structure."""

    def test_reasoning_model_info_attributes(self):
        """Test ReasoningModelInfo has correct attributes."""
        info = get_openai_reasoning_model_info("o1-mini")
        assert hasattr(info, "is_reasoning")
        assert hasattr(info, "supports_streaming")
        assert hasattr(info, "supports_tools")
        assert hasattr(info, "supports_system_messages")
        assert hasattr(info, "supports_reasoning_effort")
        assert hasattr(info, "requires_max_completion_tokens")

    def test_default_model_info(self):
        """Test default values for standard models."""
        info = get_openai_reasoning_model_info("gpt-4o")
        assert info.is_reasoning is False
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is True
        assert info.supports_reasoning_effort is False
        assert info.requires_max_completion_tokens is False


# ========== Anthropic Claude Model Tests ==========


class TestAnthropicModelDetection:
    """Test auto-detection of Anthropic Claude model capabilities."""

    def test_claude_sonnet_3_5_standard_capabilities(self):
        """Test Claude 3.5 Sonnet has standard capabilities (not reasoning)."""
        info = get_anthropic_reasoning_model_info("claude-3-5-sonnet-20241022")
        assert info.is_reasoning is False
        assert info.supports_extended_thinking is False
        assert info.supports_streaming is True
        assert info.supports_tools is True

    def test_claude_3_5_sonnet_not_reasoning(self):
        """Test claude-3-5-sonnet is NOT detected as reasoning model."""
        info = get_anthropic_reasoning_model_info("claude-3-5-sonnet")
        assert info.is_reasoning is False
        assert info.supports_extended_thinking is False
        assert info.requires_thinking_budget is False

    def test_claude_3_opus_not_reasoning(self):
        """Test claude-3-opus is NOT detected as reasoning model."""
        info = get_anthropic_reasoning_model_info("claude-3-opus")
        assert info.is_reasoning is False
        assert info.supports_extended_thinking is False

    def test_claude_3_haiku_not_reasoning(self):
        """Test claude-3-haiku is NOT detected as reasoning model."""
        info = get_anthropic_reasoning_model_info("claude-3-haiku")
        assert info.is_reasoning is False
        assert info.supports_extended_thinking is False


class TestAnthropicModelCapabilities:
    """Test capabilities for Anthropic Claude models."""

    def test_claude_3_5_sonnet_capabilities(self):
        """Test Claude 3.5 Sonnet has standard capabilities."""
        info = get_anthropic_reasoning_model_info("claude-3-5-sonnet-20241022")
        assert info.is_reasoning is False
        assert info.provider == "anthropic"
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is True
        assert info.supports_extended_thinking is False
        assert info.requires_thinking_budget is False

    def test_claude_3_haiku_capabilities(self):
        """Test Claude 3 Haiku has standard capabilities."""
        info = get_anthropic_reasoning_model_info("claude-3-haiku-20240307")
        assert info.is_reasoning is False
        assert info.provider == "anthropic"
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is True
        assert info.supports_extended_thinking is False
        assert info.requires_thinking_budget is False


class TestAnthropicModelCost:
    """Test cost calculation for Anthropic models."""

    def test_claude_3_5_sonnet_cost(self):
        """Test claude-3-5-sonnet cost calculation."""
        provider = AnthropicProvider(api_key="test")
        # Blended rate: $9.00 per 1M tokens
        # 2M tokens total = $18.00
        cost = provider.estimate_cost(tokens=2000000, model="claude-3-5-sonnet-20241022")
        assert abs(cost - 18.0) < 0.001

    def test_claude_3_5_haiku_cost(self):
        """Test claude-3-5-haiku cost calculation."""
        provider = AnthropicProvider(api_key="test")
        # Blended rate: $3.00 per 1M tokens
        # 2M tokens total = $6.00
        cost = provider.estimate_cost(tokens=2000000, model="claude-3-5-haiku-20241022")
        assert abs(cost - 6.0) < 0.001

    def test_prefix_matching_versioned_models(self):
        """Test prefix matching for versioned Claude 3.5 models."""
        provider = AnthropicProvider(api_key="test")
        cost1 = provider.estimate_cost(tokens=2000000, model="claude-3-5-sonnet-20241022")
        cost2 = provider.estimate_cost(tokens=2000000, model="claude-3-5-sonnet-20240620")
        assert abs(cost1 - cost2) < 0.001  # Both should use same rate

    def test_zero_tokens_cost(self):
        """Test cost calculation with zero tokens."""
        provider = AnthropicProvider(api_key="test")
        cost = provider.estimate_cost(tokens=0, model="claude-3-7-sonnet")
        assert cost == 0

    def test_large_token_count_scaling(self):
        """Test cost calculation scales linearly for large token counts."""
        provider = AnthropicProvider(api_key="test")
        # 20M tokens at $9/M blended = $180
        cost = provider.estimate_cost(tokens=20000000, model="claude-3-7-sonnet")
        assert abs(cost - 180.0) < 0.01

    def test_fallback_pricing_unknown_model(self):
        """Test fallback to Sonnet pricing for unknown models."""
        provider = AnthropicProvider(api_key="test")
        cost = provider.estimate_cost(tokens=2000000, model="claude-unknown")
        # Should use $9.0 blended fallback
        assert abs(cost - 18.0) < 0.001


class TestAnthropicPricingMatrix:
    """Test comprehensive pricing for all Anthropic models."""

    @pytest.mark.parametrize(
        ("model", "expected_blended"),
        [
            # Claude 4 Series
            ("claude-opus-4.1", 45.0),
            ("claude-opus-4", 45.0),
            ("claude-sonnet-4.5", 9.0),
            ("claude-sonnet-4", 9.0),
            # Claude 3.5 Series
            ("claude-3-5-sonnet", 9.0),
            ("claude-3-5-haiku", 3.0),
            # Claude 3 Series
            ("claude-3-opus", 45.0),
            ("claude-3-sonnet", 9.0),
            ("claude-3-haiku", 0.75),
        ],
    )
    def test_model_blended_pricing(self, model, expected_blended):
        """Test blended pricing for all supported Anthropic models."""
        provider = AnthropicProvider(api_key="test")
        cost = provider.estimate_cost(tokens=2000000, model=model)
        expected_cost = 2.0 * expected_blended
        assert abs(cost - expected_cost) < 0.001


class TestAnthropicBackwardCompatibility:
    """Test backward compatibility of Anthropic models."""

    def test_standard_models_work_correctly(self):
        """Test that standard Claude models work correctly."""
        provider = AnthropicProvider(api_key="test")
        cost = provider.estimate_cost(tokens=2000000, model="claude-3-5-sonnet")
        # claude-3-5-sonnet: $9.0 blended
        assert abs(cost - 18.0) < 0.001

    def test_provider_initialization(self):
        """Test provider can be initialized with Claude 3.7 models."""
        provider = AnthropicProvider(api_key="test")
        assert provider is not None


class TestCrossProviderReasoningComparison:
    """Test comparison between OpenAI and Anthropic reasoning models."""

    def test_openai_vs_anthropic_detection(self):
        """Test detection works for both providers."""
        o1_info = get_openai_reasoning_model_info("o1-mini")
        claude_info = get_anthropic_reasoning_model_info("claude-sonnet-4-5")

        assert o1_info.is_reasoning is True
        assert claude_info.is_reasoning is True
        assert o1_info.provider == "openai"
        assert claude_info.provider == "anthropic"

    def test_different_capabilities(self):
        """Test OpenAI vs Anthropic have different capabilities."""
        o1_info = get_openai_reasoning_model_info("o1-mini")
        claude_info = get_anthropic_reasoning_model_info("claude-sonnet-4-5")

        # OpenAI o1 doesn't support tools
        assert o1_info.supports_tools is False

        # Claude Sonnet 4.5 supports tools
        assert claude_info.supports_tools is True

        # Different extended thinking approaches
        assert (
            not hasattr(o1_info, "supports_extended_thinking")
            or o1_info.supports_extended_thinking is False
        )
        assert claude_info.supports_extended_thinking is True

    def test_cost_comparison_o1_mini_vs_claude_3_7(self):
        """Test cost comparison between o1-mini and claude-3-7-sonnet.

        This test uses 2M input + 1M output tokens (3M total):
        - o1-mini: (2M / 1K) * $0.003 + (1M / 1K) * $0.012 = $6 + $12 = $18
        - claude-3-7: (3M / 1M) * $9 = $27

        So o1-mini should be cheaper for this distribution.
        """
        o1_provider = OpenAIProvider(api_key="test")
        claude_provider = AnthropicProvider(api_key="test")

        # Calculate costs with 2M prompt + 1M completion (favors o1-mini's cheaper input rate)
        o1_cost = o1_provider.estimate_cost(
            tokens=3000000, model="o1-mini", prompt_tokens=2000000, completion_tokens=1000000
        )
        claude_cost = claude_provider.estimate_cost(tokens=3000000, model="claude-3-7-sonnet")

        # Both should return valid costs
        assert o1_cost > 0
        assert claude_cost > 0

        # Verify o1-mini is cheaper for this distribution (18 < 27)
        assert o1_cost < claude_cost


class TestDeepSeekR1OllamaDetection:
    """Test DeepSeek-R1 detection for Ollama provider."""

    def test_deepseek_r1_detection(self):
        """Test deepseek-r1 is detected as reasoning model."""
        info = get_ollama_reasoning_model_info("deepseek-r1")
        assert info.is_reasoning is True
        assert info.provider == "ollama"
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is True
        assert info.supports_extended_thinking is False
        assert info.requires_thinking_budget is False

    def test_deepseek_r1_latest_detection(self):
        """Test deepseek-r1:latest is detected as reasoning model."""
        info = get_ollama_reasoning_model_info("deepseek-r1:latest")
        assert info.is_reasoning is True
        assert info.provider == "ollama"

    def test_deepseek_r1_8b_detection(self):
        """Test deepseek-r1:8b is detected as reasoning model."""
        info = get_ollama_reasoning_model_info("deepseek-r1:8b")
        assert info.is_reasoning is True
        assert info.provider == "ollama"

    def test_deepseek_r1_32b_detection(self):
        """Test deepseek-r1:32b is detected as reasoning model."""
        info = get_ollama_reasoning_model_info("deepseek-r1:32b")
        assert info.is_reasoning is True
        assert info.provider == "ollama"

    def test_deepseek_r1_70b_detection(self):
        """Test deepseek-r1:70b is detected as reasoning model."""
        info = get_ollama_reasoning_model_info("deepseek-r1:70b")
        assert info.is_reasoning is True
        assert info.provider == "ollama"

    def test_deepseek_r1_case_insensitive(self):
        """Test case-insensitive detection."""
        info1 = get_ollama_reasoning_model_info("DEEPSEEK-R1")
        info2 = get_ollama_reasoning_model_info("DeepSeek-R1:8B")
        assert info1.is_reasoning is True
        assert info2.is_reasoning is True

    def test_deepseek_r1_underscore_detection(self):
        """Test deepseek_r1 with underscore is detected."""
        info = get_ollama_reasoning_model_info("deepseek_r1")
        assert info.is_reasoning is True
        assert info.provider == "ollama"

    def test_llama_not_reasoning(self):
        """Test llama3.2 is not detected as reasoning model."""
        info = get_ollama_reasoning_model_info("llama3.2")
        assert info.is_reasoning is False
        assert info.provider == "ollama"

    def test_mistral_not_reasoning(self):
        """Test mistral is not detected as reasoning model."""
        info = get_ollama_reasoning_model_info("mistral")
        assert info.is_reasoning is False

    def test_qwen_not_reasoning(self):
        """Test qwen is not detected as reasoning model."""
        info = get_ollama_reasoning_model_info("qwen:7b")
        assert info.is_reasoning is False


class TestDeepSeekR1OllamaCost:
    """Test cost calculation for DeepSeek-R1 on Ollama (always free)."""

    def test_deepseek_r1_cost_is_free(self):
        """Test DeepSeek-R1 on Ollama is free."""
        provider = OllamaProvider()
        cost = provider.estimate_cost(tokens=1000000, model="deepseek-r1")
        assert cost == 0.0

    def test_all_ollama_models_are_free(self):
        """Test all Ollama models are free."""
        provider = OllamaProvider()
        models = ["deepseek-r1", "deepseek-r1:8b", "llama3.2", "mistral"]

        for model in models:
            cost = provider.estimate_cost(tokens=1000000, model=model)
            assert cost == 0.0

    def test_ollama_large_tokens_still_free(self):
        """Test large token counts are still free."""
        provider = OllamaProvider()
        cost = provider.estimate_cost(tokens=10000000, model="deepseek-r1")
        assert cost == 0.0


class TestDeepSeekR1VLLMDetection:
    """Test DeepSeek-R1 detection for vLLM provider."""

    def test_deepseek_r1_detection(self):
        """Test deepseek-r1 is detected as reasoning model."""
        info = get_vllm_reasoning_model_info("deepseek-r1")
        assert info.is_reasoning is True
        assert info.provider == "vllm"
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_system_messages is True
        assert info.supports_extended_thinking is False
        assert info.requires_thinking_budget is False

    def test_deepseek_r1_distill_detection(self):
        """Test deepseek-r1-distill is detected as reasoning model."""
        info = get_vllm_reasoning_model_info("deepseek-r1-distill")
        assert info.is_reasoning is True
        assert info.provider == "vllm"

    def test_deepseek_r1_distill_llama_detection(self):
        """Test deepseek-r1-distill-llama-8b is detected."""
        info = get_vllm_reasoning_model_info("deepseek-r1-distill-llama-8b")
        assert info.is_reasoning is True
        assert info.provider == "vllm"

    def test_deepseek_r1_case_insensitive(self):
        """Test case-insensitive detection."""
        info1 = get_vllm_reasoning_model_info("DEEPSEEK-R1")
        info2 = get_vllm_reasoning_model_info("DeepSeek-R1-Distill")
        assert info1.is_reasoning is True
        assert info2.is_reasoning is True

    def test_deepseek_r1_underscore_detection(self):
        """Test deepseek_r1 with underscore is detected."""
        info = get_vllm_reasoning_model_info("deepseek_r1")
        assert info.is_reasoning is True
        assert info.provider == "vllm"

    def test_llama_not_reasoning(self):
        """Test llama is not detected as reasoning model."""
        info = get_vllm_reasoning_model_info("llama-3.2-1b")
        assert info.is_reasoning is False
        assert info.provider == "vllm"

    def test_mistral_not_reasoning(self):
        """Test mistral is not detected as reasoning model."""
        info = get_vllm_reasoning_model_info("mistral-7b-instruct")
        assert info.is_reasoning is False

    def test_qwen_not_reasoning(self):
        """Test qwen is not detected as reasoning model."""
        info = get_vllm_reasoning_model_info("qwen-7b")
        assert info.is_reasoning is False


class TestDeepSeekR1VLLMCost:
    """Test cost calculation for DeepSeek-R1 on vLLM (free by default)."""

    def test_deepseek_r1_cost_is_free_by_default(self):
        """Test DeepSeek-R1 on vLLM is free by default (self-hosted)."""
        provider = VLLMProvider()
        cost = provider.estimate_cost(tokens=1000000, model="deepseek-r1")
        assert cost == 0.0

    def test_all_vllm_models_are_free_by_default(self):
        """Test all vLLM models are free by default."""
        provider = VLLMProvider()
        models = ["deepseek-r1", "deepseek-r1-distill", "llama-3.2-1b", "mistral-7b"]

        for model in models:
            cost = provider.estimate_cost(tokens=1000000, model=model)
            assert cost == 0.0

    def test_vllm_large_tokens_still_free(self):
        """Test large token counts are still free."""
        provider = VLLMProvider()
        cost = provider.estimate_cost(tokens=10000000, model="deepseek-r1")
        assert cost == 0.0


class TestMultiProviderDeepSeekR1:
    """Test DeepSeek-R1 across multiple providers."""

    def test_deepseek_r1_detected_in_both_providers(self):
        """Test DeepSeek-R1 is detected in both Ollama and vLLM."""
        ollama_info = get_ollama_reasoning_model_info("deepseek-r1")
        vllm_info = get_vllm_reasoning_model_info("deepseek-r1")

        assert ollama_info.is_reasoning is True
        assert vllm_info.is_reasoning is True
        assert ollama_info.provider == "ollama"
        assert vllm_info.provider == "vllm"

    def test_consistent_capabilities_across_providers(self):
        """Test DeepSeek-R1 has consistent capabilities across providers."""
        ollama_info = get_ollama_reasoning_model_info("deepseek-r1")
        vllm_info = get_vllm_reasoning_model_info("deepseek-r1")

        assert ollama_info.supports_streaming == vllm_info.supports_streaming
        assert ollama_info.supports_tools == vllm_info.supports_tools
        assert ollama_info.supports_system_messages == vllm_info.supports_system_messages
        assert ollama_info.supports_extended_thinking == vllm_info.supports_extended_thinking
        assert ollama_info.requires_thinking_budget == vllm_info.requires_thinking_budget

    def test_both_local_providers_are_free(self):
        """Test both local providers (Ollama and vLLM) are free."""
        ollama_provider = OllamaProvider()
        vllm_provider = VLLMProvider()

        ollama_cost = ollama_provider.estimate_cost(tokens=1000000, model="deepseek-r1")
        vllm_cost = vllm_provider.estimate_cost(tokens=1000000, model="deepseek-r1")

        assert ollama_cost == 0.0
        assert vllm_cost == 0.0
