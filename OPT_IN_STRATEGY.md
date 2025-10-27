# Opt-In Strategy for ML Features (UPDATED)

## Core Principle: Explicit Over Implicit

**ML features are OFF by default and require explicit opt-in.**

This approach:
- ✅ Maintains v0.1.1 behavior as default (no surprises)
- ✅ Zero performance regression for existing users
- ✅ Clear when ML dependencies are needed
- ✅ Follows principle of least surprise
- ✅ Production-safe (no unexpected latency)

---

## Default Behavior (No ML)

### Quality Validation

**Default: Rule-Based Only (Current v0.1.1 behavior)**

```python
# Default behavior - NO ML, NO additional dependencies
agent = CascadeAgent(models=[...])
result = await agent.run(query="...")

# Uses:
# ✅ Rule-based hedging detection
# ✅ Rule-based coherence analysis
# ✅ Rule-based completeness scoring
# ✅ Query-response alignment (existing logic)
# ✅ Multi-signal confidence estimation
# ❌ NO semantic similarity (requires opt-in)
# ❌ NO toxicity detection (requires opt-in)
# ❌ NO ML models loaded

# Performance: 3-5ms validation overhead (same as v0.1.1)
```

**Opt-In: Semantic Quality System**

```python
# EXPLICIT opt-in for ML-based quality
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig(
        enable_semantic_similarity=True,  # EXPLICIT
        enable_toxicity_detection=True,   # EXPLICIT
    )
)

# OR use preset helper
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.semantic()  # Requires pip install cascadeflow[semantic]
)

# If dependencies missing, gets clear error:
# ImportError: Semantic quality requires additional dependencies.
# Install with: pip install cascadeflow[semantic]
```

### Domain Detection

**Default: Rule-Based Only (Fast, No Dependencies)**

```python
# Default behavior - NO ML, pure rules + keywords
agent = CascadeAgent(
    models=[...],
    enable_domain_routing=True  # Still uses rule-based detection only
)

result = await agent.run(query="Write a Python function...")

# Domain detection process:
# 1. Keyword matching: "Python", "function" → code domain ✅
# 2. Pattern matching: code snippets, imports → code domain ✅
# 3. Format detection: ```python → code domain ✅
# ❌ NO semantic vector similarity (requires opt-in)
# ❌ NO zero-shot classifier (requires opt-in)
# ❌ NO ML models loaded

# Performance: <1ms detection (keyword/pattern matching only)
# Accuracy: 70-80% (sufficient for most cases)
```

**Opt-In: ML-Based Domain Detection**

```python
# EXPLICIT opt-in for ML-based domain detection
agent = CascadeAgent(
    models=[...],
    domain_config=DomainConfig(
        enable_semantic_routing=True,  # EXPLICIT - requires [semantic]
        enable_zero_shot_classifier=True,  # EXPLICIT - requires [semantic]
    )
)

# OR use preset helper
agent = CascadeAgent(
    models=[...],
    domain_config=DomainConfig.ml_enhanced()  # Requires pip install cascadeflow[semantic]
)

# Domain detection with ML:
# 1. Rules (fast path): 70-80% of queries, <1ms
# 2. Semantic router: 15-20% of queries, 10-50ms (if enabled)
# 3. Zero-shot classifier: 5-10% of queries, 200ms (if enabled)

# Performance: 10-50ms average (only when needed)
# Accuracy: 90-95% (significant improvement)
```

---

## Configuration Presets (Updated)

### Fast (Default - No ML)

```python
# Default preset - NO dependencies required
agent = CascadeAgent(models=[...])

# OR explicitly:
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.fast(),  # Rule-based only (default)
    domain_config=DomainConfig.fast(),    # Rule-based only (default)
)

# Features:
# ✅ Cost tracking (existing)
# ✅ Cascading (existing)
# ✅ User tiers (new, no ML needed)
# ✅ Budget enforcement (new, no ML needed)
# ✅ Rule-based quality validation (existing)
# ✅ Rule-based domain detection (new, no ML)

# Requirements:
# - Core dependencies only
# - No ML models
# - pip install cascadeflow

# Performance:
# - Validation: 3-5ms
# - Domain detection: <1ms
# - Total overhead: <10ms
```

### Balanced (Opt-In - Requires Semantic)

```python
# EXPLICIT opt-in for ML features
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.balanced(),  # Requires [semantic]
    domain_config=DomainConfig.balanced(),    # Requires [semantic]
)

# Features:
# ✅ Everything from Fast preset
# ✅ Semantic similarity validation (ML)
# ✅ Toxicity detection (ML)
# ✅ Semantic domain routing (ML)

# Requirements:
# - pip install cascadeflow[semantic]
# - ~500MB additional dependencies

# Performance:
# - Validation: 50-100ms
# - Domain detection: 10-50ms
# - Total overhead: 70-150ms

# Use case: Production APIs, content-sensitive apps
```

### Strict (Opt-In - Maximum Validation)

```python
# EXPLICIT opt-in for heavyweight validation
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.strict(),  # Requires [semantic]
)

# Features:
# ✅ Everything from Balanced
# ✅ Hallucination detection (SelfCheckGPT)
# ✅ LLM-as-judge (offline evaluation)

# Requirements:
# - pip install cascadeflow[semantic]
# - Additional inference cost (3-4x for hallucination detection)

# Performance:
# - Validation: 500-1000ms
# - Use async/offline only

# Use case: High-stakes domains (medical, legal, financial)
```

---

## Implementation: Explicit Opt-In Checks

### Quality Configuration

```python
# cascadeflow/config/quality.py

from typing import Optional
import logging

logger = logging.getLogger(__name__)

class QualityConfig:
    """Quality validation configuration with explicit opt-in for ML features."""

    def __init__(
        self,
        # Rule-based (always available, ON by default)
        enable_hedging_check: bool = True,
        enable_coherence_check: bool = True,
        enable_completeness_check: bool = True,
        enable_alignment_check: bool = True,

        # ML-based (requires opt-in, OFF by default)
        enable_semantic_similarity: bool = False,  # DEFAULT: OFF
        enable_toxicity_detection: bool = False,   # DEFAULT: OFF
        enable_hallucination_detection: bool = False,  # DEFAULT: OFF

        # Behavior
        strict_mode: bool = False,  # If True, error if ML enabled but deps missing
    ):
        self.enable_hedging_check = enable_hedging_check
        self.enable_coherence_check = enable_coherence_check
        self.enable_completeness_check = enable_completeness_check
        self.enable_alignment_check = enable_alignment_check

        self.enable_semantic_similarity = enable_semantic_similarity
        self.enable_toxicity_detection = enable_toxicity_detection
        self.enable_hallucination_detection = enable_hallucination_detection

        self.strict_mode = strict_mode

        # Validate ML features are available if enabled
        if self._ml_features_requested() and not self._ml_available():
            self._handle_missing_ml_dependencies()

    def _ml_features_requested(self) -> bool:
        """Check if any ML features are enabled."""
        return (
            self.enable_semantic_similarity
            or self.enable_toxicity_detection
            or self.enable_hallucination_detection
        )

    def _ml_available(self) -> bool:
        """Check if ML dependencies are installed."""
        try:
            import fastembed
            import transformers
            return True
        except ImportError:
            return False

    def _handle_missing_ml_dependencies(self):
        """Handle case where ML features requested but dependencies missing."""

        error_msg = (
            "ML-based quality features are enabled but dependencies not installed.\n\n"
            "Install with:\n"
            "  pip install cascadeflow[semantic]\n\n"
            "Or disable ML features:\n"
            "  quality_config = QualityConfig(enable_semantic_similarity=False)\n"
            "  # or\n"
            "  quality_config = QualityConfig.fast()  # Uses rules only"
        )

        if self.strict_mode:
            raise ImportError(error_msg)
        else:
            logger.error(error_msg)
            # Disable ML features
            self.enable_semantic_similarity = False
            self.enable_toxicity_detection = False
            self.enable_hallucination_detection = False

    @classmethod
    def fast(cls):
        """
        Fast preset using ONLY rule-based validation (default).

        NO ML dependencies required.
        Same as v0.1.1 behavior.
        """
        return cls(
            enable_semantic_similarity=False,
            enable_toxicity_detection=False,
            enable_hallucination_detection=False,
        )

    @classmethod
    def balanced(cls):
        """
        Balanced preset with ML-based validation (EXPLICIT OPT-IN).

        Requires: pip install cascadeflow[semantic]
        Raises ImportError if dependencies missing.
        """
        return cls(
            enable_semantic_similarity=True,  # EXPLICIT
            enable_toxicity_detection=True,   # EXPLICIT
            strict_mode=True,  # Raise error if deps missing
        )

    @classmethod
    def strict(cls):
        """
        Strict preset with maximum validation (EXPLICIT OPT-IN).

        Requires: pip install cascadeflow[semantic]
        """
        return cls(
            enable_semantic_similarity=True,
            enable_toxicity_detection=True,
            enable_hallucination_detection=True,
            strict_mode=True,
        )

    @classmethod
    def for_production(cls):
        """
        Production preset (DEFAULTS TO RULE-BASED).

        This is an alias for fast() to maintain backward compatibility.
        If you want ML validation, use balanced() explicitly.
        """
        return cls.fast()  # Default to rule-based
```

### Domain Configuration

```python
# cascadeflow/config/domain.py

class DomainConfig:
    """Domain detection configuration with explicit opt-in for ML."""

    def __init__(
        self,
        # Rule-based (always available, ON by default if domain routing enabled)
        enable_keyword_detection: bool = True,
        enable_pattern_matching: bool = True,
        enable_format_detection: bool = True,

        # ML-based (requires opt-in, OFF by default)
        enable_semantic_routing: bool = False,     # DEFAULT: OFF
        enable_zero_shot_classifier: bool = False, # DEFAULT: OFF

        # Behavior
        strict_mode: bool = False,
    ):
        self.enable_keyword_detection = enable_keyword_detection
        self.enable_pattern_matching = enable_pattern_matching
        self.enable_format_detection = enable_format_detection

        self.enable_semantic_routing = enable_semantic_routing
        self.enable_zero_shot_classifier = enable_zero_shot_classifier

        self.strict_mode = strict_mode

        # Validate ML features
        if self._ml_features_requested() and not self._ml_available():
            self._handle_missing_ml_dependencies()

    def _ml_features_requested(self) -> bool:
        return self.enable_semantic_routing or self.enable_zero_shot_classifier

    def _ml_available(self) -> bool:
        try:
            import fastembed
            from transformers import pipeline
            return True
        except ImportError:
            return False

    def _handle_missing_ml_dependencies(self):
        error_msg = (
            "ML-based domain detection is enabled but dependencies not installed.\n\n"
            "Install with:\n"
            "  pip install cascadeflow[semantic]\n\n"
            "Or disable ML features:\n"
            "  domain_config = DomainConfig.fast()  # Rules only"
        )

        if self.strict_mode:
            raise ImportError(error_msg)
        else:
            logger.error(error_msg)
            self.enable_semantic_routing = False
            self.enable_zero_shot_classifier = False

    @classmethod
    def fast(cls):
        """
        Fast preset using ONLY rule-based detection (default).

        NO ML dependencies required.
        Accuracy: 70-80%, Latency: <1ms
        """
        return cls(
            enable_semantic_routing=False,
            enable_zero_shot_classifier=False,
        )

    @classmethod
    def balanced(cls):
        """
        Balanced preset with semantic routing (EXPLICIT OPT-IN).

        Requires: pip install cascadeflow[semantic]
        Accuracy: 85-90%, Latency: 10-50ms
        """
        return cls(
            enable_semantic_routing=True,  # EXPLICIT
            enable_zero_shot_classifier=False,  # Too slow for standard use
            strict_mode=True,
        )

    @classmethod
    def ml_enhanced(cls):
        """
        ML-enhanced preset with full ML stack (EXPLICIT OPT-IN).

        Requires: pip install cascadeflow[semantic]
        Accuracy: 90-95%, Latency: 50-200ms
        """
        return cls(
            enable_semantic_routing=True,
            enable_zero_shot_classifier=True,
            strict_mode=True,
        )
```

### CascadeAgent Integration

```python
# cascadeflow/agent.py

class CascadeAgent:
    def __init__(
        self,
        models: list[ModelConfig],

        # Quality (defaults to rule-based)
        quality_config: Optional[QualityConfig] = None,

        # Domain routing (defaults to disabled)
        enable_domain_routing: bool = False,
        domain_config: Optional[DomainConfig] = None,

        # User tiers (no ML needed)
        tier_config: Optional[dict] = None,

        # Budget enforcement (no ML needed)
        cost_tracker: Optional[CostTracker] = None,

        **kwargs,
    ):
        self.models = models

        # Quality: Default to rule-based (v0.1.1 behavior)
        if quality_config is None:
            self.quality_config = QualityConfig.fast()
        else:
            self.quality_config = quality_config

        # Domain: Default to disabled
        self.enable_domain_routing = enable_domain_routing
        if enable_domain_routing and domain_config is None:
            # If domain routing enabled but no config, use fast (rule-based)
            self.domain_config = DomainConfig.fast()
        else:
            self.domain_config = domain_config

        # Initialize validators (lazy loading)
        self._quality_validator = None
        self._domain_detector = None

        # Other components...
        self.tier_config = tier_config
        self.cost_tracker = cost_tracker or CostTracker()

    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        user_tier: Optional[str] = None,
        **kwargs,
    ):
        """Run query with configured features."""

        # 1. Domain detection (if enabled)
        domain = None
        if self.enable_domain_routing:
            domain = await self._detect_domain(query)

        # 2. Tier validation (if configured)
        if user_tier and self.tier_config:
            self._validate_tier_constraints(user_tier)

        # 3. Budget check (if user_id provided)
        if user_id:
            self.cost_tracker.check_budget(user_id, user_tier)

        # 4. Model selection (considers domain if detected)
        draft_model, verifier_model = self._select_models(domain, user_tier)

        # 5. Draft execution
        draft_result = await self._execute_draft(query, draft_model)

        # 6. Quality validation
        quality_result = await self._validate_quality(query, draft_result)

        # 7. Cascade decision
        if quality_result.confidence > self._get_threshold(domain):
            final_result = draft_result
        else:
            final_result = await self._execute_verifier(query, verifier_model)

        # 8. Cost tracking
        self._track_cost(final_result, user_id, user_tier, domain)

        return final_result

    async def _detect_domain(self, query: str) -> Optional[str]:
        """Detect domain using configured detection method."""
        if self._domain_detector is None:
            from cascadeflow.domain import DomainDetector
            self._domain_detector = DomainDetector(self.domain_config)

        return await self._domain_detector.detect(query)

    async def _validate_quality(self, query: str, result) -> dict:
        """Validate quality using configured validators."""
        if self._quality_validator is None:
            from cascadeflow.quality import QualityValidator
            self._quality_validator = QualityValidator(self.quality_config)

        return await self._quality_validator.validate(query, result)
```

---

## User Experience Examples

### Example 1: Default (No ML, No Changes)

```python
# User upgrading from v0.1.1 - NO CHANGES NEEDED
agent = CascadeAgent(
    models=[
        ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
        ModelConfig(name='gpt-4o', provider='openai', cost=0.003),
    ]
)

result = await agent.run(query="What is 2+2?")

# Behavior:
# ✅ Uses rule-based quality validation (same as v0.1.1)
# ✅ No domain detection (disabled by default)
# ✅ Standard cascading logic
# ✅ No ML models loaded
# ✅ 3-5ms validation overhead (same as v0.1.1)
# ✅ Zero breaking changes
```

### Example 2: Add User Tiers (No ML)

```python
# Add user tiers - STILL NO ML NEEDED
agent = CascadeAgent(
    models=[...],
    tier_config={
        'free': TierConfig(daily_budget=0.10, allowed_models=['gpt-4o-mini']),
        'pro': TierConfig(daily_budget=5.00, allowed_models=['gpt-4o-mini', 'gpt-4o']),
    }
)

result = await agent.run(query="...", user_id='user_123', user_tier='pro')

# Behavior:
# ✅ Tier constraints enforced (no ML needed)
# ✅ Budget tracking (no ML needed)
# ✅ Still rule-based quality validation
# ✅ No additional dependencies required
```

### Example 3: Enable Domain Routing (Rule-Based)

```python
# Enable domain routing - USES RULES ONLY BY DEFAULT
agent = CascadeAgent(
    models=[...],
    enable_domain_routing=True,  # No ML, just keywords/patterns
)

result = await agent.run(query="Write a Python function for binary search")

# Behavior:
# ✅ Domain detected: 'code' (via keywords "Python", "function")
# ✅ Detection time: <1ms
# ✅ Accuracy: 70-80% (good enough for most cases)
# ✅ No ML dependencies needed
# ✅ Routes to appropriate model based on domain
```

### Example 4: Opt-In to Semantic Quality

```python
# EXPLICIT opt-in for ML-based quality
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.balanced()  # REQUIRES pip install cascadeflow[semantic]
)

# If semantic not installed:
# ImportError: ML-based quality features are enabled but dependencies not installed.
#
# Install with:
#   pip install cascadeflow[semantic]
#
# Or disable ML features:
#   quality_config = QualityConfig.fast()

# After installing cascadeflow[semantic]:
result = await agent.run(query="...")

# Behavior:
# ✅ Uses semantic similarity validation (+20-30ms)
# ✅ Uses toxicity detection (+50-100ms)
# ✅ 10x better quality detection
# ✅ Total overhead: ~70-130ms
```

### Example 5: Opt-In to ML Domain Detection

```python
# EXPLICIT opt-in for ML-based domain detection
agent = CascadeAgent(
    models=[...],
    enable_domain_routing=True,
    domain_config=DomainConfig.balanced()  # REQUIRES pip install cascadeflow[semantic]
)

result = await agent.run(query="Ambiguous query here...")

# Behavior:
# 1. Tries rule-based first (<1ms)
# 2. If uncertain, uses semantic routing (10-50ms)
# 3. Accuracy: 90-95% (vs 70-80% rules-only)
```

### Example 6: Full ML Stack (Production API)

```python
# EXPLICIT opt-in for full ML features
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.balanced(),  # Semantic quality
    enable_domain_routing=True,
    domain_config=DomainConfig.balanced(),    # Semantic routing
    tier_config={...},                        # User tiers (no ML)
)

# Requires: pip install cascadeflow[semantic]

result = await agent.run(
    query="...",
    user_id='user_123',
    user_tier='pro'
)

# Behavior:
# ✅ Full tier management
# ✅ Budget enforcement
# ✅ ML domain detection (90-95% accurate)
# ✅ Semantic quality validation (10x better)
# ✅ Toxicity detection
# ✅ Total overhead: 80-150ms (acceptable for quality gain)
```

---

## Error Messages (Clear & Actionable)

### Quality - ML Not Installed

```python
>>> agent = CascadeAgent(models=[...], quality_config=QualityConfig.balanced())

ImportError: ML-based quality features are enabled but dependencies not installed.

Install with:
  pip install cascadeflow[semantic]

Or disable ML features:
  quality_config = QualityConfig.fast()  # Uses rules only
  # or
  agent = CascadeAgent(models=[...])  # Default is fast (rules-only)
```

### Domain - ML Not Installed

```python
>>> agent = CascadeAgent(
...     models=[...],
...     enable_domain_routing=True,
...     domain_config=DomainConfig.balanced()
... )

ImportError: ML-based domain detection is enabled but dependencies not installed.

Install with:
  pip install cascadeflow[semantic]

Or use rule-based detection:
  domain_config = DomainConfig.fast()  # Keywords/patterns only (70-80% accuracy)
  # or
  agent = CascadeAgent(models=[...], enable_domain_routing=True)  # Default is fast
```

---

## Documentation Updates

### Updated Quick Start

```markdown
## Quick Start

### 1. Install CascadeFlow

```bash
pip install cascadeflow
```

This installs the core features:
- ✅ Cost optimization (60-85% savings)
- ✅ User tier management
- ✅ Budget enforcement
- ✅ Rule-based quality validation
- ✅ Multi-provider support

### 2. Basic Usage

```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(
    models=[
        ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
        ModelConfig(name='gpt-4o', provider='openai', cost=0.003),
    ]
)

result = await agent.run(query="What is 2+2?")
print(result.content)
```

### 3. Add ML Features (Optional)

Want better quality validation or domain detection? Install semantic features:

```bash
pip install cascadeflow[semantic]
```

Then enable in your config:

```python
from cascadeflow import QualityConfig, DomainConfig

agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.balanced(),  # ML-based validation
    enable_domain_routing=True,
    domain_config=DomainConfig.balanced(),    # ML-based detection
)
```

This adds:
- ✅ Semantic similarity validation (10x better quality detection)
- ✅ Toxicity detection (94.87% accuracy)
- ✅ ML-based domain routing (90-95% accuracy vs 70-80% rules)
```

### Feature Comparison Table

```markdown
## Feature Comparison

| Feature | Core | With [semantic] |
|---------|------|-----------------|
| **Cost Optimization** | ✅ 60-85% savings | ✅ Same |
| **User Tiers** | ✅ Full support | ✅ Same |
| **Budget Enforcement** | ✅ Real-time | ✅ Same |
| **Quality Validation** | ✅ Rule-based (3-5ms) | ✅ ML-based (70-130ms) |
| **Quality Detection** | ✅ Good | ✅ 10x better |
| **Domain Detection** | ✅ Rules (70-80%) | ✅ ML (90-95%) |
| **Toxicity Detection** | ❌ | ✅ 94.87% accuracy |
| **Package Size** | 500KB | +500MB |
| **Install Time** | 5s | +60s |

**Recommendation:** Start with core, add `[semantic]` when quality/accuracy becomes priority.
```

---

## Migration Path (v0.1.1 → v0.2.0)

### Zero Changes Required

```python
# v0.1.1 code works EXACTLY the same in v0.2.0
agent = CascadeAgent(models=[...])
result = await agent.run(query="...")

# Behavior:
# ✅ Same rule-based quality validation
# ✅ Same performance (3-5ms overhead)
# ✅ Same cost tracking
# ✅ Zero breaking changes
```

### Adding New Features (Progressive)

```python
# Step 1: Add user tiers (no ML needed)
agent = CascadeAgent(
    models=[...],
    tier_config={...}  # NEW in v0.2.0
)

# Step 2: Add domain routing (rule-based, no ML)
agent = CascadeAgent(
    models=[...],
    tier_config={...},
    enable_domain_routing=True,  # NEW - uses rules by default
)

# Step 3: Upgrade to ML (when ready)
$ pip install --upgrade cascadeflow[semantic]

agent = CascadeAgent(
    models=[...],
    tier_config={...},
    enable_domain_routing=True,
    quality_config=QualityConfig.balanced(),  # Enable ML validation
    domain_config=DomainConfig.balanced(),    # Enable ML detection
)
```

---

## Summary of Changes

### What Changed from Original Plan

**Before (Original Plan):**
- Quality validation: ML enabled by default (with graceful fallback)
- Domain detection: ML enabled by default (with graceful fallback)
- Philosophy: "Secure by default"

**After (Updated):**
- Quality validation: Rule-based by default (EXPLICIT opt-in for ML)
- Domain detection: Rule-based by default (EXPLICIT opt-in for ML)
- Philosophy: "Explicit over implicit"

### Why This is Better

1. **Zero Breaking Changes** - v0.1.1 behavior is default
2. **No Surprises** - Users explicitly choose when to add latency
3. **Clear Expectations** - Know exactly when ML dependencies needed
4. **Production Safe** - No unexpected performance regression
5. **Progressive Enhancement** - Start simple, add complexity when needed

### Configuration Matrix

| Config | Quality | Domain | ML Deps | Overhead | Accuracy |
|--------|---------|--------|---------|----------|----------|
| **Default** | Rules | Disabled | ❌ No | 3-5ms | Good |
| **+ Domain (rules)** | Rules | Rules | ❌ No | <5ms | 70-80% |
| **+ Semantic quality** | ML | Rules | ✅ Yes | 70-130ms | 10x better |
| **+ ML domain** | Rules | ML | ✅ Yes | 10-50ms | 90-95% |
| **Full ML** | ML | ML | ✅ Yes | 80-150ms | Best |

---

## Implementation Checklist

- [ ] Update `QualityConfig` defaults (all ML flags = False)
- [ ] Update `DomainConfig` defaults (all ML flags = False)
- [ ] Update `CascadeAgent.__init__()` defaults
- [ ] Add clear error messages for missing dependencies
- [ ] Update presets (fast, balanced, strict)
- [ ] Update documentation (emphasize opt-in nature)
- [ ] Add migration guide (highlight zero changes)
- [ ] Update tests (test both with/without ML)
- [ ] Update examples (show progressive enhancement)

---

This approach maintains backward compatibility while providing a clear, explicit path to ML features when users need them.
