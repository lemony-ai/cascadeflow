from cascadeflow.config_loader import (
    create_agent_from_config,
    parse_channel_failover,
    parse_channel_models,
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
            "heartbeat": "gpt-4o-mini",
            "cron": ["gpt-4o-mini"],
        },
        "channel_failover": {"voice": "heartbeat"},
    }

    agent = create_agent_from_config(config)

    assert agent.rule_engine.channel_models["heartbeat"] == ["gpt-4o-mini"]
    assert agent.rule_engine.channel_models["cron"] == ["gpt-4o-mini"]
    assert agent.rule_engine.channel_failover["voice"] == "heartbeat"
