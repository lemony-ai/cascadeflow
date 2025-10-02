"""Tests for configuration classes."""

import pytest
from cascadeflow import ModelConfig, CascadeConfig, UserTier
from cascadeflow.exceptions import ValidationError


class TestModelConfig:
    """Tests for ModelConfig class."""

    def test_basic_creation(self):
        """Test basic ModelConfig creation."""
        config = ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.002
        )

        assert config.name == "gpt-3.5-turbo"
        assert config.provider == "openai"
        assert config.cost == 0.002
        assert config.max_tokens == 4096  # Default
        assert config.temperature == 0.7  # Default

    def test_with_keywords_and_domains(self):
        """Test ModelConfig with keywords and domains."""
        config = ModelConfig(
            name="codellama",
            provider="ollama",
            cost=0.0,
            keywords=["code", "programming"],
            domains=["code"]
        )

        assert "code" in config.keywords
        assert "code" in config.domains
        assert config.cost == 0.0

    def test_cost_validation_negative(self):
        """Test that negative cost raises error."""
        with pytest.raises(ValueError, match="Cost must be non-negative"):
            ModelConfig(
                name="test",
                provider="openai",
                cost=-1.0
            )

    def test_provider_validation_invalid(self):
        """Test that invalid provider raises error."""
        with pytest.raises(ValueError, match="Provider must be one of"):
            ModelConfig(
                name="test",
                provider="invalid_provider",
                cost=0.0
            )

    def test_provider_validation_case_insensitive(self):
        """Test that provider validation is case-insensitive."""
        config = ModelConfig(
            name="test",
            provider="OpenAI",  # Mixed case
            cost=0.0
        )
        assert config.provider == "openai"  # Converted to lowercase

    def test_temperature_validation(self):
        """Test temperature validation."""
        # Valid temperatures
        ModelConfig(name="test", provider="openai", cost=0.0, temperature=0.0)
        ModelConfig(name="test", provider="openai", cost=0.0, temperature=1.0)
        ModelConfig(name="test", provider="openai", cost=0.0, temperature=2.0)

        # Invalid temperature
        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            ModelConfig(name="test", provider="openai", cost=0.0, temperature=3.0)

    def test_max_tokens_validation(self):
        """Test max_tokens validation."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            ModelConfig(name="test", provider="openai", cost=0.0, max_tokens=0)


class TestCascadeConfig:
    """Tests for CascadeConfig class."""

    def test_defaults(self):
        """Test CascadeConfig default values."""
        config = CascadeConfig()

        assert config.quality_threshold == 0.7
        assert config.max_budget == 1.0
        assert config.max_retries == 2
        assert config.timeout == 30
        assert config.use_speculative == True  # Important!
        assert config.routing_strategy == "adaptive"

    def test_custom_values(self):
        """Test CascadeConfig with custom values."""
        config = CascadeConfig(
            quality_threshold=0.85,
            max_budget=0.05,
            use_speculative=True,
            routing_strategy="semantic"
        )

        assert config.quality_threshold == 0.85
        assert config.max_budget == 0.05
        assert config.routing_strategy == "semantic"

    def test_quality_threshold_validation(self):
        """Test quality threshold validation."""
        with pytest.raises(ValueError, match="Quality threshold must be between 0 and 1"):
            CascadeConfig(quality_threshold=1.5)

        with pytest.raises(ValueError, match="Quality threshold must be between 0 and 1"):
            CascadeConfig(quality_threshold=-0.1)

    def test_budget_validation(self):
        """Test budget validation."""
        with pytest.raises(ValueError, match="Max budget must be non-negative"):
            CascadeConfig(max_budget=-1.0)

    def test_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            CascadeConfig(timeout=0)


class TestUserTier:
    """Tests for UserTier class."""

    def test_basic_creation(self):
        """Test basic UserTier creation."""
        tier = UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.9
        )

        assert tier.name == "premium"
        assert tier.max_budget == 0.10
        assert tier.quality_threshold == 0.9

    def test_to_cascade_config(self):
        """Test converting UserTier to CascadeConfig params."""
        tier = UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.9,
            timeout=60,
            max_retries=3
        )

        cascade_params = tier.to_cascade_config()

        assert cascade_params["max_budget"] == 0.10
        assert cascade_params["quality_threshold"] == 0.9
        assert cascade_params["timeout"] == 60
        assert cascade_params["max_retries"] == 3

    def test_allows_model_wildcard(self):
        """Test allows_model with wildcard."""
        tier = UserTier(allowed_models=["*"])

        assert tier.allows_model("gpt-4") == True
        assert tier.allows_model("anything") == True

    def test_allows_model_specific(self):
        """Test allows_model with specific models."""
        tier = UserTier(allowed_models=["gpt-3.5-turbo", "llama3:8b"])

        assert tier.allows_model("gpt-3.5-turbo") == True
        assert tier.allows_model("llama3:8b") == True
        assert tier.allows_model("gpt-4") == False

    def test_allows_model_excluded(self):
        """Test allows_model with exclusions."""
        tier = UserTier(
            allowed_models=["*"],
            excluded_models=["gpt-4"]
        )

        assert tier.allows_model("gpt-3.5-turbo") == True
        assert tier.allows_model("gpt-4") == False

    def test_default_values(self):
        """Test UserTier default values."""
        tier = UserTier()

        assert tier.name == "free"
        assert tier.max_budget == 0.001
        assert tier.quality_threshold == 0.6
        assert tier.allowed_models == ["*"]
        assert tier.use_speculative == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])