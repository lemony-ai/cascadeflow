import pytest

from cascadeflow.quality.complexity import QueryComplexity
from cascadeflow.routing.base import RoutingStrategy
from cascadeflow.rules import RuleEngine
from cascadeflow.rules.context import RuleContext
from cascadeflow.schema.config import LatencyProfile, OptimizationWeights, UserTier, WorkflowProfile
from cascadeflow.schema.domain_config import DomainConfig


def _make_tier(name: str = "pro") -> UserTier:
    return UserTier(
        name=name,
        latency=LatencyProfile(
            max_total_ms=1000,
            max_per_model_ms=800,
            prefer_parallel=False,
            skip_cascade_threshold=0,
        ),
        optimization=OptimizationWeights(cost=0.2, speed=0.3, quality=0.5),
        max_budget=0.05,
        allowed_models=["m1"],
        preferred_models=["m2"],
        exclude_models=["m3"],
        excluded_models=["m4"],
        quality_threshold=0.8,
    )


def _make_workflow(name: str = "draft") -> WorkflowProfile:
    return WorkflowProfile(
        name=name,
        force_models=["m1"],
        preferred_models=["m2"],
        exclude_models=["m3"],
        quality_threshold_override=0.4,
        max_budget_override=0.01,
    )


def test_domain_requires_verifier():
    engine = RuleEngine()
    domain_config = DomainConfig(drafter="draft", verifier="verify", require_verifier=True)
    context = RuleContext(
        query="check",
        detected_domain="code",
        domain_config=domain_config,
        domain_confidence=0.9,
        complexity=QueryComplexity.TRIVIAL,
        complexity_confidence=0.8,
    )

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.DIRECT_BEST
    assert "domain 'code'" in decision.reason
    assert decision.metadata.get("rule") == "domain_routing"


def test_domain_cascade_complexity_match():
    engine = RuleEngine()
    domain_config = DomainConfig(
        drafter="draft",
        verifier="verify",
        cascade_complexities=["trivial", "simple"],
    )
    context = RuleContext(
        query="easy",
        detected_domain="general",
        domain_config=domain_config,
        domain_confidence=0.7,
        complexity=QueryComplexity.TRIVIAL,
        complexity_confidence=0.9,
    )

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.CASCADE


def test_domain_cascade_complexity_miss():
    engine = RuleEngine()
    domain_config = DomainConfig(
        drafter="draft",
        verifier="verify",
        cascade_complexities=["trivial", "simple"],
    )
    context = RuleContext(
        query="hard",
        detected_domain="general",
        domain_config=domain_config,
        domain_confidence=0.7,
        complexity=QueryComplexity.EXPERT,
        complexity_confidence=0.9,
    )

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.DIRECT_BEST


def test_tier_rules_apply_constraints():
    engine = RuleEngine()
    tier = _make_tier()
    context = RuleContext(query="hi", tier_config=tier)

    decision = engine.decide(context)

    assert decision is not None
    assert decision.allowed_models == ["m1"]
    assert set(decision.excluded_models or []) == {"m3", "m4"}
    assert decision.preferred_models == ["m2"]
    assert decision.quality_threshold == pytest.approx(0.8)
    assert decision.max_budget == pytest.approx(0.05)


def test_workflow_rules_apply_overrides():
    engine = RuleEngine()
    workflow = _make_workflow()
    context = RuleContext(query="hi", workflow_profile=workflow)

    decision = engine.decide(context)

    assert decision is not None
    assert decision.forced_models == ["m1"]
    assert decision.preferred_models == ["m2"]
    assert decision.excluded_models == ["m3"]
    assert decision.quality_threshold == pytest.approx(0.4)
    assert decision.max_budget == pytest.approx(0.01)


def test_kpi_profile_quality_direct():
    engine = RuleEngine()
    context = RuleContext(query="hi", kpi_flags={"profile": "quality"})

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.DIRECT_BEST


def test_kpi_profile_cost_cascade():
    engine = RuleEngine()
    context = RuleContext(query="hi", kpi_flags={"profile": "cost"})

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.CASCADE


def test_kpi_risk_override():
    engine = RuleEngine()
    context = RuleContext(query="hi", kpi_flags={"risk": "high"})

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.DIRECT_BEST


def test_kpi_record_only():
    engine = RuleEngine()
    context = RuleContext(query="hi", kpi_flags={"custom": "flag"})

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy is None
    assert decision.reason == "KPI flags recorded"


def test_tenant_override_rule():
    engine = RuleEngine(
        tenant_rules={
            "tenant-1": {
                "routing_strategy": RoutingStrategy.CASCADE,
                "preferred_channel": "voice",
                "allowed_models": ["m1"],
            }
        }
    )
    context = RuleContext(query="hi", tenant_id="tenant-1")

    decision = engine.decide(context)

    assert decision is not None
    assert decision.routing_strategy == RoutingStrategy.CASCADE
    assert decision.preferred_channel == "voice"
    assert decision.allowed_models == ["m1"]
    assert decision.metadata.get("tenant_id") == "tenant-1"


def test_channel_failover_routing():
    engine = RuleEngine(
        channel_models={"backup": ["m2"]},
        channel_failover={"voice": "backup"},
    )
    context = RuleContext(query="hi", channel="voice")

    decision = engine.decide(context)

    assert decision is not None
    assert decision.preferred_channel == "backup"
    assert decision.allowed_models == ["m2"]
    assert decision.failover_channel == "backup"
