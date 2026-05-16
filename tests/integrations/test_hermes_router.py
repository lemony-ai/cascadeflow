import pytest

from cascadeflow.integrations.hermes import (
    HermesDelegationRequest,
    HermesDelegationRouter,
    HermesRouteProfile,
    HermesRoutingConfig,
    HermesTaskClassification,
)


class StaticClassifier:
    def __init__(
        self,
        *,
        domain="code",
        complexity="moderate",
        confidence=0.8,
        reason="static",
        topic=None,
    ):
        self.classification = HermesTaskClassification(
            domain=domain,
            complexity=complexity,
            confidence=confidence,
            reason=reason,
            topic=topic,
        )

    def classify(self, request):
        return self.classification


class FailingClassifier:
    def classify(self, request):
        raise RuntimeError("classification failed")


def _router(config, **classification):
    return HermesDelegationRouter(
        config=HermesRoutingConfig.from_dict(config),
        classifier=StaticClassifier(**classification),
    )


def _request(**kwargs):
    return HermesDelegationRequest(
        goal=kwargs.pop("goal", "Implement a typed API client and unit tests"),
        toolsets=kwargs.pop("toolsets", ("terminal", "git")),
        loaded_skills=kwargs.pop("loaded_skills", ("python",)),
        **kwargs,
    )


def test_disabled_config_returns_inherit_decision():
    router = _router({"enabled": False})

    decision = router.route_delegation(_request())

    assert decision.action == "inherit"
    assert decision.reason == "cascadeflow_disabled"
    assert decision.applies is False


def test_observe_mode_returns_recommendation_without_applying_it():
    router = _router(
        {
            "enabled": True,
            "mode": "observe",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "high",
                }
            },
        }
    )

    decision = router.route_delegation(_request())

    assert decision.action == "inherit"
    assert decision.provider == "nous"
    assert decision.model == "nous/hermes-4.1"
    assert decision.reasoning_effort == "high"
    assert decision.metadata["mode"] == "observe"
    assert decision.metadata["would_route"] is True
    assert decision.metadata["applied"] is False


def test_route_mode_applies_matching_domain_profile():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "high",
                }
            },
        },
        domain="code",
        complexity="hard",
        confidence=0.91,
        topic="code",
    )

    decision = router.route_delegation(_request())

    assert decision.action == "route"
    assert decision.provider == "nous"
    assert decision.model == "nous/hermes-4.1"
    assert decision.domain == "code"
    assert decision.complexity == "hard"
    assert decision.confidence == pytest.approx(0.91)
    assert decision.metadata["loaded_skills"] == ["python"]


def test_debugging_domain_can_use_code_route():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "high",
                }
            },
        },
        domain="debugging",
        complexity="hard",
        confidence=0.9,
        topic="debugging",
    )

    decision = router.route_delegation(_request(goal="Debug the failing regression"))

    assert decision.action == "route"
    assert decision.domain == "debugging"
    assert decision.topic == "debugging"
    assert decision.model == "nous/hermes-4.1"


def test_skill_metadata_profile_takes_precedence_over_classifier():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "simple": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "reasoning_effort": "low",
                }
            },
        },
        domain="simple",
        complexity="simple",
        confidence=0.7,
    )
    request = _request(
        skill_metadata={
            "cascadeflow": {
                "provider": "anthropic",
                "model": "claude-opus-4.1",
                "reasoning_effort": "high",
                "domain": "legal",
                "topic": "contract-review",
                "confidence": 0.99,
            }
        }
    )

    decision = router.route_delegation(request)

    assert decision.action == "route"
    assert decision.source == "skill_metadata"
    assert decision.provider == "anthropic"
    assert decision.model == "claude-opus-4.1"
    assert decision.domain == "legal"
    assert decision.topic == "contract-review"


def test_simple_complexity_uses_simple_route():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "simple": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "reasoning_effort": "low",
                }
            },
        },
        domain="general",
        complexity="simple",
        confidence=0.73,
    )

    decision = router.route_delegation(_request(goal="Rename this variable"))

    assert decision.action == "route"
    assert decision.model == "gpt-4.1-mini"
    assert decision.complexity == "simple"


def test_high_stakes_domain_without_matching_route_inherits():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                }
            },
        },
        domain="medical",
        complexity="hard",
        confidence=0.86,
    )

    decision = router.route_delegation(_request(goal="Review this patient diagnosis note"))

    assert decision.action == "inherit"
    assert decision.reason == "high_stakes_domain_unconfigured"
    assert decision.domain == "medical"


def test_high_stakes_domain_does_not_fall_back_to_complexity_route():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "simple": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "reasoning_effort": "low",
                },
                "general": {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "reasoning_effort": "medium",
                },
            },
        },
        domain="legal",
        complexity="simple",
        confidence=0.86,
    )

    decision = router.route_delegation(_request(goal="Review this contract clause"))

    assert decision.action == "inherit"
    assert decision.reason == "high_stakes_domain_unconfigured"
    assert decision.domain == "legal"
    assert decision.model is None


def test_parent_loaded_skills_do_not_override_task_domain():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "high",
                }
            },
        }
    )
    request = HermesDelegationRequest(
        goal="Review this indemnity clause for legal risk",
        loaded_skills=("python", "debugging"),
    )

    decision = router.route_delegation(request)

    assert decision.action == "inherit"
    assert decision.reason == "high_stakes_domain_unconfigured"
    assert decision.domain == "legal"
    assert decision.metadata["loaded_skills"] == ["python", "debugging"]


def test_confidence_below_threshold_inherits_but_keeps_audit_recommendation():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "min_confidence": 0.9,
            "routes": {
                "research": {
                    "provider": "nous",
                    "model": "nous/hermes-research",
                    "reasoning_effort": "medium",
                }
            },
        },
        domain="research",
        complexity="moderate",
        confidence=0.74,
    )

    decision = router.route_delegation(_request(goal="Research the current market"))

    assert decision.action == "inherit"
    assert decision.reason == "confidence_below_threshold"
    assert decision.model == "nous/hermes-research"
    assert decision.metadata["would_route"] is True
    assert decision.metadata["applied"] is False


def test_route_provider_model_can_be_disabled_independently():
    router = _router(
        {
            "enabled": True,
            "mode": "route",
            "route_provider_model": False,
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "reasoning_effort": "high",
                }
            },
        }
    )

    decision = router.route_delegation(_request())

    assert decision.action == "route"
    assert decision.provider is None
    assert decision.model is None
    assert decision.reasoning_effort == "high"


def test_router_never_raises_on_classifier_failure():
    router = HermesDelegationRouter(
        config=HermesRoutingConfig(
            enabled=True,
            mode="route",
            routes={"code": HermesRouteProfile(provider="nous", model="x")},
        ),
        classifier=FailingClassifier(),
    )

    decision = router.route_delegation(_request())

    assert decision.action == "inherit"
    assert decision.reason == "router_error"
    assert decision.metadata["error"] == "RuntimeError"
