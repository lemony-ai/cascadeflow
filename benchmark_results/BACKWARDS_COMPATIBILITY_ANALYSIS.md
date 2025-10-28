# Backwards Compatibility Analysis
**Date**: October 28, 2025
**Question**: Why do tests fail if we claim backwards compatibility?

## Executive Summary

**Answer**: We do NOT have backwards compatibility for the `tiers` and `enable_caching` parameters. The tests are failing because they were written for **a future API that was planned but never fully implemented**.

---

## The Truth About "Backwards Compatibility"

### What IS Backwards Compatible ✅

1. **Text Queries** - Simple queries work the same way
```python
# v0.1.x AND v2.5
agent = CascadeAgent(models=[...])
result = await agent.run("What is 2+2?")
```

2. **Basic Agent Initialization** - Core parameters
```python
# v0.1.x AND v2.5
agent = CascadeAgent(
    models=[...],
    verbose=True
)
```

3. **Tool Calling** - Universal tool format
```python
# v0.1.x AND v2.5
result = await agent.run(
    "Get weather in SF",
    tools=[weather_tool]
)
```

### What IS NOT Backwards Compatible ❌

1. **Tiers Parameter** - NEVER IMPLEMENTED
```python
# DOES NOT EXIST IN v2.5
agent = CascadeAgent(
    models=[...],
    tiers={'free': {...}, 'pro': {...}}  # ❌ NOT SUPPORTED
)
```

2. **Workflows Parameter** - NEVER IMPLEMENTED
```python
# DOES NOT EXIST IN v2.5
agent = CascadeAgent(
    models=[...],
    workflows={'medical': {...}}  # ❌ NOT SUPPORTED
)
```

3. **Enable Caching Parameter** - NEVER IMPLEMENTED
```python
# DOES NOT EXIST IN v2.5
agent = CascadeAgent(
    models=[...],
    enable_caching=True  # ❌ NOT SUPPORTED
)
```

4. **Enable Callbacks Parameter** - NEVER IMPLEMENTED
```python
# DOES NOT EXIST IN v2.5
agent = CascadeAgent(
    models=[...],
    enable_callbacks=True  # ❌ NOT SUPPORTED
)
```

---

## Where Did These Parameters Come From?

### From V0.2.0_FINAL_PLAN.md (18-Week Plan)

The V0.2.0 plan outlined these features for **FUTURE** implementation:

**Phase 1 (Weeks 1-3)**: Budget Enforcement
- Tier-based budget limits
- User tier policies (free vs pro)
- Enforcement callbacks

**Phase 5 (Weeks 13-15)**: Tier Routing + Presets 2.0
- `cascadeflow/routing/tier_routing.py`
- `TierModelPolicy` dataclass
- Tier-aware model selection

**Quote from Plan**:
```
Milestone 1.2: Enforcement Callbacks (Week 2)
- [ ] EnforcementCallbacks class
- [ ] filter_models() callback (tier-based model filtering)
```

### The Tests Were Written for the PLAN, Not Reality

The tests in `tests/test_agent.py` and `tests/test_agent_integration.py` were written **aspirationally** - they test features that were **planned but not implemented**.

**Evidence**:
```python
# tests/test_agent.py line 134-140
agent = CascadeAgent(
    models=mock_models,
    tiers=mock_tiers,           # ❌ Planned for Week 13-15
    workflows=mock_workflows,    # ❌ Never in any plan
    enable_caching=True,        # ❌ Planned but not implemented
    enable_callbacks=True,      # ❌ Planned for Week 2
    verbose=True,
)
```

---

## What WAS Actually Implemented?

### Current v2.5 CascadeAgent API

```python
class CascadeAgent:
    def __init__(
        self,
        models: list[ModelConfig],           # ✅ IMPLEMENTED
        quality_config: Optional[QualityConfig] = None,  # ✅ IMPLEMENTED
        enable_cascade: bool = True,         # ✅ IMPLEMENTED
        verbose: bool = False,               # ✅ IMPLEMENTED
    ):
```

**That's it.** Four parameters, not eight.

### What Infrastructure Exists?

#### 1. Callbacks - Partially Implemented ⚠️

**File**: `cascadeflow/telemetry/callbacks.py`

**What Exists**:
- `CallbackManager` class ✅
- `CallbackEvent` enum ✅
- `CallbackData` dataclass ✅
- Event triggering system ✅

**What's Missing**:
- ❌ NOT wired into `CascadeAgent.__init__()`
- ❌ No `enable_callbacks` parameter
- ❌ No auto-registration system
- ❌ Agent doesn't trigger callback events

**Status**: Infrastructure exists, integration missing

#### 2. Tiers - NOT Implemented ❌

**Search Results**:
```bash
$ find cascadeflow/ -name "*tier*.py"
# No files found
```

**What's Missing**:
- ❌ No `TierModelPolicy` class
- ❌ No tier-based routing
- ❌ No tier-based budget enforcement
- ❌ No `cascadeflow/routing/tier_routing.py`

**Status**: Completely unimplemented (planned for Phase 5, Weeks 13-15)

#### 3. Caching - NOT Implemented ❌

**Search Results**:
```bash
$ grep -r "cache" cascadeflow/agent.py
# No results
```

**What's Missing**:
- ❌ No cache infrastructure
- ❌ No `enable_caching` parameter
- ❌ No `agent.cache` attribute

**Status**: Not mentioned in V0.2.0 plan, completely unimplemented

#### 4. Workflows - NOT Implemented ❌

**What's Missing**:
- ❌ No workflow system
- ❌ No workflow routing
- ❌ Not mentioned in V0.2.0 plan

**Status**: Never planned, never implemented

---

## How Do We Handle Tiers and Callbacks NOW?

### Short Answer: We Don't ❌

The current v2.5 implementation does NOT support:
- User tiers
- Tier-based routing
- Tier-based budget enforcement
- Callback system integration
- Caching
- Workflows

### What CAN Users Do? (Current v2.5)

#### 1. Manual Model Selection (Tier Workaround)

```python
# Free tier users - cheap models only
free_tier_models = [
    ModelConfig(name='llama-3.1-8b-instant', provider='groq', cost=0.00005),
    ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
]

free_agent = CascadeAgent(models=free_tier_models)

# Pro tier users - include expensive models
pro_tier_models = [
    ModelConfig(name='llama-3.1-8b-instant', provider='groq', cost=0.00005),
    ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
    ModelConfig(name='gpt-4o', provider='openai', cost=0.0025),
]

pro_agent = CascadeAgent(models=pro_tier_models)
```

**Workaround**: Create different agent instances per tier

#### 2. Manual Callback Integration

```python
from cascadeflow.telemetry.callbacks import CallbackManager, CallbackEvent

# Create callback manager manually
callback_manager = CallbackManager(verbose=True)

def on_query_complete(data):
    print(f"Query cost: ${data.data.get('total_cost', 0):.6f}")

callback_manager.register(CallbackEvent.QUERY_COMPLETE, on_query_complete)

# NO WAY TO PASS IT TO AGENT! ❌
agent = CascadeAgent(models=[...])  # No callback parameter
```

**Problem**: Even though `CallbackManager` exists, there's no way to integrate it with the agent.

#### 3. Custom Budget Enforcement

```python
# Manual enforcement OUTSIDE the agent
user_spent_today = 0.05
user_budget = 0.10

result = await agent.run("Query...")

user_spent_today += result.total_cost

if user_spent_today >= user_budget:
    raise Exception("Budget exceeded!")
```

**Workaround**: Track budgets externally, don't use the agent

---

## The Plan vs Reality Gap

### V0.2.0 Plan Said (18 weeks):

**Phase 1** (Weeks 1-3): Budget enforcement with tiers and callbacks
**Phase 2** (Weeks 4-6): Provider integration
**Phase 3** (Weeks 7-9): Quality enhancements
**Phase 4** (Weeks 10-12): Domain routing
**Phase 5** (Weeks 13-15): Tier routing + Presets 2.0
**Phase 6** (Weeks 16-18): n8n + comprehensive testing

### What Was Actually Built:

**Phase 1**: ❌ Budget enforcement NOT built (callbacks exist but not integrated)
**Phase 2**: ✅ Provider integration COMPLETE
**Phase 3**: ✅ Quality system COMPLETE
**Phase 4**: ✅ Domain routing COMPLETE
**Phase 5**: ⚠️ Presets 2.0 NOT built, tier routing NOT built
**Phase 6**: ⚠️ n8n still at v0.1.1, testing partial

**Reality**: Skipped directly from Phase 1 planning → Phase 2-4 implementation → stopped before Phase 1 and 5

---

## Why the Mismatch?

### Theory 1: Test-Driven Development Gone Wrong

Someone wrote tests for the PLANNED API before implementing it, then never went back to implement the features.

### Theory 2: Rapid Prototyping

Focus shifted to core functionality (cascading, routing, quality) rather than user-facing features (tiers, callbacks, caching).

### Theory 3: Changing Priorities

The plan was made, core features got built, but tier/callback features were deprioritized.

---

## What Should We Do?

### Option 1: Implement Tiers + Callbacks (Comprehensive) - 2-3 weeks

**Scope**: Build everything in Phase 1 and Phase 5 of the plan
- Tier routing system
- Callback integration in agent
- Budget enforcement
- Caching system

**Pros**:
- Tests would pass
- Feature-complete as planned
- User tier support

**Cons**:
- 2-3 weeks of work
- Delays launch significantly

### Option 2: Fix Tests to Match Reality (Pragmatic) - 2-4 hours ⭐ RECOMMENDED

**Scope**: Update tests to match current v2.5 API
- Remove `tiers` parameter from tests
- Remove `enable_caching` from tests
- Remove `enable_callbacks` from tests
- Remove `workflows` from tests

**Pros**:
- Quick fix (2-4 hours)
- Tests validate actual implementation
- Can launch immediately

**Cons**:
- Still no tier/callback support
- Need to implement later if needed

### Option 3: Add Backwards Compatibility Layer - 1-2 days

**Scope**: Accept old parameters but ignore them
```python
def __init__(
    self,
    models: list[ModelConfig],
    quality_config: Optional[QualityConfig] = None,
    enable_cascade: bool = True,
    verbose: bool = False,
    # Deprecated - accepted but ignored
    tiers: Optional[dict] = None,
    workflows: Optional[dict] = None,
    enable_caching: bool = False,
    enable_callbacks: bool = False,
):
    if tiers is not None:
        logger.warning("tiers parameter is deprecated and will be ignored")
    if enable_caching:
        logger.warning("enable_caching is not yet implemented")
    # ... continue with normal init
```

**Pros**:
- Tests pass (with warnings)
- Doesn't break anything
- Easy migration path

**Cons**:
- Features still don't work
- Confusing for users
- Technical debt

---

## Recommendation

### Short-term: Option 2 (Fix Tests) ⭐

**Rationale**:
- Tests should validate what EXISTS, not what's PLANNED
- Fastest path to green build (2-4 hours)
- Honest about current capabilities
- Can launch v0.1.1 immediately

### Long-term: Option 1 (Implement Features)

**Timeline**:
- After v0.1.1 launch
- Implement in v0.2.0 or v0.3.0
- Follow original Phase 1 + Phase 5 plan
- 2-3 weeks of focused development

---

## Conclusion

**Answer to "Why aren't we backwards compatible?"**

We ARE backwards compatible for core functionality (basic agent usage, text queries, tools).

We are NOT backwards compatible for features that:
1. Were never implemented (tiers, workflows, caching)
2. Were partially implemented but not integrated (callbacks)
3. Only exist in the 18-week plan (Phase 1, Phase 5)

The tests fail because they test a PLANNED API, not the CURRENT API.

**Fix**: Update tests to match v2.5 reality (2-4 hours), then implement Phase 1+5 features post-launch if needed (2-3 weeks).

---

**Current v2.5 API** (ACTUAL):
```python
CascadeAgent(
    models=[...],
    quality_config=...,
    enable_cascade=True,
    verbose=False
)
```

**Test API** (ASPIRATIONAL):
```python
CascadeAgent(
    models=[...],
    tiers={...},           # ❌ Never implemented
    workflows={...},       # ❌ Never implemented
    enable_caching=True,   # ❌ Never implemented
    enable_callbacks=True, # ❌ Exists but not integrated
)
```

**Status**: Tests are ahead of implementation, not behind.
