"""Edge-case / fuzz sweep for HermesDelegationRouter.

Targets:
- route_key fallback chain (domain → debugging→code → complexity → simple/hard → general)
- no_matching_route path
- malformed / partial configs via from_dict
- skill_metadata variations
- request crash paths
"""

import pytest

from cascadeflow.integrations.hermes import (
    HermesDelegationRequest,
    HermesDelegationRouter,
    HermesRoutingConfig,
)


def _req(**kw):
    return HermesDelegationRequest(goal=kw.pop("goal", "Implement the python API"), **kw)


# --- route_key fallback chain ---


def test_debugging_domain_falls_back_to_code_route():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "routes": {"code": {"provider": "nous", "model": "nous/hermes-4.1"}},
        }
    )
    decision = router.route_delegation(
        _req(goal="Investigate the failing test traceback and find the root cause")
    )
    assert decision.action == "route"
    assert decision.provider == "nous"
    assert decision.domain == "debugging"


def test_simple_complexity_falls_back_to_simple_route():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "min_confidence": 0.0,
            "routes": {"simple": {"provider": "nous", "model": "nous/hermes-flash"}},
        }
    )
    # Trivial goal → general/simple complexity → simple route
    decision = router.route_delegation(_req(goal="hi"))
    assert decision.action == "route"
    assert decision.model == "nous/hermes-flash"


def test_general_route_used_when_nothing_else_matches():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "min_confidence": 0.0,
            "routes": {"general": {"provider": "nous", "model": "nous/hermes-general"}},
        }
    )
    # Creative goal with no creative route → falls back to general
    decision = router.route_delegation(_req(goal="Write a creative brand headline"))
    assert decision.action == "route"
    assert decision.model == "nous/hermes-general"


def test_no_matching_route_returns_inherit_with_no_matching_route_reason():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "routes": {"code": {"provider": "nous", "model": "nous/hermes-4.1"}},
        }
    )
    decision = router.route_delegation(_req(goal="Write a creative brand headline"))
    assert decision.action == "inherit"
    assert decision.reason == "no_matching_route"
    assert decision.domain == "creative"


# --- malformed config ---


def test_from_dict_handles_none():
    router = HermesDelegationRouter.from_dict(None)
    decision = router.route_delegation(_req())
    # default config has enabled=False → inherit
    assert decision.action == "inherit"


def test_from_dict_handles_empty():
    router = HermesDelegationRouter.from_dict({})
    decision = router.route_delegation(_req())
    assert decision.action == "inherit"


def test_from_dict_ignores_unknown_keys():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "this_key_does_not_exist": "garbage",
            "routes": {"code": {"provider": "nous", "model": "nous/hermes-4.1"}},
        }
    )
    decision = router.route_delegation(_req())
    assert decision.action == "route"


def test_from_dict_handles_malformed_route_profile():
    # route value is not a dict → config should tolerate or skip
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "routes": {"code": "this is not a dict"},
        }
    )
    decision = router.route_delegation(_req())
    # Either gracefully skipped or surfaced via "router_error" fallback
    assert decision.action == "inherit"


# --- skill_metadata variations ---


def test_skill_metadata_route_overrides_classifier():
    router = HermesDelegationRouter.from_dict({"enabled": True, "mode": "route", "routes": {}})
    decision = router.route_delegation(
        _req(
            goal="Some legal contract review",  # would otherwise be inherit/legal
            skill_metadata={
                "cascadeflow": {
                    "provider": "nous",
                    "model": "nous/hermes-explicit",
                    "domain": "compliance",
                }
            },
        )
    )
    # explicit skill metadata wins
    assert decision.source == "skill_metadata"
    assert decision.model == "nous/hermes-explicit"


def test_empty_skill_metadata_falls_through_to_classifier():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "routes": {"code": {"provider": "nous", "model": "nous/hermes-4.1"}},
        }
    )
    decision = router.route_delegation(_req(goal="Implement the python API", skill_metadata={}))
    assert decision.source == "classifier"
    assert decision.action == "route"


def test_skill_metadata_with_unknown_fields_is_tolerated():
    router = HermesDelegationRouter.from_dict({"enabled": True, "mode": "route", "routes": {}})
    decision = router.route_delegation(
        _req(
            goal="any",
            skill_metadata={
                "cascadeflow": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "this_field_is_unknown": "garbage",
                    "nested": {"more": "garbage"},
                }
            },
        )
    )
    assert decision.source == "skill_metadata"


# --- request crash paths ---


def test_router_returns_fallback_decision_on_unexpected_exception():
    router = HermesDelegationRouter(config=HermesRoutingConfig(enabled=True))
    # Inject a request that lies about its toolsets type (not str-coerced)
    request = _req(goal="any")

    # Force classifier to blow up by stubbing
    class BoomClassifier:
        def classify(self, request):
            raise RuntimeError("kaboom")

    router.classifier = BoomClassifier()
    decision = router.route_delegation(request)
    assert decision.action == "inherit"
    assert decision.source == "fallback"
    assert decision.reason == "router_error"
    assert "RuntimeError" in decision.metadata.get("error", "")


# --- observe mode ---


def test_observe_mode_returns_inherit_but_keeps_route_metadata():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "observe",
            "min_confidence": 0.0,
            "routes": {"code": {"provider": "nous", "model": "nous/hermes-4.1"}},
        }
    )
    decision = router.route_delegation(_req(goal="Implement the python API"))
    assert decision.action == "inherit"
    # In observe mode, recommended provider/model should be None (not applied),
    # but the metadata about the would-be-route is preserved on the decision
    assert decision.domain == "code"


# --- per-route confidence ---


def test_per_route_confidence_can_exceed_classifier_confidence():
    router = HermesDelegationRouter.from_dict(
        {
            "enabled": True,
            "mode": "route",
            "min_confidence": 0.0,
            "routes": {
                "code": {
                    "provider": "nous",
                    "model": "nous/hermes-4.1",
                    "confidence": 0.99,
                }
            },
        }
    )
    decision = router.route_delegation(_req(goal="Implement the python API"))
    assert decision.confidence >= 0.99
