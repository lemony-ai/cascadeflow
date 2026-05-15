from cascadeflow.integrations.hermes import HermesRouteProfile, HermesRoutingConfig
from cascadeflow.integrations import HERMES_AVAILABLE, get_integration_info


def test_routing_config_defaults_to_disabled_observe_mode():
    config = HermesRoutingConfig.from_dict(None)

    assert config.enabled is False
    assert config.mode == "observe"
    assert config.routes == {}


def test_routing_config_sanitizes_invalid_values():
    config = HermesRoutingConfig.from_dict(
        {
            "enabled": "yes",
            "mode": "invalid",
            "min_confidence": "not-a-number",
            "route_provider_model": "false",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "turbo",
                    "confidence": 2,
                }
            },
        }
    )

    assert config.enabled is True
    assert config.mode == "observe"
    assert config.min_confidence == 0.6
    assert config.route_provider_model is False
    assert config.routes["code"].reasoning_effort is None
    assert config.routes["code"].confidence == 1.0


def test_route_profile_accepts_known_reasoning_effort():
    profile = HermesRouteProfile.from_dict(
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "reasoning_effort": "LOW",
        }
    )

    assert profile.reasoning_effort == "low"


def test_hermes_integration_is_discoverable():
    info = get_integration_info()

    assert HERMES_AVAILABLE is True
    assert info["hermes_available"] is True
    assert info["capabilities"]["hermes"] is True
