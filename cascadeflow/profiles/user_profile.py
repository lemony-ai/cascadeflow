"""User profile system for cascadeflow."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .tier_config import TierConfig, TierLevel


@dataclass
class UserProfile:
    """
    Complete user profile for cascadeflow.

    Multi-dimensional profile system where tier is ONE subcategory among:
    1. Identity (who)
    2. Tier (subscription level)
    3. Limits (what they can do)
    4. Preferences (how they want it)
    5. Guardrails (safety & compliance)
    6. Telemetry (observability)

    v0.2.1 Foundation: Tier, limits, basic preferences, basic guardrails
    Future versions will add organization, workspace, advanced features
    """

    # 1. Identity (Who)
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    # 2. Tier (Subscription Level) - ONE subcategory
    tier: TierConfig = field(default_factory=lambda: TierConfig.from_preset(TierLevel.FREE))

    # 3. Limits (What They Can Do) - Can override tier defaults
    custom_daily_budget: Optional[float] = None
    custom_requests_per_hour: Optional[int] = None
    custom_requests_per_day: Optional[int] = None

    # 4. Preferences (How They Want It)
    preferred_models: Optional[list[str]] = None
    cost_sensitivity: str = "balanced"  # aggressive, balanced, quality_first
    preferred_domains: Optional[list[str]] = None  # e.g., ["code", "medical", "legal"]
    domain_models: Optional[dict[str, list[str]]] = None  # Domain-specific model overrides

    # 5. Guardrails (Safety & Compliance) - v0.2.1 basic flags
    enable_content_moderation: bool = False
    enable_pii_detection: bool = False

    # 6. Telemetry (Observability)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_tier(cls, tier: TierLevel, user_id: str, **kwargs) -> "UserProfile":
        """
        Simple factory: Create profile from tier preset.

        This is the recommended way for most use cases.

        Example:
            profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
            agent = CascadeAgent.from_profile(profile)
        """
        tier_config = TierConfig.from_preset(tier)
        return cls(user_id=user_id, tier=tier_config, **kwargs)

    def get_daily_budget(self) -> Optional[float]:
        """Get effective daily budget (custom or tier default)"""
        return (
            self.custom_daily_budget
            if self.custom_daily_budget is not None
            else self.tier.daily_budget
        )

    def get_requests_per_hour(self) -> Optional[int]:
        """Get effective rate limit (custom or tier default)"""
        return (
            self.custom_requests_per_hour
            if self.custom_requests_per_hour is not None
            else self.tier.requests_per_hour
        )

    def get_requests_per_day(self) -> Optional[int]:
        """Get effective daily request limit (custom or tier default)"""
        return (
            self.custom_requests_per_day
            if self.custom_requests_per_day is not None
            else self.tier.requests_per_day
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage"""
        return {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "tier": {
                "name": self.tier.name,
                "daily_budget": self.tier.daily_budget,
                "requests_per_hour": self.tier.requests_per_hour,
                "requests_per_day": self.tier.requests_per_day,
                "enable_streaming": self.tier.enable_streaming,
                "enable_batch": self.tier.enable_batch,
                "enable_embeddings": self.tier.enable_embeddings,
                "min_quality": self.tier.min_quality,
                "target_quality": self.tier.target_quality,
            },
            "custom_daily_budget": self.custom_daily_budget,
            "custom_requests_per_hour": self.custom_requests_per_hour,
            "custom_requests_per_day": self.custom_requests_per_day,
            "preferred_models": self.preferred_models,
            "cost_sensitivity": self.cost_sensitivity,
            "preferred_domains": self.preferred_domains,
            "domain_models": self.domain_models,
            "enable_content_moderation": self.enable_content_moderation,
            "enable_pii_detection": self.enable_pii_detection,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        """Deserialize from dict"""
        # Parse tier
        tier_data = data.get("tier", {})
        tier_name = tier_data.get("name", "free")

        try:
            tier_level = TierLevel(tier_name)
            tier = TierConfig.from_preset(tier_level)
        except (ValueError, KeyError):
            # Fallback to FREE tier
            tier = TierConfig.from_preset(TierLevel.FREE)

        # Parse datetime
        created_at_str = data.get("created_at")
        created_at = datetime.fromisoformat(created_at_str) if created_at_str else datetime.utcnow()

        return cls(
            user_id=data["user_id"],
            created_at=created_at,
            tier=tier,
            custom_daily_budget=data.get("custom_daily_budget"),
            custom_requests_per_hour=data.get("custom_requests_per_hour"),
            custom_requests_per_day=data.get("custom_requests_per_day"),
            preferred_models=data.get("preferred_models"),
            cost_sensitivity=data.get("cost_sensitivity", "balanced"),
            preferred_domains=data.get("preferred_domains"),
            domain_models=data.get("domain_models"),
            enable_content_moderation=data.get("enable_content_moderation", False),
            enable_pii_detection=data.get("enable_pii_detection", False),
            metadata=data.get("metadata", {}),
        )
