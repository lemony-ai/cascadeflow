from cascadeflow.integrations.hermes import (
    extract_cascadeflow_skill_metadata,
    profile_from_skill_metadata,
)


def test_extracts_direct_cascadeflow_skill_metadata():
    metadata = {
        "name": "python-code",
        "cascadeflow": {
            "provider": "nous",
            "model": "nous/hermes-4.1",
            "reasoning_effort": "high",
            "domain": "code",
        },
    }

    block = extract_cascadeflow_skill_metadata(metadata)

    assert block["provider"] == "nous"
    assert block["model"] == "nous/hermes-4.1"


def test_extracts_nested_hermes_cascadeflow_metadata():
    metadata = {
        "metadata": {
            "hermes": {
                "cascadeflow": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "reasoning_effort": "low",
                    "domain": "research",
                }
            }
        }
    }

    profile = profile_from_skill_metadata(metadata)

    assert profile is not None
    assert profile.provider == "openai"
    assert profile.model == "gpt-4.1-mini"
    assert profile.reasoning_effort == "low"
    assert profile.domain == "research"


def test_missing_skill_metadata_returns_no_profile():
    assert extract_cascadeflow_skill_metadata({"name": "plain-skill"}) == {}
    assert profile_from_skill_metadata({"name": "plain-skill"}) is None

