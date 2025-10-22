"""Test suite for smart presets."""

from unittest.mock import MagicMock, patch

import pytest

from cascadeflow.presets import CascadePresets


class TestCascadePresets:
    """Test cascade presets."""

    def test_detect_ollama_success(self):
        """Test successful Ollama detection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3:8b"}, {"name": "codellama:7b"}]
        }

        with patch("httpx.get", return_value=mock_response):
            models = CascadePresets._detect_ollama()

        assert len(models) == 2
        assert models[0].name == "llama3:8b"
        assert models[0].provider == "ollama"
        assert models[0].cost == 0.0

    def test_detect_ollama_failure(self):
        """Test Ollama detection failure."""
        with patch("httpx.get", side_effect=Exception("Connection failed")):
            models = CascadePresets._detect_ollama()

        assert len(models) == 0

    def test_detect_ollama_code_domain(self):
        """Test code domain detection for codellama."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "codellama:7b"}]}

        with patch("httpx.get", return_value=mock_response):
            models = CascadePresets._detect_ollama()

        assert "code" in models[0].domains

    @patch.dict("os.environ", {}, clear=True)
    def test_auto_detect_no_providers(self):
        """Test auto-detect with no providers available."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            with pytest.raises(ValueError, match="No providers detected"):
                CascadePresets.auto_detect_models()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_auto_detect_openai(self):
        """Test auto-detect with OpenAI."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            models = CascadePresets.auto_detect_models()

        model_names = [m.name for m in models]
        assert "gpt-3.5-turbo" in model_names
        assert "gpt-4" in model_names

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_auto_detect_anthropic(self):
        """Test auto-detect with Anthropic."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            models = CascadePresets.auto_detect_models()

        model_names = [m.name for m in models]
        assert "claude-3-haiku" in model_names
        assert "claude-3-sonnet" in model_names

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    def test_auto_detect_groq(self):
        """Test auto-detect with Groq."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            models = CascadePresets.auto_detect_models()

        model_names = [m.name for m in models]
        assert "llama-3.1-70b-versatile" in model_names

    @patch.dict("os.environ", {"GROQ_API_KEY": "test-key"})
    def test_cost_optimized_models(self):
        """Test cost-optimized preset."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            models = CascadePresets.cost_optimized_models()

        # Should prioritize free models
        assert all(m.cost == 0.0 or m.cost < 0.01 for m in models)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"})
    def test_quality_optimized_models(self):
        """Test quality-optimized preset."""
        models = CascadePresets.quality_optimized_models()

        # Should include high-quality models
        assert any(m.quality_score >= 0.90 for m in models)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_balanced_models(self):
        """Test balanced preset."""
        with patch("cascadeflow.presets.CascadePresets._detect_ollama", return_value=[]):
            models = CascadePresets.balanced_models()

        # Should be same as auto_detect
        assert len(models) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
