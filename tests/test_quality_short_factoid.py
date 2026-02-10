"""Tests for short factoid leniency in quality validation."""

from cascadeflow.quality.quality import QualityConfig, QualityValidator


def test_short_factoid_leniency_passes():
    validator = QualityValidator(config=QualityConfig.for_cascade())
    query = "What is the capital of France?"
    response = "Paris."

    result = validator.validate(
        response,
        query,
        confidence=0.8,
        complexity="simple",
        threshold_override=0.7,
    )

    assert result.passed is True
    assert result.details.get("short_factoid_mode") is True
