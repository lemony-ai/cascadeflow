# CascadeFlow v0.2.0 Development Context

**Branch:** `feature/cost-control-quality-v2`
**Current Phase:** Phase 1, Milestone 1.1 - Per-User Budget Tracking
**Date:** 2025-10-27

---

## 🎯 Current Development Status

### Active Milestone: 1.1 - Per-User Budget Tracking (Week 1)

**Goal:** Add per-user cost tracking and budget management

**Status:** Design phase - validating lean approach that reuses existing code

**Key Principle:** Extend existing code, don't duplicate. Stay lean.

---

## 📁 Existing Code Structure (27K lines)

### Core Modules
```
cascadeflow/
├── agent.py (63KB) - Main CascadeAgent
├── __init__.py (6.7KB) - Package exports
├── core/
│   ├── cascade.py - Cascade execution logic
│   └── execution.py - Execution engine
├── providers/ (10 files)
│   ├── base.py - Provider interface
│   ├── openai.py, anthropic.py, groq.py
│   ├── ollama.py, together.py, huggingface.py
│   └── vllm.py - Already has vLLM support!
├── quality/ (9 files)
│   ├── quality.py - Quality validation
│   ├── confidence.py - Confidence scoring
│   └── complexity.py - Query complexity
├── routing/ (8 files)
│   ├── router.py - Main router
│   ├── complexity_router.py
│   └── tool_router.py
├── schema/
│   ├── config.py (21KB) - IMPORTANT: Has UserTier, ModelConfig
│   ├── result.py - CascadeResult
│   └── exceptions.py - Has BudgetExceededError
├── telemetry/ (4 files)
│   ├── cost_tracker.py (6.9KB) - EXTEND THIS
│   ├── cost_calculator.py (26KB)
│   ├── collector.py (34KB)
│   └── callbacks.py (7KB)
├── utils/
│   └── presets.py - Preset configurations
└── streaming/, tools/, interface/
```

### Key Existing Classes to Reuse

**`UserTier` (in schema/config.py):**
- ✅ Already has `max_budget` field
- ✅ Already has `preferred_budget` field
- ✅ Used by DEFAULT_TIERS (free, standard, premium, enterprise)
- ⚠️ **These are per-query budgets, not per-user budgets**

**`CostTracker` (in telemetry/cost_tracker.py):**
- ✅ Already tracks: `total_cost`, `by_model`, `by_provider`, `entries`
- ✅ Already has: `budget_limit`, `warn_threshold`, `budget_warned`, `budget_exceeded`
- 🎯 **We need to add:** `by_user` dict, `user_entries` dict, per-user budget checking

**`BudgetExceededError` (in schema/exceptions.py):**
- ✅ Already exists! Can reuse for user budget exceeded

**Existing Tests:**
- tests/test_config.py - Tests ModelConfig, UserTier
- tests/test_callbacks.py - Tests callback system
- tests/ - No test_cost_tracker.py yet (we need to create)

---

## ✅ LEAN Design for Milestone 1.1

### What We're Adding (Minimal Changes)

**1. New Dataclass: `BudgetConfig` (in telemetry/cost_tracker.py)**
```python
@dataclass
class BudgetConfig:
    """Per-user/tier budget limits (NEW in v0.2.0)."""
    daily: Optional[float] = None
    weekly: Optional[float] = None
    monthly: Optional[float] = None
    total: Optional[float] = None
```

**Why new class?**
- ✅ `UserTier.max_budget` is per-query, this is per-user/period
- ✅ Supports multiple periods (daily/weekly/monthly)
- ✅ Keeps telemetry module self-contained
- ✅ Only ~15 lines of code

**2. Enhance `CostTracker` (in telemetry/cost_tracker.py)**

Add to `__init__`:
```python
# NEW: Per-user tracking
user_budgets: Optional[dict[str, BudgetConfig]] = None
self.by_user: dict[str, float] = defaultdict(float)
self.user_entries: dict[str, list[CostEntry]] = defaultdict(list)
```

Add to `add_cost`:
```python
# NEW parameter: user_id: Optional[str] = None
if user_id:
    self.by_user[user_id] += cost
    self.user_entries[user_id].append(entry)
```

Add methods:
- `_check_user_budget(user_id, user_tier)` - Check budget limits
- `get_user_summary(user_id, user_tier)` - Get per-user cost summary
- `get_all_users()` - List tracked users
- `get_users_by_tier(tier)` - Get users by tier

**Total LOC:** ~150 lines added to existing 225-line file

**3. Tests (tests/test_cost_tracker.py - NEW FILE)**
- 10+ test cases
- ~200 lines
- Covers: backward compat, per-user tracking, budget warnings, performance

**Total New Code:** ~365 lines (very lean!)

---

## 🚫 What We're NOT Doing (Keep Lean)

- ❌ NOT creating new schema classes (reuse UserTier, BudgetExceededError)
- ❌ NOT modifying schema/config.py (too many dependencies)
- ❌ NOT adding time-based budget resets yet (defer to Milestone 1.2)
- ❌ NOT adding enforcement callbacks yet (defer to Milestone 1.2)
- ❌ NOT modifying agent.py yet (wait until we integrate)
- ❌ NOT touching routing/ or quality/ (future milestones)

---

## 🎯 Development Workflow

### Before Writing Code
1. ✅ Read existing code to understand structure
2. ✅ Identify what can be reused vs needs creation
3. ✅ Design minimal API that extends (not replaces)
4. ⏸️ **Get user validation on design**

### During Implementation
1. Write code in small chunks (one method at a time)
2. Test each method immediately
3. Validate backward compatibility
4. Keep diff minimal

### After Implementation
1. Run full test suite
2. Validate real-world benefit (Sarah's scenario)
3. Update documentation
4. Commit with clear message

---

## 📊 Reusability Map

**Reuse:**
- ✅ `UserTier` for tier-based budget lookup
- ✅ `BudgetExceededError` for exceptions
- ✅ `CostEntry` for tracking
- ✅ `CostTracker` (enhance, don't replace)
- ✅ Test structure from test_config.py

**Create New:**
- 🆕 `BudgetConfig` dataclass (15 LOC)
- 🆕 Per-user tracking in `CostTracker` (150 LOC)
- 🆕 test_cost_tracker.py (200 LOC)
- 🆕 API documentation

**Total New Code:** ~365 LOC (1.4% increase from 27K base)

---

## 🔄 Integration Points (Future Milestones)

### Milestone 1.2: Enforcement Callbacks
- Will use `EnforcementCallbacks` class (new)
- Will integrate with `CostTracker._check_user_budget()`

### Milestone 1.3: Graceful Degradation
- Will use `UserTier.max_budget` for per-query limits
- Will use `BudgetConfig` for per-user limits
- Both work together

### Phase 2: LiteLLM Integration
- Will use `CostTracker` for tracking
- Will use LiteLLM for pricing database
- Clean separation of concerns

---

## ⚠️ Design Constraints

1. **Backward Compatibility:** All v0.1.1 code must still work
2. **No Breaking Changes:** Don't modify existing public APIs
3. **Minimal Dependencies:** Only use stdlib + pydantic (already required)
4. **Keep Tests Fast:** <100ms for unit tests
5. **Memory Efficient:** O(users) space, not O(queries)

---

## 📝 Current Questions for User

1. Is `BudgetConfig` the right approach vs extending `UserTier`?
   - **Rationale:** Keeps telemetry self-contained, UserTier is per-query focused
2. Should we add time-based resets now or defer to Milestone 1.2?
   - **Recommendation:** Defer (adds complexity, can track cumulative for now)
3. Do we need weekly/monthly or just daily budgets?
   - **Recommendation:** Support all, but daily is most common for SaaS

---

## 🎯 Success Criteria for Milestone 1.1

### Code Quality
- ✅ <400 new LOC
- ✅ 100% test coverage for new code
- ✅ 100% backward compatible
- ✅ No performance regression

### Real-World Validation
- ✅ Sarah can enforce free tier budget with 10 lines of code
- ✅ Works with Stripe/Auth0 (tier-based budgets)
- ✅ <1ms overhead per add_cost call

### Production Ready
- ✅ Clear error messages
- ✅ Handles edge cases (missing user_id, invalid tier)
- ✅ Thread-safe (for async use)

---

## 📚 Relevant Files for This Milestone

**Read First:**
- cascadeflow/telemetry/cost_tracker.py
- cascadeflow/schema/config.py (UserTier)
- cascadeflow/schema/exceptions.py (BudgetExceededError)

**Will Modify:**
- cascadeflow/telemetry/cost_tracker.py (enhance)
- cascadeflow/telemetry/__init__.py (export BudgetConfig)

**Will Create:**
- tests/test_cost_tracker.py (new)

**Won't Touch Yet:**
- cascadeflow/agent.py (wait for integration)
- cascadeflow/schema/*.py (no schema changes)
- cascadeflow/routing/*.py (future phases)

---

## 🚀 Next Steps

1. ⏸️ **Awaiting user validation on lean design**
2. Implement BudgetConfig dataclass
3. Enhance CostTracker with per-user tracking
4. Write comprehensive tests
5. Validate real-world benefit
6. Document and commit

---

**Last Updated:** 2025-10-27
**Lines of Code:** 27,000 (baseline) → ~27,365 after Milestone 1.1 (+1.4%)
