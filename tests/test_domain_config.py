from cascadeflow.schema.domain_config import get_builtin_domain_config


def test_builtin_creative_threshold_relaxed():
    config = get_builtin_domain_config("creative")
    assert config is not None
    assert config.threshold == 0.50


def test_builtin_comparison_threshold():
    config = get_builtin_domain_config("comparison")
    assert config is not None
    assert config.threshold == 0.52
    assert "moderate" in (config.cascade_complexities or [])


def test_builtin_factual_requires_verifier():
    config = get_builtin_domain_config("factual")
    assert config is not None
    assert config.require_verifier is True
    assert config.threshold == 0.9

