"""Tests for code response leniency in quality validation."""

from cascadeflow.quality.quality import QualityConfig, QualityValidator


def test_code_response_leniency_passes():
    validator = QualityValidator(config=QualityConfig.for_cascade())
    query = (
        "Write a Python function that returns the sum of all even numbers in a list."
    )
    response = "def sum_even(numbers: list[int]) -> int:\n    return sum(n for n in numbers if n % 2 == 0)"

    result = validator.validate(
        response,
        query,
        confidence=0.8,
        complexity="moderate",
        threshold_override=0.7,
    )

    assert result.passed is True
    assert result.details.get("code_mode") is True
