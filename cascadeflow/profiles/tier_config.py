"""Tier configuration for user profiles."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TierLevel(str, Enum):
    """Predefined tier levels"""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


@dataclass
class TierConfig:
    """
    Tier configuration (one dimension of UserProfile).

    This represents subscription tiers with predefined limits and features.
    Can be used as-is or customized per user.
    """

    name: str

    # Budget limits
    daily_budget: Optional[float] = None
    weekly_budget: Optional[float] = None
    monthly_budget: Optional[float] = None

    # Rate limits
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None
    tokens_per_minute: Optional[int] = None

    # Feature flags
    enable_streaming: bool = True
    enable_batch: bool = False
    enable_embeddings: bool = False

    # Quality settings
    min_quality: float = 0.60
    target_quality: float = 0.80

    # Model access
    allowed_models: Optional[list[str]] = None
    blocked_models: Optional[list[str]] = None

    # Support level
    support_priority: str = "community"  # community, priority, dedicated

    @classmethod
    def from_preset(cls, tier: TierLevel) -> "TierConfig":
        """Create TierConfig from predefined preset"""
        return TIER_PRESETS[tier]


# Predefined tier presets
TIER_PRESETS = {
    TierLevel.FREE: TierConfig(
        name="free",
        daily_budget=0.10,
        requests_per_hour=10,
        requests_per_day=100,
        enable_streaming=False,
        enable_batch=False,
        enable_embeddings=False,
        min_quality=0.60,
        target_quality=0.70,
        support_priority="community",
    ),
    TierLevel.STARTER: TierConfig(
        name="starter",
        daily_budget=1.00,
        requests_per_hour=100,
        requests_per_day=1000,
        enable_streaming=True,
        enable_batch=False,
        enable_embeddings=False,
        min_quality=0.70,
        target_quality=0.80,
        support_priority="community",
    ),
    TierLevel.PRO: TierConfig(
        name="pro",
        daily_budget=10.00,
        requests_per_hour=1000,
        requests_per_day=10000,
        tokens_per_minute=100000,
        enable_streaming=True,
        enable_batch=True,
        enable_embeddings=True,
        min_quality=0.75,
        target_quality=0.85,
        allowed_models=None,  # All models
        support_priority="priority",
    ),
    TierLevel.BUSINESS: TierConfig(
        name="business",
        daily_budget=50.00,
        requests_per_hour=5000,
        requests_per_day=50000,
        tokens_per_minute=500000,
        enable_streaming=True,
        enable_batch=True,
        enable_embeddings=True,
        min_quality=0.80,
        target_quality=0.90,
        support_priority="priority",
    ),
    TierLevel.ENTERPRISE: TierConfig(
        name="enterprise",
        daily_budget=None,  # Unlimited
        requests_per_hour=None,  # Unlimited
        requests_per_day=None,  # Unlimited
        tokens_per_minute=None,  # Unlimited
        enable_streaming=True,
        enable_batch=True,
        enable_embeddings=True,
        min_quality=0.85,
        target_quality=0.95,
        support_priority="dedicated",
    ),
}
