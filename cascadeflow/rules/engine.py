"""
Rule engine for routing decisions.

This centralizes tier/profile/domain/KPI routing rules and returns
structured decisions to the PreRouter.
"""

import logging
from typing import Any, Optional

from cascadeflow.quality.complexity import QueryComplexity
from cascadeflow.routing.base import RoutingStrategy
from cascadeflow.schema.config import UserTier, WorkflowProfile

from .context import RuleContext
from .decision import RuleDecision

logger = logging.getLogger(__name__)


class RuleEngine:
    """Rule engine that produces routing decisions from structured context."""

    def __init__(
        self,
        enable_domain_routing: bool = True,
        tiers: Optional[dict[str, UserTier]] = None,
        workflows: Optional[dict[str, WorkflowProfile]] = None,
        tenant_rules: Optional[dict[str, Any]] = None,
        channel_models: Optional[dict[str, list[str]]] = None,
        channel_failover: Optional[dict[str, str]] = None,
        channel_strategies: Optional[dict[str, Any]] = None,
        verbose: bool = False,
    ) -> None:
        self.enable_domain_routing = enable_domain_routing
        self.tiers = tiers or {}
        self.workflows = workflows or {}
        self.tenant_rules = tenant_rules or {}
        self.channel_models = channel_models or {}
        self.channel_failover = channel_failover or {}
        self.channel_strategies = channel_strategies or {}
        self.verbose = verbose

    def decide(self, context: RuleContext) -> Optional[RuleDecision]:
        """Return the first matching rule decision, or None."""
        decision = None

        if self.enable_domain_routing:
            decision = self._merge_decisions(decision, self._apply_domain_rules(context))

        decision = self._merge_decisions(decision, self._apply_tenant_rules(context))
        decision = self._merge_decisions(decision, self._apply_channel_failover(context))
        decision = self._merge_decisions(decision, self._apply_tier_rules(context))
        decision = self._merge_decisions(decision, self._apply_workflow_rules(context))
        decision = self._merge_decisions(decision, self._apply_kpi_rules(context))

        return decision

    def _apply_domain_rules(self, context: RuleContext) -> Optional[RuleDecision]:
        """Apply domain-specific routing rules if a domain config is present."""
        domain_config = context.domain_config
        if not domain_config or not getattr(domain_config, "enabled", True):
            return None

        complexity = self._coerce_complexity(context.complexity)
        domain_confidence = context.domain_confidence or context.complexity_confidence
        confidence = domain_confidence if domain_confidence > 0 else 0.6

        domain_cascade_complexities = getattr(domain_config, "cascade_complexities", None)
        domain_cascade_set = None
        if domain_cascade_complexities:
            try:
                domain_cascade_set = {QueryComplexity(level.lower()) for level in domain_cascade_complexities}
            except ValueError as exc:
                logger.warning("Invalid complexity in domain config: %s", exc)
                domain_cascade_set = None

        metadata = {
            "rule": "domain_routing",
            "domain": context.detected_domain,
            "domain_confidence": context.domain_confidence,
            "domain_cascade_complexities": domain_cascade_complexities,
            "domain_drafter": getattr(domain_config, "drafter", None),
            "domain_verifier": getattr(domain_config, "verifier", None),
            "domain_threshold": getattr(domain_config, "threshold", None),
        }

        if getattr(domain_config, "require_verifier", False):
            return RuleDecision(
                routing_strategy=RoutingStrategy.DIRECT_BEST,
                reason=f"Rule: domain '{context.detected_domain}' requires verifier",
                confidence=confidence,
                metadata=metadata,
            )

        if domain_cascade_set is not None and complexity is not None:
            if complexity in domain_cascade_set:
                return RuleDecision(
                    routing_strategy=RoutingStrategy.CASCADE,
                    reason=(
                        f"Rule: domain '{context.detected_domain}' + {complexity.value} → cascade"
                    ),
                    confidence=min(context.complexity_confidence, confidence),
                    metadata=metadata,
                )

            return RuleDecision(
                routing_strategy=RoutingStrategy.DIRECT_BEST,
                reason=(
                    f"Rule: domain '{context.detected_domain}' + {complexity.value} → direct"
                ),
                confidence=confidence,
                metadata=metadata,
            )

        return RuleDecision(
            routing_strategy=RoutingStrategy.CASCADE,
            reason=f"Rule: domain '{context.detected_domain}' configured → cascade",
            confidence=confidence,
            metadata=metadata,
        )

    def _apply_tier_rules(self, context: RuleContext) -> Optional[RuleDecision]:
        tier = context.tier_config
        if tier is None and context.user_tier:
            tier = self.tiers.get(context.user_tier)

        if tier is None:
            return None

        excluded = list(tier.exclude_models or [])
        if tier.excluded_models:
            excluded.extend(tier.excluded_models)

        metadata = {
            "rule": "tier_constraints",
            "tier": tier.name,
            "latency": {
                "max_total_ms": tier.latency.max_total_ms,
                "max_per_model_ms": tier.latency.max_per_model_ms,
            },
            "optimization": {
                "cost": tier.optimization.cost,
                "speed": tier.optimization.speed,
                "quality": tier.optimization.quality,
            },
        }

        return RuleDecision(
            reason=f"Tier '{tier.name}' constraints applied",
            confidence=0.7,
            metadata=metadata,
            allowed_models=list(tier.allowed_models or []),
            excluded_models=excluded or None,
            preferred_models=list(tier.preferred_models or []),
            quality_threshold=tier.quality_threshold,
            max_budget=tier.max_budget,
        )

    def _apply_tenant_rules(self, context: RuleContext) -> Optional[RuleDecision]:
        tenant_id = context.tenant_id
        if not tenant_id:
            return None

        rule = self.tenant_rules.get(tenant_id)
        if not rule:
            return None

        decision = self._decision_from_value(rule)
        if decision.metadata is None:
            decision.metadata = {}
        decision.metadata.update({"rule": "tenant_override", "tenant_id": tenant_id})
        if not decision.reason:
            decision.reason = f"Tenant '{tenant_id}' override applied"
        if decision.confidence == 0:
            decision.confidence = 0.75
        return decision

    def _apply_channel_failover(self, context: RuleContext) -> Optional[RuleDecision]:
        channel = context.channel
        if not channel:
            return None

        selected_channel = channel
        models = self.channel_models.get(selected_channel)
        failover = None
        if not models:
            failover = self.channel_failover.get(selected_channel)
            if failover:
                selected_channel = failover
                models = self.channel_models.get(selected_channel)

        if not models and not failover:
            return None

        strategy = None
        strategy_value = self.channel_strategies.get(selected_channel) or self.channel_strategies.get(
            channel
        )
        if strategy_value:
            try:
                strategy = (
                    strategy_value
                    if isinstance(strategy_value, RoutingStrategy)
                    else RoutingStrategy(str(strategy_value))
                )
            except ValueError:
                logger.warning("Invalid channel routing strategy: %s", strategy_value)

        if strategy is None and selected_channel in {"heartbeat", "cron"}:
            strategy = RoutingStrategy.DIRECT_CHEAP

        metadata = {
            "rule": "channel_routing",
            "channel": channel,
            "selected_channel": selected_channel,
            "failover_channel": failover,
            "channel_strategy": strategy.value if strategy else None,
        }

        return RuleDecision(
            reason=f"Channel '{channel}' routing applied",
            confidence=0.65,
            metadata=metadata,
            allowed_models=list(models or []),
            preferred_channel=selected_channel,
            failover_channel=failover,
            routing_strategy=strategy,
        )

    def _apply_workflow_rules(self, context: RuleContext) -> Optional[RuleDecision]:
        workflow = context.workflow_profile
        if workflow is None and context.workflow_name:
            workflow = self.workflows.get(context.workflow_name)
        if workflow is None:
            return None

        metadata = {"rule": "workflow_overrides", "workflow": workflow.name}

        return RuleDecision(
            reason=f"Workflow '{workflow.name}' overrides applied",
            confidence=0.8,
            metadata=metadata,
            forced_models=list(workflow.force_models or []) if workflow.force_models else None,
            preferred_models=list(workflow.preferred_models or []),
            excluded_models=list(workflow.exclude_models or []),
            quality_threshold=workflow.quality_threshold_override,
            max_budget=workflow.max_budget_override,
        )

    def _apply_kpi_rules(self, context: RuleContext) -> Optional[RuleDecision]:
        flags = context.kpi_flags or {}
        if not flags:
            return None

        metadata = {"rule": "kpi_flags", "kpis": flags}

        profile = flags.get("profile")
        if isinstance(profile, str):
            profile_value = profile.strip().lower()
            if profile_value in {"quality", "best", "accuracy"}:
                return RuleDecision(
                    routing_strategy=RoutingStrategy.DIRECT_BEST,
                    reason="KPI profile override → direct verifier",
                    confidence=0.75,
                    metadata=metadata,
                )
            if profile_value in {"cost", "cost_savings", "cheap", "fast"}:
                return RuleDecision(
                    routing_strategy=RoutingStrategy.CASCADE,
                    reason="KPI profile override → cascade",
                    confidence=0.7,
                    metadata=metadata,
                )

        risk = flags.get("risk") or flags.get("compliance")
        risk_str = str(risk).lower() if risk is not None else ""
        if risk is True or risk_str in {"high", "strict", "true", "1"}:
            return RuleDecision(
                routing_strategy=RoutingStrategy.DIRECT_BEST,
                reason="KPI risk/compliance override → direct verifier",
                confidence=0.8,
                metadata=metadata,
            )

        return RuleDecision(
            reason="KPI flags recorded",
            confidence=0.5,
            metadata=metadata,
        )

    @staticmethod
    def _decision_from_value(value: Any) -> RuleDecision:
        if isinstance(value, RuleDecision):
            return value
        return RuleDecision(
            routing_strategy=value.get("routing_strategy"),
            reason=value.get("reason", ""),
            confidence=value.get("confidence", 0.0),
            metadata=value.get("metadata", {}),
            preferred_channel=value.get("preferred_channel"),
            model_name=value.get("model_name"),
            allowed_models=value.get("allowed_models"),
            excluded_models=value.get("excluded_models"),
            preferred_models=value.get("preferred_models"),
            forced_models=value.get("forced_models"),
            quality_threshold=value.get("quality_threshold"),
            max_budget=value.get("max_budget"),
            failover_channel=value.get("failover_channel"),
        )

    @staticmethod
    def _merge_decisions(
        base: Optional[RuleDecision], other: Optional[RuleDecision]
    ) -> Optional[RuleDecision]:
        if other is None:
            return base
        if base is None:
            return other

        if other.routing_strategy is not None:
            base.routing_strategy = other.routing_strategy
        if other.reason:
            if base.reason:
                base.reason = f"{base.reason}; {other.reason}"
            else:
                base.reason = other.reason
        if other.confidence:
            base.confidence = max(base.confidence, other.confidence)
        if other.metadata:
            base.metadata.update(other.metadata)
        if other.preferred_channel is not None:
            base.preferred_channel = other.preferred_channel
        if other.model_name is not None:
            base.model_name = other.model_name
        if other.allowed_models is not None:
            base.allowed_models = other.allowed_models
        if other.excluded_models is not None:
            base.excluded_models = other.excluded_models
        if other.preferred_models is not None:
            base.preferred_models = other.preferred_models
        if other.forced_models is not None:
            base.forced_models = other.forced_models
        if other.quality_threshold is not None:
            base.quality_threshold = other.quality_threshold
        if other.max_budget is not None:
            base.max_budget = other.max_budget
        if other.failover_channel is not None:
            base.failover_channel = other.failover_channel

        return base

    @staticmethod
    def _coerce_complexity(value: Optional[object]) -> Optional[QueryComplexity]:
        if isinstance(value, QueryComplexity):
            return value
        if isinstance(value, str):
            try:
                return QueryComplexity(value.lower())
            except ValueError:
                return None
        return None
