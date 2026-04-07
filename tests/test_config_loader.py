import os
from unittest.mock import patch

from cascadeflow.config_loader import (
    _resolve_env_vars,
    create_agent_from_config,
    load_config,
    parse_channel_failover,
    parse_channel_models,
    parse_channel_strategies,
)


def test_parse_channel_models_accepts_str_and_list():
    parsed = parse_channel_models(
        {
            "heartbeat": "gpt-4o-mini",
            "cron": ["gpt-4o-mini", "gpt-4o"],
        }
    )

    assert parsed["heartbeat"] == ["gpt-4o-mini"]
    assert parsed["cron"] == ["gpt-4o-mini", "gpt-4o"]


def test_parse_channel_models_accepts_dict():
    parsed = parse_channel_models(
        {"heartbeat": {"models": "gpt-4o-mini", "strategy": "direct_cheap"}}
    )

    assert parsed["heartbeat"] == ["gpt-4o-mini"]


def test_parse_channel_strategies_accepts_dict():
    parsed = parse_channel_strategies(
        {"heartbeat": {"models": "gpt-4o-mini", "strategy": "direct_cheap"}}
    )

    assert parsed == {"heartbeat": "direct_cheap"}


def test_parse_channel_failover_accepts_strings():
    parsed = parse_channel_failover({"voice": "heartbeat"})
    assert parsed == {"voice": "heartbeat"}


def test_create_agent_from_config_includes_channels():
    config = {
        "models": [
            {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
            {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
        ],
        "channels": {
            "heartbeat": {"models": "gpt-4o-mini", "strategy": "direct_cheap"},
            "cron": ["gpt-4o-mini"],
        },
        "channel_failover": {"voice": "heartbeat"},
    }

    agent = create_agent_from_config(config)

    assert agent.rule_engine.channel_models["heartbeat"] == ["gpt-4o-mini"]
    assert agent.rule_engine.channel_models["cron"] == ["gpt-4o-mini"]
    assert agent.rule_engine.channel_failover["voice"] == "heartbeat"
    assert agent.rule_engine.channel_strategies["heartbeat"] == "direct_cheap"


# ==================== Environment Variable Resolution Tests ====================


def test_resolve_env_vars_simple_string():
    """Test resolving a single env var in a string."""
    with patch.dict(os.environ, {"MY_API_KEY": "sk-resolved-key"}):
        result = _resolve_env_vars("${env:MY_API_KEY}")
        assert result == "sk-resolved-key"


def test_resolve_env_vars_in_dict():
    """Test resolving env vars in a nested dict."""
    with patch.dict(os.environ, {"OPENAI_KEY": "sk-openai-123"}):
        config = {"api_key": "${env:OPENAI_KEY}", "name": "gpt-4o"}
        result = _resolve_env_vars(config)
        assert result["api_key"] == "sk-openai-123"
        assert result["name"] == "gpt-4o"


def test_resolve_env_vars_in_list():
    """Test resolving env vars in a list."""
    with patch.dict(os.environ, {"KEY_A": "val-a", "KEY_B": "val-b"}):
        result = _resolve_env_vars(["${env:KEY_A}", "${env:KEY_B}", "literal"])
        assert result == ["val-a", "val-b", "literal"]


def test_resolve_env_vars_nested():
    """Test resolving env vars in deeply nested structures."""
    with patch.dict(os.environ, {"SECRET": "s3cr3t"}):
        config = {"models": [{"name": "test", "api_key": "${env:SECRET}"}]}
        result = _resolve_env_vars(config)
        assert result["models"][0]["api_key"] == "s3cr3t"
        assert result["models"][0]["name"] == "test"


def test_resolve_env_vars_missing_var_left_as_is():
    """Test that missing env vars are left as-is with a warning."""
    with patch.dict(os.environ, {}, clear=True):
        result = _resolve_env_vars("${env:NONEXISTENT_VAR}")
        assert result == "${env:NONEXISTENT_VAR}"


def test_resolve_env_vars_partial_string():
    """Test resolving env var embedded in a larger string."""
    with patch.dict(os.environ, {"HOST": "localhost", "PORT": "8080"}):
        result = _resolve_env_vars("http://${env:HOST}:${env:PORT}/v1")
        assert result == "http://localhost:8080/v1"


def test_resolve_env_vars_non_string_passthrough():
    """Test that non-string values pass through unchanged."""
    assert _resolve_env_vars(42) == 42
    assert _resolve_env_vars(3.14) == 3.14
    assert _resolve_env_vars(True) is True
    assert _resolve_env_vars(None) is None


def test_resolve_env_vars_no_pattern():
    """Test that strings without env patterns pass through unchanged."""
    assert _resolve_env_vars("just a normal string") == "just a normal string"
    assert _resolve_env_vars("sk-my-api-key") == "sk-my-api-key"


# ==================== Integration: load_config with env var resolution ====================


def test_load_config_resolves_env_vars_yaml(tmp_path):
    """Integration test: load_config() resolves ${env:VAR} in a YAML file."""
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(
        "models:\n"
        "  - name: gpt-4o\n"
        "    provider: openai\n"
        "    cost: 0.0025\n"
        '    api_key: "${env:TEST_OPENAI_KEY}"\n'
        '    base_url: "${env:TEST_BASE_URL}/v1"\n'
    )

    with patch.dict(
        os.environ, {"TEST_OPENAI_KEY": "sk-yaml-resolved", "TEST_BASE_URL": "https://proxy.test"}
    ):
        config = load_config(yaml_file)

    assert config["models"][0]["api_key"] == "sk-yaml-resolved"
    assert config["models"][0]["base_url"] == "https://proxy.test/v1"
    assert config["models"][0]["name"] == "gpt-4o"


def test_load_config_resolves_env_vars_json(tmp_path):
    """Integration test: load_config() resolves ${env:VAR} in a JSON file."""
    json_file = tmp_path / "test_config.json"
    json_file.write_text(
        '{"models": [{"name": "test", "provider": "openai", '
        '"api_key": "${env:TEST_JSON_KEY}", "cost": 0.01}]}'
    )

    with patch.dict(os.environ, {"TEST_JSON_KEY": "sk-json-resolved"}):
        config = load_config(json_file)

    assert config["models"][0]["api_key"] == "sk-json-resolved"


def test_load_config_missing_env_var_survives(tmp_path):
    """Integration test: missing env vars don't crash load_config()."""
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(
        "models:\n"
        "  - name: test\n"
        "    provider: openai\n"
        "    cost: 0.01\n"
        '    api_key: "${env:TOTALLY_MISSING_VAR}"\n'
    )

    with patch.dict(os.environ, {}, clear=True):
        config = load_config(yaml_file)

    assert config["models"][0]["api_key"] == "${env:TOTALLY_MISSING_VAR}"
