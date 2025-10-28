. Make# User Profile System Design for CascadeFlow v0.2.1+

**Date**: October 28, 2025
**Purpose**: Design comprehensive user profile system with tiers as subcategory
**Goal**: Best developer experience for production systems with thousands of users

---

## Executive Summary

**Current State**: CascadeFlow v0.2.0 has basic `BudgetConfig` with simple tier-based budgets
**Proposed**: Comprehensive `UserProfile` system where tiers are one subcategory among many configurable dimensions

**Key Insight**: Instead of rigid tiers (free/pro/enterprise), provide flexible profile system that developers can customize for their specific use cases while offering sensible defaults.

---

## Part 1: Feature Status Check

### What We Already Have ✅

#### 1. Streaming Support ✅ IMPLEMENTED
```python
# Found in: cascadeflow/providers/base.py:815
async def stream(
    self,
    prompt: str,
    model: str,
    **kwargs
) -> AsyncIterator[str]:
    """Stream response token by token"""
```

**Status**: ✅ **Base streaming implemented** (need to integrate with CascadeAgent)
**Location**: `cascadeflow/providers/base.py:815`
**Next Step**: Expose in `CascadeAgent` API for v0.2.1

---

#### 2. Embeddings ✅ IMPLEMENTED
```python
# Found in: cascadeflow/ml/embedding.py
class UnifiedEmbeddingService:
    """
    Single embedding model for all semantic tasks.

    Uses FastEmbed with BGE-small-en-v1.5 (ONNX optimized):
    - 45M parameters, 384 dimensions
    - ~40MB model size
    - ~20-30ms per embedding (CPU)
    - 91.8% MTEB score
    """
```

**Status**: ✅ **Fully implemented** (used internally for semantic quality)
**Location**: `cascadeflow/ml/embedding.py`
**Usage**: Internal (quality validation, domain detection)
**Next Step**: Expose as public API for users in v0.3.0

---

#### 3. Batch Completion ❌ NOT IMPLEMENTED
**Status**: ❌ **Not implemented** (planned for v0.2.2)
**Recommendation**: Add in v0.2.2 using LiteLLM's batch API

---

#### 4. Async Streaming ⚠️ PARTIAL
**Status**: ⚠️ **Base streaming async**, need full integration
**Next Step**: Complete in v0.2.1

---

### Summary: Feature Status

| Feature | Status | Version | Notes |
|---------|--------|---------|-------|
| **Streaming** | ✅ Implemented | v0.2.0 | Need CascadeAgent integration (v0.2.1) |
| **Embeddings** | ✅ Implemented | v0.2.0 | Internal use, expose API in v0.3.0 |
| **Batch Completion** | ❌ Not implemented | v0.2.2 | Use LiteLLM batch API |
| **Async Streaming** | ⚠️ Partial | v0.2.1 | Complete integration |

---

## Part 2: Current Tier System (v0.2.0)

### Current Implementation

```python
# cascadeflow/telemetry/cost_tracker.py
@dataclass
class BudgetConfig:
    """Simple budget configuration"""
    daily: Optional[float] = None
    weekly: Optional[float] = None
    monthly: Optional[float] = None
    total: Optional[float] = None

# Usage (simple, limited)
tracker = CostTracker(
    user_budgets={
        'user_123': BudgetConfig(daily=1.00),
        'user_456': BudgetConfig(daily=10.00),
    }
)
```

### Problems with Current Approach

1. ❌ **No tier abstraction** - Developers manually map users to budgets
2. ❌ **Budget only** - Can't configure rate limits, quality, features
3. ❌ **No presets** - No default free/pro/enterprise configurations
4. ❌ **Hard to scale** - Managing thousands of users manually
5. ❌ **No organization/workspace** - Flat user structure
6. ❌ **Limited customization** - Can't set model preferences, domains, etc.

---

## Part 3: User Profile System Design

### 3.1 Architecture: Multi-Dimensional Profiles

**Key Design Principle**: Tiers are just ONE dimension of a user profile, not the profile itself.

```
UserProfile
├── identity (who)
│   ├── user_id
│   ├── organization_id  # NEW: Multi-tenant support
│   ├── workspace_id     # NEW: Multiple workspaces per org
│   └── roles            # NEW: RBAC support
│
├── tier (subscription level) ← One subcategory
│   ├── name: "free" | "pro" | "enterprise" | custom
│   └── inherits_from: Tier preset or custom config
│
├── limits (what they can do)
│   ├── budgets (cost limits)
│   ├── rate_limits (request limits)
│   ├── quota_limits (usage limits)
│   └── feature_flags (enabled features)
│
├── preferences (how they want it)
│   ├── quality_preferences
│   ├── latency_preferences
│   ├── cost_preferences
│   ├── domain_preferences
│   └── model_preferences
│
├── governance (safety & compliance)
│   ├── guardrails (content moderation, PII, toxicity)
│   ├── audit_logging
│   ├── data_retention
│   └── compliance_requirements (HIPAA, GDPR, etc.)
│
└── telemetry (observability)
    ├── cost_tracking
    ├── usage_metrics
    ├── quality_metrics
    └── custom_metadata
```

---

### 3.2 UserProfile Data Structure

```python
# NEW: cascadeflow/schema/user_profile.py

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

# ============================================================================
# TIER SYSTEM (Subcategory of UserProfile)
# ============================================================================

class TierLevel(Enum):
    """Predefined tier levels (customizable)"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


@dataclass
class TierConfig:
    """
    Tier configuration (one dimension of UserProfile).

    Developers can use predefined tiers or create custom ones.

    Example:
        >>> # Use predefined tier
        >>> tier = TierConfig.from_preset(TierLevel.PRO)
        >>>
        >>> # Create custom tier
        >>> tier = TierConfig(
        ...     name="startup",
        ...     daily_budget=5.00,
        ...     requests_per_hour=1000
        ... )
    """
    name: str

    # Budget limits
    daily_budget: Optional[float] = None
    weekly_budget: Optional[float] = None
    monthly_budget: Optional[float] = None

    # Rate limits
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None

    # Quality settings
    default_quality_threshold: float = 0.7
    max_quality_threshold: float = 0.95

    # Feature flags
    enable_streaming: bool = True
    enable_batch: bool = False
    enable_embeddings: bool = False
    enable_quality_validation: bool = True
    enable_domain_routing: bool = True
    enable_guardrails: bool = True

    # Model access
    allowed_models: Optional[List[str]] = None  # None = all models
    preferred_models: Optional[List[str]] = None

    # Support level
    support_priority: str = "standard"  # "basic", "standard", "priority", "dedicated"

    @classmethod
    def from_preset(cls, level: TierLevel) -> 'TierConfig':
        """Load from predefined tier."""
        return TIER_PRESETS[level]


# ============================================================================
# PREDEFINED TIER PRESETS
# ============================================================================

TIER_PRESETS = {
    TierLevel.FREE: TierConfig(
        name="free",
        daily_budget=0.10,
        requests_per_hour=10,
        requests_per_day=100,
        default_quality_threshold=0.65,
        max_quality_threshold=0.80,
        enable_streaming=False,
        enable_batch=False,
        enable_embeddings=False,
        enable_quality_validation=True,  # Basic quality
        enable_domain_routing=False,  # No domain routing
        enable_guardrails=True,  # Safety only
        allowed_models=["gpt-3.5-turbo", "llama-3.1-8b-instant", "claude-3-haiku"],
        support_priority="community"
    ),

    TierLevel.STARTER: TierConfig(
        name="starter",
        daily_budget=1.00,
        weekly_budget=5.00,
        requests_per_hour=100,
        requests_per_day=1000,
        default_quality_threshold=0.70,
        max_quality_threshold=0.85,
        enable_streaming=True,
        enable_batch=False,
        enable_embeddings=False,
        enable_quality_validation=True,
        enable_domain_routing=True,  # Domain routing enabled
        enable_guardrails=True,
        allowed_models=None,  # All models
        support_priority="standard"
    ),

    TierLevel.PRO: TierConfig(
        name="pro",
        daily_budget=10.00,
        weekly_budget=50.00,
        monthly_budget=200.00,
        requests_per_hour=1000,
        requests_per_day=10000,
        default_quality_threshold=0.75,
        max_quality_threshold=0.90,
        enable_streaming=True,
        enable_batch=True,  # Batch enabled
        enable_embeddings=True,  # Embeddings enabled
        enable_quality_validation=True,
        enable_domain_routing=True,
        enable_guardrails=True,
        allowed_models=None,
        support_priority="priority"
    ),

    TierLevel.BUSINESS: TierConfig(
        name="business",
        daily_budget=50.00,
        weekly_budget=250.00,
        monthly_budget=1000.00,
        requests_per_hour=5000,
        requests_per_day=50000,
        default_quality_threshold=0.80,
        max_quality_threshold=0.95,
        enable_streaming=True,
        enable_batch=True,
        enable_embeddings=True,
        enable_quality_validation=True,
        enable_domain_routing=True,
        enable_guardrails=True,
        allowed_models=None,
        support_priority="dedicated"
    ),

    TierLevel.ENTERPRISE: TierConfig(
        name="enterprise",
        daily_budget=None,  # Unlimited (or custom)
        weekly_budget=None,
        monthly_budget=None,
        requests_per_hour=None,  # Unlimited (or custom)
        requests_per_day=None,
        default_quality_threshold=0.85,
        max_quality_threshold=0.98,
        enable_streaming=True,
        enable_batch=True,
        enable_embeddings=True,
        enable_quality_validation=True,
        enable_domain_routing=True,
        enable_guardrails=True,
        allowed_models=None,
        support_priority="dedicated"
    ),
}


# ============================================================================
# QUALITY PREFERENCES
# ============================================================================

@dataclass
class QualityPreferences:
    """
    User preferences for quality vs cost vs speed tradeoffs.

    Allows fine-grained control beyond tier defaults.
    """
    # Quality thresholds
    minimum_quality: float = 0.70  # Never accept below this
    target_quality: float = 0.85   # Aim for this
    maximum_quality: float = 0.95  # Don't exceed (cost control)

    # Cost preferences
    cost_sensitivity: str = "balanced"  # "aggressive", "balanced", "quality_first"
    max_cost_per_query: Optional[float] = None

    # Latency preferences
    latency_sensitivity: str = "balanced"  # "real_time", "balanced", "batch"
    max_latency_ms: Optional[int] = None

    # Semantic quality
    enable_semantic_validation: bool = True
    semantic_weight: float = 0.5  # 0-1, how much to weight semantic vs confidence

    # Retry preferences
    max_retries: int = 2
    retry_on_low_quality: bool = True
    retry_on_guardrail_fail: bool = True


# ============================================================================
# RATE LIMITING
# ============================================================================

@dataclass
class RateLimitConfig:
    """
    Rate limiting configuration.

    Separate from budget limits - controls request rate, not cost.
    """
    # Request limits
    requests_per_second: Optional[int] = None
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    requests_per_day: Optional[int] = None

    # Token limits (separate from cost)
    tokens_per_minute: Optional[int] = None
    tokens_per_hour: Optional[int] = None
    tokens_per_day: Optional[int] = None

    # Burst allowance
    burst_multiplier: float = 1.5  # Allow 1.5x rate for short bursts
    burst_window_seconds: int = 10  # Burst window

    # Enforcement
    enforcement_mode: str = "sliding_window"  # "fixed_window", "sliding_window", "token_bucket"
    block_on_limit: bool = True  # vs warn only


# ============================================================================
# GUARDRAILS CONFIGURATION
# ============================================================================

@dataclass
class GuardrailsConfig:
    """
    Safety and compliance guardrails.

    Configure what content is allowed/blocked.
    """
    # Content moderation (pre-call)
    enable_content_moderation: bool = True
    block_hate_speech: bool = True
    block_violence: bool = True
    block_sexual_content: bool = True
    block_self_harm: bool = True

    # PII detection (pre & post call)
    enable_pii_detection: bool = True
    pii_action: str = "redact"  # "block", "redact", "warn"
    detect_email: bool = True
    detect_phone: bool = True
    detect_ssn: bool = True
    detect_credit_card: bool = True

    # Prompt injection (pre-call)
    enable_prompt_injection_detection: bool = True
    injection_action: str = "block"  # "block", "warn"

    # Toxicity detection (post-call, opt-in)
    enable_toxicity_detection: bool = False  # Opt-in (ML-based, slower)
    toxicity_threshold: float = 0.8  # 0-1
    toxicity_action: str = "retry"  # "block", "retry", "warn"

    # Hallucination detection (post-call, opt-in, experimental)
    enable_hallucination_detection: bool = False  # Opt-in (expensive)
    hallucination_action: str = "retry"  # "block", "retry", "warn"

    # Custom guardrails
    custom_guardrails: List[str] = field(default_factory=list)  # Plugin system


# ============================================================================
# ORGANIZATION & WORKSPACE (Multi-Tenant)
# ============================================================================

@dataclass
class OrganizationConfig:
    """
    Organization-level configuration (for multi-tenant SaaS).

    Allows multiple users under one organization.
    """
    organization_id: str
    organization_name: str

    # Shared budget across all users in org
    shared_budget: Optional[float] = None

    # Shared rate limits
    shared_rate_limits: Optional[RateLimitConfig] = None

    # Data isolation
    data_region: str = "us-east-1"  # Where to store data
    data_residency_requirements: Optional[List[str]] = None  # ["GDPR", "HIPAA", etc.]

    # Compliance
    compliance_mode: Optional[str] = None  # "hipaa", "gdpr", "sox", etc.
    audit_logging: bool = True
    data_retention_days: int = 90

    # Custom models (org-specific fine-tuned models)
    custom_models: Optional[List[str]] = None


@dataclass
class WorkspaceConfig:
    """
    Workspace-level configuration (within organization).

    Allows multiple workspaces per organization (e.g., dev, staging, prod).
    """
    workspace_id: str
    workspace_name: str
    organization_id: str

    # Workspace-specific budgets
    workspace_budget: Optional[float] = None

    # Environment
    environment: str = "production"  # "development", "staging", "production"

    # Workspace-level guardrails (can override org)
    workspace_guardrails: Optional[GuardrailsConfig] = None


# ============================================================================
# COMPLETE USER PROFILE
# ============================================================================

@dataclass
class UserProfile:
    """
    Complete user profile for CascadeFlow.

    Combines tier, preferences, limits, and governance into single config.

    Example:
        >>> # Simple: Use tier preset
        >>> profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
        >>>
        >>> # Advanced: Full customization
        >>> profile = UserProfile(
        ...     user_id="user_123",
        ...     tier=TierConfig.from_preset(TierLevel.PRO),
        ...     quality_preferences=QualityPreferences(target_quality=0.90),
        ...     guardrails=GuardrailsConfig(enable_toxicity_detection=True)
        ... )
        >>>
        >>> # Multi-tenant: Organization + workspace
        >>> profile = UserProfile(
        ...     user_id="user_123",
        ...     organization=OrganizationConfig(
        ...         organization_id="org_456",
        ...         organization_name="Acme Corp"
        ...     ),
        ...     workspace=WorkspaceConfig(
        ...         workspace_id="workspace_789",
        ...         workspace_name="production",
        ...         organization_id="org_456"
        ...     ),
        ...     tier=TierConfig.from_preset(TierLevel.ENTERPRISE)
        ... )
    """

    # ========== IDENTITY ==========
    user_id: str

    # Multi-tenant support (optional)
    organization: Optional[OrganizationConfig] = None
    workspace: Optional[WorkspaceConfig] = None

    # RBAC (optional)
    roles: List[str] = field(default_factory=list)  # ["admin", "developer", "viewer"]
    permissions: List[str] = field(default_factory=list)  # ["read", "write", "deploy"]

    # ========== TIER (One Subcategory) ==========
    tier: TierConfig = field(default_factory=lambda: TierConfig.from_preset(TierLevel.FREE))

    # ========== LIMITS ==========
    # Budget limits (can override tier defaults)
    budget_overrides: Optional[BudgetConfig] = None  # From v0.2.0, backward compatible

    # Rate limits (can override tier defaults)
    rate_limit_overrides: Optional[RateLimitConfig] = None

    # ========== PREFERENCES ==========
    quality_preferences: QualityPreferences = field(default_factory=QualityPreferences)

    # Domain preferences
    preferred_domains: List[str] = field(default_factory=list)  # ["code", "medical", "general"]

    # Model preferences (can override tier allowed_models)
    preferred_models: Optional[List[str]] = None
    blocked_models: Optional[List[str]] = None

    # ========== GOVERNANCE ==========
    guardrails: GuardrailsConfig = field(default_factory=GuardrailsConfig)

    # Audit & compliance
    enable_audit_logging: bool = True
    audit_log_level: str = "standard"  # "minimal", "standard", "comprehensive"

    # Data retention
    data_retention_days: int = 90

    # ========== TELEMETRY ==========
    # Custom metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Tags for filtering/grouping
    tags: List[str] = field(default_factory=list)

    # ========== METHODS ==========

    @classmethod
    def from_tier(cls, tier_level: TierLevel, user_id: str, **kwargs) -> 'UserProfile':
        """
        Create profile from predefined tier.

        Simplest way to create a profile - just specify tier.

        Example:
            >>> profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
        """
        tier_config = TierConfig.from_preset(tier_level)
        return cls(user_id=user_id, tier=tier_config, **kwargs)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Load profile from dict (e.g., from database)."""
        # Implementation for deserializing from database
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dict (e.g., for database storage)."""
        # Implementation for serializing to database
        pass

    def get_effective_budget(self) -> BudgetConfig:
        """
        Get effective budget (tier + overrides).

        Returns:
            Combined budget from tier defaults + user overrides
        """
        if self.budget_overrides:
            return self.budget_overrides

        # Convert tier limits to BudgetConfig
        return BudgetConfig(
            daily=self.tier.daily_budget,
            weekly=self.tier.weekly_budget,
            monthly=self.tier.monthly_budget
        )

    def get_effective_rate_limits(self) -> RateLimitConfig:
        """
        Get effective rate limits (tier + overrides).

        Returns:
            Combined rate limits from tier defaults + user overrides
        """
        if self.rate_limit_overrides:
            return self.rate_limit_overrides

        # Convert tier limits to RateLimitConfig
        return RateLimitConfig(
            requests_per_minute=self.tier.requests_per_minute,
            requests_per_hour=self.tier.requests_per_hour,
            requests_per_day=self.tier.requests_per_day
        )

    def can_use_feature(self, feature: str) -> bool:
        """
        Check if user can use a feature based on tier.

        Example:
            >>> if profile.can_use_feature("streaming"):
            ...     # Enable streaming
        """
        feature_map = {
            "streaming": self.tier.enable_streaming,
            "batch": self.tier.enable_batch,
            "embeddings": self.tier.enable_embeddings,
            "quality_validation": self.tier.enable_quality_validation,
            "domain_routing": self.tier.enable_domain_routing,
            "guardrails": self.tier.enable_guardrails,
        }
        return feature_map.get(feature, False)

    def can_use_model(self, model: str) -> bool:
        """
        Check if user can use a specific model.

        Checks:
        1. Tier allowed_models (None = all allowed)
        2. User blocked_models
        3. User preferred_models (if specified)
        """
        # Check blocked models
        if self.blocked_models and model in self.blocked_models:
            return False

        # Check tier allowed models
        if self.tier.allowed_models and model not in self.tier.allowed_models:
            return False

        return True

    def get_model_preferences(self) -> List[str]:
        """
        Get preferred models (user > tier > all).

        Returns:
            List of preferred models in priority order
        """
        if self.preferred_models:
            return self.preferred_models
        if self.tier.preferred_models:
            return self.tier.preferred_models
        if self.tier.allowed_models:
            return self.tier.allowed_models
        return []  # All models allowed


# ============================================================================
# PROFILE MANAGER (for managing many users)
# ============================================================================

class UserProfileManager:
    """
    Manage user profiles at scale (thousands of users).

    Features:
    - Profile caching (fast lookups)
    - Bulk operations
    - Database integration
    - Profile inheritance

    Example:
        >>> manager = UserProfileManager()
        >>>
        >>> # Load profile (from cache or DB)
        >>> profile = await manager.get_profile("user_123")
        >>>
        >>> # Bulk create profiles
        >>> profiles = manager.create_bulk([
        ...     {"user_id": f"user_{i}", "tier": "free"}
        ...     for i in range(1000)
        ... ])
        >>>
        >>> # Update tier
        >>> await manager.update_tier("user_123", TierLevel.PRO)
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 300,  # 5 min cache
        default_tier: TierLevel = TierLevel.FREE
    ):
        """
        Initialize profile manager.

        Args:
            cache_ttl_seconds: How long to cache profiles
            default_tier: Default tier for new users
        """
        self._cache: Dict[str, UserProfile] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = cache_ttl_seconds
        self._default_tier = default_tier

    async def get_profile(self, user_id: str) -> UserProfile:
        """
        Get user profile (from cache or load).

        Returns:
            UserProfile for user_id
        """
        # Check cache
        if user_id in self._cache:
            import time
            if time.time() - self._cache_timestamps[user_id] < self._cache_ttl:
                return self._cache[user_id]

        # Load from database (placeholder - implement based on your DB)
        profile = await self._load_from_database(user_id)

        # If not found, create default
        if profile is None:
            profile = UserProfile.from_tier(self._default_tier, user_id=user_id)
            await self._save_to_database(profile)

        # Cache
        self._cache[user_id] = profile
        import time
        self._cache_timestamps[user_id] = time.time()

        return profile

    async def _load_from_database(self, user_id: str) -> Optional[UserProfile]:
        """Load profile from database (implement based on your DB)."""
        # Placeholder - implement with your database
        # Could be PostgreSQL, MongoDB, Redis, etc.
        pass

    async def _save_to_database(self, profile: UserProfile):
        """Save profile to database (implement based on your DB)."""
        # Placeholder - implement with your database
        pass

    async def update_tier(self, user_id: str, new_tier: TierLevel):
        """
        Update user tier.

        Example:
            >>> await manager.update_tier("user_123", TierLevel.PRO)
        """
        profile = await self.get_profile(user_id)
        profile.tier = TierConfig.from_preset(new_tier)
        await self._save_to_database(profile)

        # Invalidate cache
        if user_id in self._cache:
            del self._cache[user_id]

    def create_bulk(self, user_data: List[Dict[str, Any]]) -> List[UserProfile]:
        """
        Create multiple profiles efficiently.

        Example:
            >>> profiles = manager.create_bulk([
            ...     {"user_id": "user_1", "tier": "pro"},
            ...     {"user_id": "user_2", "tier": "free"},
            ... ])
        """
        profiles = []
        for data in user_data:
            tier_name = data.get("tier", "free")
            tier_level = TierLevel(tier_name) if isinstance(tier_name, str) else tier_name
            profile = UserProfile.from_tier(tier_level, user_id=data["user_id"])
            profiles.append(profile)

        return profiles
```

This is getting very long - shall I continue with the implementation plan and examples in the same file, or would you like me to split it into multiple documents?

Let me know and I'll complete the design with:
- Part 4: Integration with CascadeAgent
- Part 5: Migration from v0.2.0 BudgetConfig
- Part 6: Implementation Roadmap (v0.2.1, v0.2.2, v0.3.0)
- Part 7: Code Examples
- Part 8: Best Practices for Production Systems