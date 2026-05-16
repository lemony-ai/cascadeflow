"""Hermes Agent delegation router."""

from __future__ import annotations

from typing import Optional

from .classifier import HIGH_STAKES_DOMAINS, HermesTaskClassifier
from .config import HermesRouteProfile, HermesRoutingConfig
from .skill_metadata import profile_from_skill_metadata
from .types import HermesDelegationDecision, HermesDelegationRequest


class HermesDelegationRouter:
    """Return routing recommendations for Hermes ``delegate_task`` children."""

    def __init__(
        self,
        config: Optional[HermesRoutingConfig] = None,
        classifier: Optional[HermesTaskClassifier] = None,
    ):
        self.config = config or HermesRoutingConfig()
        self.classifier = classifier or HermesTaskClassifier()

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> HermesDelegationRouter:
        return cls(config=HermesRoutingConfig.from_dict(data))

    def route_delegation(
        self,
        request: HermesDelegationRequest,
    ) -> HermesDelegationDecision:
        try:
            return self._route_delegation(request)
        except Exception as exc:
            return HermesDelegationDecision(
                action="inherit",
                confidence=0.0,
                reason="router_error",
                source="fallback",
                metadata={"error": exc.__class__.__name__},
            )

    def _route_delegation(
        self,
        request: HermesDelegationRequest,
    ) -> HermesDelegationDecision:
        if not self.config.enabled:
            return HermesDelegationDecision(
                action="inherit",
                confidence=0.0,
                reason="cascadeflow_disabled",
                source="config",
            )

        skill_profile = profile_from_skill_metadata(request.skill_metadata)
        if skill_profile is not None:
            return self._decision_from_profile(
                skill_profile,
                request=request,
                source="skill_metadata",
                reason="explicit_skill_metadata",
                domain=skill_profile.domain,
                topic=skill_profile.topic,
                complexity=None,
                confidence=skill_profile.confidence or 1.0,
            )

        classification = self.classifier.classify(request)
        if (
            classification.domain in HIGH_STAKES_DOMAINS
            and classification.domain not in self.config.routes
        ):
            return HermesDelegationDecision(
                action="inherit",
                domain=classification.domain,
                topic=classification.topic,
                complexity=classification.complexity,
                confidence=classification.confidence,
                reason="high_stakes_domain_unconfigured",
                source="classifier",
                metadata={
                    "route_key": classification.domain,
                    "loaded_skills": list(request.loaded_skills),
                },
            )

        route_key = self._select_route_key(classification.domain, classification.complexity)
        profile = self.config.routes.get(route_key) if route_key else None
        if profile is None:
            return HermesDelegationDecision(
                action="inherit",
                domain=classification.domain,
                topic=classification.topic,
                complexity=classification.complexity,
                confidence=classification.confidence,
                reason="no_matching_route",
                source="classifier",
                metadata={
                    "route_key": route_key,
                    "loaded_skills": list(request.loaded_skills),
                },
            )

        return self._decision_from_profile(
            profile,
            request=request,
            source="classifier",
            reason=classification.reason,
            domain=profile.domain or classification.domain,
            topic=profile.topic or classification.topic,
            complexity=classification.complexity,
            confidence=min(1.0, max(classification.confidence, profile.confidence)),
        )

    def _select_route_key(self, domain: str, complexity: str) -> str:
        normalized_domain = (domain or "").lower()
        normalized_complexity = (complexity or "").lower()
        if normalized_domain in self.config.routes:
            return normalized_domain
        if normalized_domain == "debugging" and "code" in self.config.routes:
            return "code"
        if normalized_complexity in self.config.routes:
            return normalized_complexity
        if normalized_complexity in {"trivial", "simple"} and "simple" in self.config.routes:
            return "simple"
        if normalized_complexity in {"hard", "expert"} and "hard" in self.config.routes:
            return "hard"
        if "general" in self.config.routes:
            return "general"
        return normalized_domain or normalized_complexity

    def _decision_from_profile(
        self,
        profile: HermesRouteProfile,
        *,
        request: HermesDelegationRequest,
        source: str,
        reason: str,
        domain: Optional[str],
        topic: Optional[str],
        complexity: Optional[str],
        confidence: float,
    ) -> HermesDelegationDecision:
        confidence = max(0.0, min(1.0, confidence))
        below_threshold = confidence < self.config.min_confidence
        action = "route"
        if self.config.mode == "observe" or below_threshold:
            action = "inherit"

        provider = profile.provider if self.config.route_provider_model else None
        model = profile.model if self.config.route_provider_model else None
        reasoning_effort = profile.reasoning_effort if self.config.route_reasoning_effort else None
        return HermesDelegationDecision(
            action=action,
            provider=provider,
            model=model,
            reasoning_effort=reasoning_effort,
            domain=domain,
            topic=topic,
            complexity=complexity,
            confidence=confidence,
            reason="confidence_below_threshold" if below_threshold else reason,
            source=source,
            metadata={
                "mode": self.config.mode,
                "would_route": bool(provider or model or reasoning_effort),
                "applied": action == "route",
                "loaded_skills": list(request.loaded_skills),
            },
        )
