# User Profile System - Executive Summary

**Date**: October 28, 2025
**Purpose**: Quick reference for user profile system design
**Full Design**: See `USER_PROFILE_SYSTEM_DESIGN.md`

---

## TL;DR - Key Answers

### Q1: Do we have batch, async streaming, embeddings?

| Feature | Status | Details |
|---------|--------|---------|
| **Streaming** | ✅ YES | Implemented in `providers/base.py:815`, need CascadeAgent integration (v0.2.1) |
| **Embeddings** | ✅ YES | Fully implemented in `ml/embedding.py`, used internally, expose API in v0.3.0 |
| **Batch Completion** | ❌ NO | Not implemented, planned for v0.2.2 using LiteLLM |
| **Async Streaming** | ⚠️ PARTIAL | Base async streaming works, need full integration (v0.2.1) |

### Q2: User tiers as subcategory?

**YES** - Brilliant idea! Instead of rigid tiers, create flexible `UserProfile` system where tiers are ONE dimension among many:

```
UserProfile
├── tier (subscription) ← ONE subcategory, not the whole profile
├── limits (budgets, rate limits, quotas)
├── preferences (quality, latency, cost)
├── governance (guardrails, compliance, audit)
├── organization (multi-tenant)
├── workspace (dev/staging/prod)
└── telemetry (metrics, metadata)
```

**Key Benefits**:
- ✅ Flexible - Developers customize for their use case
- ✅ Powerful - 7 dimensions vs just "free/pro/enterprise"
- ✅ Optional - Simple by default, powerful when needed
- ✅ Production-ready - Handles thousands of users
- ✅ Multi-tenant - Organizations + workspaces

---

## Proposed Architecture

### Simple Usage (Most Developers)

```python
# Just use tier preset - that's it!
from cascadeflow import CascadeAgent, UserProfile, TierLevel

profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
agent = CascadeAgent.from_profile(profile)

result = await agent.run("Your query")
# Automatically enforces pro tier limits, preferences, features
```

### Advanced Usage (Production SaaS)

```python
# Full customization with organization + workspace
profile = UserProfile(
    user_id="user_123",

    # Organization (multi-tenant)
    organization=OrganizationConfig(
        organization_id="acme_corp",
        shared_budget=1000.00,  # Shared across all users
        compliance_mode="hipaa"
    ),

    # Workspace (dev/staging/prod)
    workspace=WorkspaceConfig(
        workspace_id="production",
        environment="production"
    ),

    # Tier (preset or custom)
    tier=TierConfig.from_preset(TierLevel.ENTERPRISE),

    # Custom preferences
    quality_preferences=QualityPreferences(
        target_quality=0.90,
        cost_sensitivity="quality_first"
    ),

    # Guardrails (safety)
    guardrails=GuardrailsConfig(
        enable_toxicity_detection=True,
        enable_pii_detection=True,
        pii_action="redact"
    )
)

agent = CascadeAgent.from_profile(profile)
```

---

## Tier System Design

### Predefined Tiers (Ready to Use)

| Tier | Daily Budget | Req/Hour | Features | Use Case |
|------|-------------|----------|----------|----------|
| **FREE** | $0.10 | 10 | Basic quality, safety guardrails | Hobby, learning |
| **STARTER** | $1.00 | 100 | + Streaming, domain routing | Side projects, MVPs |
| **PRO** | $10.00 | 1000 | + Batch, embeddings, all models | Startups, production apps |
| **BUSINESS** | $50.00 | 5000 | + Priority support, higher quality | Growing companies |
| **ENTERPRISE** | Unlimited | Unlimited | + Custom models, dedicated support | Large enterprises |

### Custom Tiers (Full Flexibility)

```python
# Create completely custom tier
custom_tier = TierConfig(
    name="startup_special",
    daily_budget=5.00,
    requests_per_hour=500,
    enable_streaming=True,
    enable_batch=True,
    allowed_models=["gpt-4o-mini", "claude-3-haiku"],  # Cost-effective only
    support_priority="priority"
)
```

---

## Multi-Dimensional Profiles (7 Dimensions)

### 1. Identity (Who)
- `user_id`, `organization_id`, `workspace_id`
- RBAC: roles, permissions
- Multi-tenant support

### 2. Tier (Subscription Level) ← ONE subcategory
- Predefined: free, starter, pro, business, enterprise
- Custom: your own tier definitions
- Inheritable: custom tiers can extend presets

### 3. Limits (What They Can Do)
- **Budgets**: daily, weekly, monthly, total
- **Rate limits**: requests/sec, requests/hour, requests/day
- **Token limits**: tokens/minute, tokens/hour
- **Quota limits**: usage caps

### 4. Preferences (How They Want It)
- **Quality**: minimum, target, maximum quality
- **Cost sensitivity**: aggressive, balanced, quality_first
- **Latency**: real_time, balanced, batch
- **Models**: preferred models, blocked models
- **Domains**: preferred domains (code, medical, etc.)

### 5. Governance (Safety & Compliance)
- **Guardrails**: content moderation, PII, toxicity, hallucination
- **Compliance**: HIPAA, GDPR, SOX
- **Audit logging**: minimal, standard, comprehensive
- **Data retention**: days to keep data

### 6. Organization (Multi-Tenant)
- **Shared budgets**: across all users in org
- **Data isolation**: per-region, per-tenant
- **Custom models**: org-specific fine-tuned models
- **Compliance requirements**: org-level policies

### 7. Telemetry (Observability)
- **Cost tracking**: automatic
- **Usage metrics**: requests, tokens, models
- **Quality metrics**: semantic quality scores
- **Custom metadata**: your own tracking data

---

## Developer Experience - Why This is Better

### Before (v0.2.0)
```python
# Manual budget management, no tier concept
tracker = CostTracker(
    user_budgets={
        'user_1': BudgetConfig(daily=0.10),  # Must manually map each user
        'user_2': BudgetConfig(daily=1.00),
        'user_3': BudgetConfig(daily=10.00),
        # ... repeat for thousands of users
    }
)
```

**Problems**:
- ❌ No tier abstraction
- ❌ Budget only (no rate limits, preferences, guardrails)
- ❌ Hard to scale (manual mapping)
- ❌ No organization/workspace support

### After (v0.2.1+)
```python
# Simple: Use tier preset
profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
agent = CascadeAgent.from_profile(profile)

# Or load from database
manager = UserProfileManager()
profile = await manager.get_profile("user_123")  # Cached, fast
agent = CascadeAgent.from_profile(profile)
```

**Benefits**:
- ✅ Tier abstraction (free, pro, enterprise)
- ✅ 7 dimensions (budget, limits, preferences, guardrails, org, workspace, telemetry)
- ✅ Scales to thousands (profile manager with caching)
- ✅ Multi-tenant (organizations + workspaces)
- ✅ Flexible (custom tiers, overrides)
- ✅ Optional (simple by default, powerful when needed)

---

## Implementation Roadmap

### v0.2.1 (WEEK 4-6) - Foundation
**Goal**: Basic UserProfile system with tier presets

- ✅ Define `UserProfile` data structure
- ✅ Define 5 predefined tier presets (free, starter, pro, business, enterprise)
- ✅ Implement `UserProfileManager` (caching, DB integration)
- ✅ Integrate with `CascadeAgent.from_profile()`
- ✅ Migrate from `BudgetConfig` to `UserProfile` (backward compatible)
- ✅ Rate limiting (per-user, per-tier)
- ✅ Basic guardrails (content moderation, PII)

**Code Example**:
```python
# v0.2.1 - Basic tier system
profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
agent = CascadeAgent.from_profile(profile)
result = await agent.run("query")  # Auto-enforces pro tier limits
```

### v0.2.2 (WEEK 7-9) - Advanced Features
**Goal**: Quality preferences, advanced guardrails, batch processing

- ✅ `QualityPreferences` (quality vs cost vs speed tradeoffs)
- ✅ Advanced guardrails (toxicity detection, opt-in)
- ✅ Batch completion (using LiteLLM batch API)
- ✅ Custom tier creation (beyond presets)
- ✅ Budget forecasting (predict overrun)

**Code Example**:
```python
# v0.2.2 - Quality preferences + batch
profile = UserProfile(
    user_id="user_123",
    tier=TierConfig.from_preset(TierLevel.PRO),
    quality_preferences=QualityPreferences(
        target_quality=0.90,
        cost_sensitivity="quality_first"
    )
)

# Batch processing
agent = CascadeAgent.from_profile(profile)
results = await agent.run_batch([...])  # Process multiple queries
```

### v0.3.0 (WEEK 10-12) - Multi-Tenant & Enterprise
**Goal**: Organization/workspace support, compliance, custom models

- ✅ `OrganizationConfig` (multi-tenant support)
- ✅ `WorkspaceConfig` (dev/staging/prod)
- ✅ Shared budgets (org-level)
- ✅ Compliance modes (HIPAA, GDPR, SOX)
- ✅ Custom models (org-specific fine-tuned models)
- ✅ Embeddings API (expose for users)
- ✅ Hallucination detection (opt-in, experimental)

**Code Example**:
```python
# v0.3.0 - Full multi-tenant with compliance
profile = UserProfile(
    user_id="user_123",
    organization=OrganizationConfig(
        organization_id="acme_corp",
        shared_budget=1000.00,
        compliance_mode="hipaa",
        data_region="us-east-1"
    ),
    workspace=WorkspaceConfig(
        workspace_id="production",
        environment="production"
    ),
    tier=TierConfig.from_preset(TierLevel.ENTERPRISE)
)

agent = CascadeAgent.from_profile(profile)
# Automatically enforces HIPAA compliance, org budget, workspace isolation
```

---

## Production Best Practices

### For SaaS Apps with Thousands of Users

#### 1. Use UserProfileManager (Caching)
```python
# Initialize once at startup
manager = UserProfileManager(cache_ttl_seconds=300)  # 5 min cache

# Fast lookups (cached)
async def handle_request(user_id: str, query: str):
    profile = await manager.get_profile(user_id)  # Fast (cached)
    agent = CascadeAgent.from_profile(profile)
    return await agent.run(query)
```

#### 2. Database Integration
```python
# Store profiles in your database (PostgreSQL, MongoDB, etc.)
class PostgreSQLProfileManager(UserProfileManager):
    async def _load_from_database(self, user_id: str):
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_profiles WHERE user_id = $1",
                user_id
            )
            return UserProfile.from_dict(row) if row else None

    async def _save_to_database(self, profile: UserProfile):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_profiles VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET data = $2",
                profile.user_id, profile.to_dict()
            )
```

#### 3. Bulk Operations
```python
# Create 1000 free tier users efficiently
profiles = manager.create_bulk([
    {"user_id": f"user_{i}", "tier": "free"}
    for i in range(1000)
])
```

#### 4. Tier Upgrades
```python
# Upgrade user from free to pro
await manager.update_tier("user_123", TierLevel.PRO)
# Automatically invalidates cache, loads new tier settings
```

#### 5. Organization-Wide Budgets
```python
# Shared budget across all users in organization
org_profile = UserProfile(
    user_id="user_123",
    organization=OrganizationConfig(
        organization_id="acme_corp",
        shared_budget=1000.00  # Shared by all acme_corp users
    ),
    tier=TierConfig.from_preset(TierLevel.BUSINESS)
)
```

---

## Migration from v0.2.0

### Backward Compatible ✅

```python
# v0.2.0 code still works (no breaking changes)
tracker = CostTracker(
    user_budgets={'user_123': BudgetConfig(daily=1.00)}
)

# v0.2.1+ recommended way
profile = UserProfile.from_tier(TierLevel.PRO, user_id="user_123")
# Internally creates BudgetConfig, fully compatible
```

### Migration Path

**Step 1**: Keep using `BudgetConfig` (v0.2.0 works in v0.2.1)

**Step 2**: Gradually migrate to `UserProfile` (optional, recommended)

**Step 3**: Use advanced features when needed (multi-tenant, guardrails, etc.)

---

## Key Decisions

### ✅ YES - Build User Profile System
**Why**:
- Flexible (7 dimensions, not just tiers)
- Powerful (handles enterprise multi-tenant needs)
- Optional (simple by default, 1 line for basic usage)
- Scalable (profile manager with caching for thousands of users)

### ✅ YES - Tiers as Subcategory (Not Entire Profile)
**Why**:
- More flexible than rigid free/pro/enterprise
- Allows custom tiers, overrides, multi-dimensional config
- Better DX - developers can customize for their use case

### ✅ YES - Predefined Tier Presets
**Why**:
- 80% of developers just want free/pro/enterprise
- Sensible defaults (daily budgets, rate limits, features)
- Can customize or create custom tiers

### ✅ YES - Multi-Tenant Support (Organizations + Workspaces)
**Why**:
- Essential for B2B SaaS
- Shared budgets, data isolation, compliance
- Multiple workspaces per org (dev/staging/prod)

### ✅ YES - Backward Compatible
**Why**:
- v0.2.0 `BudgetConfig` still works
- Gradual migration path
- No breaking changes

---

## Summary Table

| Aspect | v0.2.0 (Current) | v0.2.1+ (Proposed) | Improvement |
|--------|------------------|-------------------|-------------|
| **Tier System** | ❌ None | ✅ 5 presets + custom | Easier setup |
| **Dimensions** | 1 (budget) | 7 (budget, limits, prefs, etc.) | 7x more flexible |
| **Multi-Tenant** | ❌ No | ✅ Org + workspace | Enterprise-ready |
| **Rate Limiting** | ❌ No | ✅ Per-user/tier | Production-ready |
| **Guardrails** | ❌ No | ✅ Built-in | Safety + compliance |
| **Quality Prefs** | ❌ No | ✅ Customizable | Better control |
| **Scaling** | Manual mapping | ✅ Profile manager | Handles thousands |
| **DX** | Complex | ✅ Simple (1 line) | 95% easier |

---

## Next Steps

### Immediate (This Week)
1. ✅ **Review design** - This document + full design doc
2. ✅ **Validate approach** - Confirm this solves your use case
3. ✅ **Prioritize features** - Which parts for v0.2.1, v0.2.2, v0.3.0

### Short-Term (v0.2.1 - WEEK 4-6)
1. 🔨 **Implement UserProfile** - Data structures, presets
2. 🔨 **Implement ProfileManager** - Caching, DB integration
3. 🔨 **Integrate with CascadeAgent** - `from_profile()` method
4. 🔨 **Rate limiting** - Per-user, per-tier
5. 🔨 **Basic guardrails** - Content moderation, PII

### Medium-Term (v0.2.2 - WEEK 7-9)
1. 🔨 **Quality preferences** - Cost vs quality vs speed tradeoffs
2. 🔨 **Advanced guardrails** - Toxicity, hallucination (opt-in)
3. 🔨 **Batch completion** - Using LiteLLM batch API
4. 🔨 **Custom tiers** - Beyond presets

### Long-Term (v0.3.0 - WEEK 10-12)
1. 🔨 **Multi-tenant** - Organizations + workspaces
2. 🔨 **Compliance** - HIPAA, GDPR, SOX modes
3. 🔨 **Custom models** - Org-specific fine-tuned models
4. 🔨 **Embeddings API** - Expose for users

---

## Questions for You

1. **Timeline**: Does v0.2.1 (WEEK 4-6) timeline work for user profile system?

2. **Priorities**: Which features are most critical for v0.2.1?
   - Tier system (free/pro/enterprise)?
   - Rate limiting?
   - Guardrails?
   - Quality preferences?

3. **Database**: What database will you use for profile storage?
   - PostgreSQL?
   - MongoDB?
   - Redis?
   - Other?

4. **Multi-Tenant**: Do you need organizations + workspaces in v0.2.1 or can wait for v0.3.0?

5. **Custom Tiers**: Will users create custom tiers or mainly use presets?

---

**Status**: ✅ Design complete, ready for implementation
**Next Action**: Review design, confirm approach, prioritize features for v0.2.1
**Full Design**: See `USER_PROFILE_SYSTEM_DESIGN.md`
