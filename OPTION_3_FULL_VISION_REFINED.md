# CascadeFlow v0.2.0 - Full Vision Plan (Refined)

**Status:** Ready for Implementation
**Timeline:** 17 weeks
**Approach:** Build on existing telemetry architecture (v2.4)
**Refinements:** Strategic provider support, domain-specific cascading, tier-aware routing, presets 2.0

---

## What's New in This Refined Plan?

### Strategic Additions (Validated ✅)

1. **Strategic Provider Support** - 9 providers (not 100+), each with unique value
2. **Domain-Specific Cascade Pipelines** - Multi-step validation workflows (code, medical, legal)
3. **Tier-Aware Model Routing** - Automatic model selection based on user tier + budget
4. **Presets 2.0** - Full-stack production configs (models + cost + quality + routing)
5. **Clear USP** - Intelligent cost optimization through domain-aware cascading

### Existing Foundation (v0.1.1 - Already Built)

✅ **In `cascadeflow/telemetry/`:**
- CostCalculator (v2.4) - Stateless cost calculation
- CostBreakdown (v2.4) - Structured cost data
- CostTracker - Basic global budget tracking
- CostEntry - Cost entry data structure
- MetricsCollector - Aggregates statistics
- CallbackManager - Event callbacks

---

## Part 1: Enhanced Cost Control (Existing Plan - No Changes)

### 1.1 Per-User Budget Tracking
**Build ON TOP of existing CostTracker**

```python
# cascadeflow/telemetry/cost_tracker.py (ENHANCE)

@dataclass
class BudgetConfig:
    """Per-user budget configuration."""
    daily: Optional[float] = None
    weekly: Optional[float] = None
    monthly: Optional[float] = None
    total: Optional[float] = None

class CostTracker:  # ENHANCE existing class
    def __init__(
        self,
        budget_limit: Optional[float] = None,  # Global (existing)
        user_budgets: Optional[Dict[str, BudgetConfig]] = None,  # NEW
        warn_threshold: float = 0.8,
        verbose: bool = False,
    ):
        # Existing tracking
        self.budget_limit = budget_limit
        self.total_cost = 0.0
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_provider: dict[str, float] = defaultdict(float)

        # NEW: Per-user tracking
        self.user_budgets = user_budgets or {}
        self.by_user: dict[str, float] = defaultdict(float)  # NEW
        self.user_entries: dict[str, list[CostEntry]] = defaultdict(list)  # NEW

    def add_cost(
        self,
        model: str,
        provider: str,
        tokens: int,
        cost: float,
        query_id: Optional[str] = None,
        user_id: Optional[str] = None,  # NEW parameter
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add cost entry (ENHANCED with user_id)."""
        # Existing logic + NEW per-user tracking
        if user_id:
            self.by_user[user_id] += cost
            self.user_entries[user_id].append(entry)
            self._check_user_budget(user_id)

    def get_user_summary(self, user_id: str) -> dict:
        """NEW: Get per-user cost summary."""
        return {
            "user_id": user_id,
            "total_cost": self.by_user[user_id],
            "entries": len(self.user_entries[user_id]),
            "budget": self.user_budgets.get(user_id),
        }
```

### 1.2 Enforcement Callbacks
**NEW module: `cascadeflow/telemetry/enforcement.py`**

```python
@dataclass
class EnforcementContext:
    """Context passed to enforcement callbacks."""
    user_id: str
    budget_limit: float
    budget_remaining: float
    budget_used: float
    budget_pct_used: float
    current_cost: float
    total_requests: int

class EnforcementCallbacks:
    """Flexible enforcement via callbacks."""

    def __init__(
        self,
        on_budget_check: Optional[Callable[[EnforcementContext], Tuple[str, str]]] = None,
        on_model_filter: Optional[Callable[[EnforcementContext, list], list]] = None,
        on_budget_warning: Optional[Callable[[EnforcementContext], None]] = None,
    ):
        self.on_budget_check = on_budget_check
        self.on_model_filter = on_model_filter
        self.on_budget_warning = on_budget_warning

    def check_budget(self, ctx: EnforcementContext) -> Tuple[str, Optional[str]]:
        """
        Check if request should proceed.

        Returns:
            (action, message) where action is 'allow', 'warn', 'block', or 'degrade'
        """
        if self.on_budget_check:
            return self.on_budget_check(ctx)

        # Default enforcement logic
        if ctx.budget_remaining <= 0:
            return 'block', "Budget exceeded"
        elif ctx.budget_pct_used >= 0.9:
            return 'warn', f"Budget {ctx.budget_pct_used:.0%} used"
        else:
            return 'allow', None
```

### 1.3 Intelligent Enforcement (Graceful Degradation)
### 1.4 Cost Forecasting (`cascadeflow/telemetry/forecasting.py`)
### 1.5 Anomaly Detection (`cascadeflow/telemetry/anomaly.py`)
### 1.6 Local Storage & Export (JSON, CSV, SQLite)

*(No changes from original plan - see OPTION_3_FULL_VISION.md for details)*

---

## Part 2: Integration Layer (REFINED)

### 2.1 LiteLLM Integration (FREE Library ONLY)

**IMPORTANT:** We use ONLY the free LiteLLM library, NOT the proxy.

**What We Use (FREE):**
- ✅ Provider abstraction (unified API)
- ✅ Pricing database (cost per 1K tokens)
- ✅ Cost calculation helpers (`completion_cost()`)

**What We DON'T Use (PROXY):**
- ❌ Rate limiting (we build our own)
- ❌ Guardrails (we build our own)
- ❌ Any proxy features (proxy costs $30K/year)

```python
# cascadeflow/integrations/litellm.py (NEW FILE)

try:
    import litellm  # FREE library (Apache 2.0)
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

# ==================== SUPPORTED PROVIDERS ====================
# Strategic selection: 9 providers with unique value

SUPPORTED_PROVIDERS = {
    # Core 4 (Essential - 95% of use cases)
    'openai': {
        'value': 'Industry standard, most reliable, GPT-4o',
        'cost_range': '$0.0015-0.025/1K tokens',
        'speed': 'Fast (2-4s)',
        'use_case': 'Essential verifier'
    },
    'anthropic': {
        'value': 'Claude Sonnet 4.5, best reasoning',
        'cost_range': '$0.003-0.015/1K tokens',
        'speed': 'Fast (2-3s)',
        'use_case': 'Essential verifier'
    },
    'groq': {
        'value': 'Ultra-fast inference (10x faster)',
        'cost_range': 'Free tier, $0.0-0.001/1K tokens',
        'speed': 'Ultra-fast (0.5-1s)',
        'use_case': 'Perfect drafter'
    },
    'ollama': {
        'value': 'Local, free, private, offline',
        'cost_range': '$0 (local)',
        'speed': 'Moderate (2-5s)',
        'use_case': 'Free tier drafter'
    },

    # Specialized 5 (Domain-specific - 20% of use cases)
    'fireworks_ai': {
        'value': 'Fast inference for open models (Llama, Mistral)',
        'cost_range': '$0.0002-0.0009/1K tokens',
        'speed': 'Fast (1-2s)',
        'use_case': 'Cost-conscious production'
    },
    'together_ai': {
        'value': 'Reliable open models, alternative to Groq',
        'cost_range': '$0.0002-0.0008/1K tokens',
        'speed': 'Fast (1-3s)',
        'use_case': 'Open model production'
    },
    'deepseek': {
        'value': 'Cheapest coding model (Deepseek-Coder)',
        'cost_range': '$0.0014/1K tokens',
        'speed': 'Fast (2-3s)',
        'use_case': 'Code domain drafting (10x cheaper than GPT-4)'
    },
    'vertex_ai': {
        'value': 'Gemini models, enterprise scale, GCP integration',
        'cost_range': '$0.00125-0.0075/1K tokens',
        'speed': 'Fast (2-4s)',
        'use_case': 'Enterprise customers on GCP'
    },
    'cohere': {
        'value': 'Command models, specialized embeddings for RAG',
        'cost_range': '$0.0001-0.002/1K tokens',
        'speed': 'Fast (1-3s)',
        'use_case': 'Search/RAG applications'
    },
}

class LiteLLMCostProvider:
    """
    Cost calculation using LiteLLM's FREE pricing database.

    NOTE: This uses ONLY the free library, NOT the proxy.
    """

    def __init__(self):
        if not LITELLM_AVAILABLE:
            raise ImportError("Install litellm: pip install litellm")

    def validate_provider(self, provider: str) -> None:
        """Validate provider is supported and has unique value."""
        if provider not in SUPPORTED_PROVIDERS:
            supported_list = ', '.join(SUPPORTED_PROVIDERS.keys())
            raise ValueError(
                f"Provider '{provider}' not supported. "
                f"CascadeFlow supports 9 strategic providers (not 100+): {supported_list}\n\n"
                f"Why only 9? Each provider adds unique value:\n"
                f"• Core 4 (openai, anthropic, groq, ollama) - Cover 95% of use cases\n"
                f"• Specialized 5 (fireworks, together, deepseek, vertex, cohere) - Domain-specific value\n\n"
                f"See docs/providers.md for details on each provider's unique value."
            )

    def get_model_cost(self, model: str, provider: str) -> float:
        """Get cost per 1K tokens from LiteLLM's FREE pricing database."""
        self.validate_provider(provider)

        try:
            # Use LiteLLM's FREE library to get pricing
            return litellm.get_model_cost_map(model)
        except Exception:
            logger.warning(f"Model '{model}' not in LiteLLM pricing database")
            return 0.0  # Fallback

    def calculate_cost(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost using LiteLLM's FREE library."""
        self.validate_provider(provider)

        # Use LiteLLM's FREE cost calculation
        return litellm.completion_cost(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens
        )

    def get_provider_info(self, provider: str) -> dict:
        """Get provider value proposition."""
        self.validate_provider(provider)
        return SUPPORTED_PROVIDERS[provider]
```

**Why Only 9 Providers?**
- ✅ Each has clear unique value (not noise)
- ✅ 95% coverage of developer use cases
- ✅ Manageable testing surface (9 vs 100+)
- ✅ Clear documentation (why use each?)
- ✅ Focused maintenance

### 2.2 OpenTelemetry Integration (FREE, Vendor-Neutral)

```python
# cascadeflow/integrations/otel.py (NEW FILE)

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

class OpenTelemetryExporter:
    """
    Export cost metrics to OpenTelemetry (FREE, vendor-neutral).

    Works with ANY observability platform:
    - Grafana (open-source)
    - Datadog
    - Prometheus
    - CloudWatch
    - New Relic
    - Splunk
    """

    def __init__(self, endpoint: str = "http://localhost:4318"):
        if not OTEL_AVAILABLE:
            raise ImportError(
                "Install opentelemetry: pip install opentelemetry-api opentelemetry-sdk"
            )

        self.endpoint = endpoint
        self.meter = metrics.get_meter(__name__)

        # Create metrics
        self.cost_counter = self.meter.create_counter(
            "cascadeflow.cost.total",
            description="Total cost in USD"
        )

        self.token_counter = self.meter.create_counter(
            "cascadeflow.tokens.total",
            description="Total tokens used"
        )

    def export_cost(
        self,
        cost: float,
        user_id: str,
        model: str,
        provider: str
    ):
        """Export cost to OpenTelemetry."""
        self.cost_counter.add(
            cost,
            attributes={
                "user_id": user_id,
                "model": model,
                "provider": provider
            }
        )
```

---

## Part 3: Quality System (No Changes)

### 3.1 Rule-Based Quality (Default)
### 3.2 Optional ML Quality (Opt-In)
### 3.3 Quality Presets

*(No changes from original plan - see OPTION_3_FULL_VISION.md for details)*

---

## Part 4: Domain-Specific Cascading (NEW - STRATEGIC ADDITION)

### Problem Statement
**Current:** All domains treated equally (2-step: draft → verify)
**Issue:** Different domains need different strategies

**Examples:**
- Code: Needs syntax validation, not just quality check
- Medical: Needs fact-checking + citation validation + safety checks (3+ steps)
- Legal: Needs citation validation + compliance checks
- General: Standard 2-step is sufficient

### Solution: Domain-Specific Multi-Step Cascade Pipelines

```python
# cascadeflow/routing/domain_cascade.py (NEW FILE)

from typing import List, Optional, Callable
from dataclasses import dataclass

@dataclass
class CascadeStep:
    """Single step in cascade pipeline."""
    model: str
    provider: str
    validation: Optional[Callable] = None  # Custom validation function
    max_retries: int = 1
    fallback_model: Optional[str] = None
    description: str = ""

@dataclass
class DomainCascadeStrategy:
    """Multi-step cascade strategy for a specific domain."""
    domain: str
    steps: List[CascadeStep]
    description: str
    expected_cost_range: str  # e.g., "$0.001-0.005"
    expected_steps: int  # e.g., 2-3 steps typically

# ==================== BUILT-IN STRATEGIES ====================

CODE_DOMAIN_STRATEGY = DomainCascadeStrategy(
    domain='code',
    description="Fast code generation with syntax validation",
    expected_cost_range="$0.0014-0.03 (90% use cheap model)",
    expected_steps=2,
    steps=[
        # Step 1: Fast, cheap code model
        CascadeStep(
            model='deepseek-coder',
            provider='deepseek',
            validation=syntax_validator,  # Check if code is syntactically valid
            fallback_model='gpt-3.5-turbo',
            description="Draft with specialized code model (10x cheaper than GPT-4)"
        ),
        # Step 2: Quality verification (only if syntax invalid or quality low)
        CascadeStep(
            model='gpt-4',
            provider='openai',
            validation=code_quality_validator,  # Check code quality, logic
            fallback_model='claude-sonnet-4',
            description="Verify code quality with premium model (only if needed)"
        )
    ]
)

MEDICAL_DOMAIN_STRATEGY = DomainCascadeStrategy(
    domain='medical',
    description="Medical responses with fact-checking and safety validation",
    expected_cost_range="$0.04-0.07 (3 steps for safety)",
    expected_steps=3,
    steps=[
        # Step 1: General medical draft
        CascadeStep(
            model='gpt-3.5-turbo',
            provider='openai',
            validation=medical_fact_checker,  # Check medical facts
            fallback_model='claude-haiku',
            description="Draft medical response with general model"
        ),
        # Step 2: Specialized medical verification
        CascadeStep(
            model='med-palm-2',
            provider='vertex_ai',
            validation=citation_validator,  # Check citations
            fallback_model='gpt-4',
            description="Verify with specialized medical model"
        ),
        # Step 3: Final safety check
        CascadeStep(
            model='claude-opus',
            provider='anthropic',
            validation=medical_safety_checker,  # Safety validation
            max_retries=2,
            description="Safety validation (critical for medical)"
        )
    ]
)

GENERAL_DOMAIN_STRATEGY = DomainCascadeStrategy(
    domain='general',
    description="General queries with cost optimization",
    expected_cost_range="$0.0007-0.003 (95% use cheap model)",
    expected_steps=2,
    steps=[
        # Step 1: Fast, cheap draft
        CascadeStep(
            model='llama-3.3-70b-versatile',
            provider='groq',
            validation=quality_validator,  # Standard quality check
            fallback_model='gpt-3.5-turbo',
            description="Ultra-fast draft with Groq (10x faster, free)"
        ),
        # Step 2: Quality verification (only if needed)
        CascadeStep(
            model='gpt-4o',
            provider='openai',
            validation=confidence_validator,  # High confidence required
            fallback_model='claude-sonnet-4',
            description="Verify with premium model if draft quality low"
        )
    ]
)
```

### Integration with `CascadeAgent`

```python
# cascadeflow/core/agent.py (ENHANCED)

class CascadeAgent:
    def __init__(
        self,
        models: List[ModelConfig],
        domain_strategies: Optional[Dict[str, DomainCascadeStrategy]] = None,  # NEW
        enable_multi_step_cascade: bool = False,  # NEW
        # ... existing parameters
    ):
        self.models = models
        self.domain_strategies = domain_strategies or {
            'code': CODE_DOMAIN_STRATEGY,
            'medical': MEDICAL_DOMAIN_STRATEGY,
            'general': GENERAL_DOMAIN_STRATEGY,
        }
        self.enable_multi_step_cascade = enable_multi_step_cascade

    async def run(
        self,
        query: str,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        # ... existing parameters
    ):
        """Run query with domain-specific multi-step cascade."""

        # Detect domain if not specified
        if not domain and self.domain_detector:
            domain, confidence = self.domain_detector.detect(query)

        # Use multi-step cascade if enabled and strategy available
        if self.enable_multi_step_cascade and domain in self.domain_strategies:
            return await self._run_multi_step_cascade(
                query=query,
                strategy=self.domain_strategies[domain],
                user_id=user_id
            )

        # Fall back to standard 2-step cascade
        return await self._run_standard_cascade(query, user_id)

    async def _run_multi_step_cascade(
        self,
        query: str,
        strategy: DomainCascadeStrategy,
        user_id: Optional[str] = None
    ):
        """Execute multi-step domain-specific cascade."""

        result = None
        total_cost = 0.0

        for step_idx, step in enumerate(strategy.steps):
            logger.info(f"Step {step_idx + 1}/{len(strategy.steps)}: {step.description}")

            # Call model
            response = await self._call_model(
                model=step.model,
                provider=step.provider,
                query=query,
                context=result  # Pass previous result as context
            )

            total_cost += response.cost

            # Validate response
            if step.validation:
                is_valid, reason = step.validation(response.text)

                if not is_valid:
                    logger.warning(f"Validation failed: {reason}")

                    # Try fallback model
                    if step.fallback_model:
                        logger.info(f"Trying fallback: {step.fallback_model}")
                        response = await self._call_model(
                            model=step.fallback_model,
                            query=query,
                            context=result
                        )
                        total_cost += response.cost

                    # If still invalid and not last step, continue to next step
                    if not step.validation(response.text)[0] and step_idx < len(strategy.steps) - 1:
                        continue

            # Update result
            result = response

        return CascadeResult(
            text=result.text,
            model_used=result.model,
            total_cost=total_cost,
            steps_executed=len(strategy.steps),
            strategy_used=strategy.domain
        )
```

### Usage Example

```python
from cascadeflow import CascadeAgent
from cascadeflow.routing import CODE_DOMAIN_STRATEGY, MEDICAL_DOMAIN_STRATEGY

# Enable domain-specific multi-step cascading
agent = CascadeAgent(
    models=all_models,
    enable_multi_step_cascade=True,
    domain_strategies={
        'code': CODE_DOMAIN_STRATEGY,
        'medical': MEDICAL_DOMAIN_STRATEGY,
    }
)

# Code query → 2-step code strategy
result = await agent.run("Write quicksort in Python", domain='code')
# Step 1: deepseek-coder ($0.0014) → syntax check → ✅ valid
# Step 2: Skipped (syntax valid, quality good)
# Total cost: $0.0014 (95% cheaper than GPT-4 $0.03)

# Medical query → 3-step medical strategy
result = await agent.run("What are symptoms of diabetes?", domain='medical')
# Step 1: gpt-3.5 ($0.002) → fact check → ✅ facts correct
# Step 2: med-palm-2 ($0.025) → citation validation → ✅ citations valid
# Step 3: claude-opus ($0.015) → safety check → ✅ safe
# Total cost: $0.042 (3 steps for safety)
```

**Benefits:**
- ✅ Domain-optimized workflows (2-5 steps)
- ✅ Custom validation per step (syntax, facts, safety)
- ✅ Automatic fallback handling
- ✅ Cost savings (use cheap models first, escalate only if needed)
- ✅ Quality improvements (domain-specific verification)

---

## Part 5: Tier-Aware Model Routing (NEW - STRATEGIC ADDITION)

### Problem Statement
**Current:** No automatic model selection based on user tier
**Issue:** Developers write boilerplate for tier → model mapping

**Example (v0.1.1 - Manual):**
```python
# Developer must manually handle tier logic (BAD DX)
if user.tier == 'free':
    models = [cheap_model]
elif user.tier == 'pro':
    models = [good_model, better_model]
else:
    models = [good_model, best_model, premium_model]

agent = CascadeAgent(models=models)
```

### Solution: Automatic Tier → Model Routing

```python
# cascadeflow/routing/tier_routing.py (NEW FILE)

from typing import List, Dict, Optional
from dataclasses import dataclass
from cascadeflow.schema import ModelConfig

@dataclass
class TierModelPolicy:
    """Define which models a tier can use."""
    tier_name: str
    allowed_models: List[str]  # Model names allowed for this tier
    max_cost_per_query: Optional[float] = None  # Max cost per query
    prefer_cheap_first: bool = True  # Always try cheap models first
    description: str = ""

class TierAwareRouter:
    """Route queries to appropriate models based on user tier."""

    def __init__(
        self,
        tier_policies: Dict[str, TierModelPolicy],
        all_models: List[ModelConfig]
    ):
        self.tier_policies = tier_policies
        self.all_models = {m.name: m for m in all_models}

    def get_models_for_tier(
        self,
        tier: str,
        budget_remaining: float,
        complexity: str = 'medium'
    ) -> List[ModelConfig]:
        """
        Get appropriate models for user tier and budget.

        Args:
            tier: User tier ('free', 'pro', 'enterprise')
            budget_remaining: Remaining budget for user
            complexity: Query complexity ('simple', 'medium', 'high')

        Returns:
            List of models user can use, sorted by cost (cheap first)
        """

        if tier not in self.tier_policies:
            raise ValueError(f"Unknown tier: {tier}")

        policy = self.tier_policies[tier]

        # Filter models allowed for tier
        available = [
            self.all_models[name]
            for name in policy.allowed_models
            if name in self.all_models
        ]

        # Filter by remaining budget
        if budget_remaining > 0:
            # Estimate max tokens (conservative: 500 output tokens)
            max_cost_estimate = budget_remaining / 500

            available = [
                m for m in available
                if m.cost <= max_cost_estimate
            ]

        # Filter by max cost per query (if policy specifies)
        if policy.max_cost_per_query:
            available = [
                m for m in available
                if m.cost <= policy.max_cost_per_query
            ]

        # Sort by cost (cheap first if policy says so)
        if policy.prefer_cheap_first:
            available.sort(key=lambda m: m.cost)
        else:
            available.sort(key=lambda m: m.cost, reverse=True)

        # Smart selection based on complexity
        if complexity == 'simple':
            # For simple queries, return only cheapest 2 models
            return available[:2]
        elif complexity == 'high':
            # For complex queries, include premium models if tier allows
            return available  # All available models
        else:
            # Medium complexity: 2-3 models
            return available[:3]

# ==================== BUILT-IN TIER POLICIES ====================

TIER_POLICIES_DEFAULT = {
    'free': TierModelPolicy(
        tier_name='free',
        allowed_models=[
            'llama-3.1-8b-instant',      # Groq free
            'llama-3.3-70b-versatile',   # Groq free
            'gpt-4o-mini',                # Backup (cheap)
        ],
        max_cost_per_query=0.001,  # $0.001 max per query
        prefer_cheap_first=True,
        description="Free tier - Ultra-cheap models only ($0.001 max per query)"
    ),

    'pro': TierModelPolicy(
        tier_name='pro',
        allowed_models=[
            'llama-3.3-70b-versatile',   # Groq
            'claude-3-5-haiku',           # Anthropic
            'gpt-4o-mini',                # OpenAI
            'gpt-4o',                     # OpenAI premium (if needed)
        ],
        max_cost_per_query=0.005,  # $0.005 max per query
        prefer_cheap_first=True,
        description="Pro tier - Quality models with smart escalation ($0.005 max)"
    ),

    'enterprise': TierModelPolicy(
        tier_name='enterprise',
        allowed_models=[
            'llama-3.3-70b-versatile',
            'claude-3-5-haiku',
            'gpt-4o-mini',
            'gpt-4o',
            'claude-sonnet-4',  # Premium
        ],
        max_cost_per_query=0.01,  # $0.01 max per query
        prefer_cheap_first=True,  # Still optimize cost
        description="Enterprise tier - Full model access with cost optimization"
    ),
}
```

### Integration with `CascadeAgent`

```python
# cascadeflow/core/agent.py (ENHANCED)

class CascadeAgent:
    def __init__(
        self,
        models: List[ModelConfig],
        tier_router: Optional[TierAwareRouter] = None,  # NEW
        enable_tier_routing: bool = False,  # NEW
        # ... existing parameters
    ):
        self.models = models
        self.tier_router = tier_router
        self.enable_tier_routing = enable_tier_routing

    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        user_tier: Optional[str] = None,  # NEW
        # ... existing parameters
    ):
        """Run query with tier-aware model routing."""

        # Tier-aware routing
        if self.enable_tier_routing and user_tier and self.tier_router:
            # Get remaining budget for user
            budget_remaining = self._get_budget_remaining(user_id)

            # Detect complexity (optional)
            complexity = 'medium'
            if self.complexity_analyzer:
                complexity = self.complexity_analyzer.analyze(query)['complexity']

            # Get models appropriate for tier + budget + complexity
            available_models = self.tier_router.get_models_for_tier(
                tier=user_tier,
                budget_remaining=budget_remaining,
                complexity=complexity
            )

            logger.info(
                f"Tier routing: {user_tier} → {len(available_models)} models "
                f"(budget: ${budget_remaining:.2f}, complexity: {complexity})"
            )

            # Use tier-filtered models
            self.models = available_models

        # Continue with standard cascade logic
        return await self._run_cascade(query, user_id)
```

### Usage Example

```python
from cascadeflow import CascadeAgent
from cascadeflow.routing import TierAwareRouter, TIER_POLICIES_DEFAULT

# Setup tier-aware agent
agent = CascadeAgent(
    models=all_models,
    tier_router=TierAwareRouter(
        tier_policies=TIER_POLICIES_DEFAULT,
        all_models=all_models
    ),
    enable_tier_routing=True,
    cost_tracker=CostTracker(
        user_budgets={
            'user_free': BudgetConfig(daily=0.10),
            'user_pro': BudgetConfig(daily=1.00),
            'user_ent': BudgetConfig(daily=10.00),
        }
    )
)

# Free user - simple query
result = await agent.run("What is 2+2?", user_id='user_free', user_tier='free')
# Tier routing: free → 2 models (llama-8b, llama-70b)
# Uses: llama-8b ($0.00005) ✅ accepted
# Total: $0.00005

# Free user - complex query (within budget)
result = await agent.run("Explain quantum physics", user_id='user_free', user_tier='free')
# Tier routing: free → 3 models (llama-8b, llama-70b, gpt-4o-mini)
# Uses: llama-70b ($0.0007) → quality low → gpt-4o-mini ($0.00015) ✅ accepted
# Total: $0.00085 (within $0.001 max)

# Pro user - complex query
result = await agent.run("Design microservices architecture", user_id='user_pro', user_tier='pro')
# Tier routing: pro → 4 models (llama-70b, haiku, 4o-mini, 4o)
# Uses: haiku ($0.0008) → quality low → gpt-4o ($0.0025) ✅ accepted
# Total: $0.0033 (within $0.005 max)
```

**Benefits:**
- ✅ Zero boilerplate (no manual tier logic)
- ✅ Smart escalation within budget (free users CAN get premium if draft fails AND budget allows)
- ✅ Complexity-aware (simple queries use cheap models even for enterprise)
- ✅ Integrates with budget enforcement

---

## Part 6: Presets 2.0 - Complete Production Configs (NEW - STRATEGIC ADDITION)

### Problem Statement
**Current (v0.1.1):** Presets only configure models
```python
PRESET_BEST_OVERALL = [
    ModelConfig(name='claude-3-5-haiku', ...),
    ModelConfig(name='gpt-4o-mini', ...),
]
```

**Issues:**
- ❌ Only models (no cost tracking, quality, routing)
- ❌ Developers still need 10-20 lines for production setup
- ❌ No guidance on which preset for which use case

### Solution: Full-Stack Production Presets

```python
# cascadeflow/utils/presets_v2.py (NEW FILE)

from dataclasses import dataclass
from typing import List, Optional, Dict
from cascadeflow.schema import ModelConfig
from cascadeflow.telemetry import CostTracker, BudgetConfig
from cascadeflow.quality import QualityValidator
from cascadeflow.routing import DomainDetector, DomainCascadeStrategy, TierAwareRouter

@dataclass
class CascadePreset:
    """
    Complete CascadeFlow configuration preset.

    Includes:
    - Models (draft + verifier + domain-specific)
    - Cost tracking + budget limits
    - Quality validation configuration
    - Domain routing configuration
    - User-tier enforcement (optional)
    - Multi-step cascading strategies (optional)
    """

    name: str
    description: str

    # Models
    models: List[ModelConfig]

    # Cost Control
    enable_cost_tracking: bool = True
    default_budget_daily: Optional[float] = None
    enable_cost_forecasting: bool = False

    # Quality
    quality_validation_mode: str = 'fast'  # 'fast', 'balanced', 'strict'
    enable_ml_quality: bool = False

    # Domain Routing
    enable_domain_routing: bool = False
    domain_strategies: Optional[Dict[str, DomainCascadeStrategy]] = None

    # User Tiers (Optional)
    enable_user_tiers: bool = False
    tier_budgets: Optional[Dict[str, BudgetConfig]] = None

    # Multi-Step Cascading (Optional)
    enable_multi_step_cascade: bool = False

    def to_agent_config(self) -> dict:
        """Convert preset to CascadeAgent initialization parameters."""
        # Implementation...
```

### Built-In Presets 2.0

```python
# ==================== PRESET 2.0: PRODUCTION READY ====================
PRESET_PRODUCTION_READY = CascadePreset(
    name='production_ready',
    description='Complete production setup with cost tracking and quality validation',
    models=[
        ModelConfig(name='claude-3-5-haiku', provider='anthropic', cost=0.0008, quality_score=0.85),
        ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015, quality_score=0.80),
        ModelConfig(name='gpt-4o', provider='openai', cost=0.0025, quality_score=0.95),
    ],
    enable_cost_tracking=True,
    default_budget_daily=10.00,
    quality_validation_mode='balanced',
)

# ==================== PRESET 2.0: COST OPTIMIZED SAAS ====================
PRESET_COST_OPTIMIZED_SAAS = CascadePreset(
    name='cost_optimized_saas',
    description='Maximum cost savings for high-volume SaaS',
    models=[
        ModelConfig(name='llama-3.1-8b-instant', provider='groq', cost=0.00005),
        ModelConfig(name='llama-3.3-70b-versatile', provider='groq', cost=0.00069),
        ModelConfig(name='gpt-4o-mini', provider='openai', cost=0.00015),
    ],
    enable_cost_tracking=True,
    default_budget_daily=1.00,
    enable_cost_forecasting=True,
    quality_validation_mode='cost-optimized',
    enable_user_tiers=True,
    tier_budgets={
        'free': BudgetConfig(daily=0.10),
        'pro': BudgetConfig(daily=1.00),
        'enterprise': BudgetConfig(daily=10.00),
    }
)

# ==================== PRESET 2.0: CODE SPECIALIST ====================
PRESET_CODE_SPECIALIST = CascadePreset(
    name='code_specialist',
    description='Optimized for code generation with multi-step validation',
    models=[
        ModelConfig(name='deepseek-coder', provider='deepseek', cost=0.0014, domains=['code']),
        ModelConfig(name='codellama-70b', provider='fireworks', cost=0.0008, domains=['code']),
        ModelConfig(name='gpt-4', provider='openai', cost=0.03, domains=['expert']),
    ],
    enable_cost_tracking=True,
    default_budget_daily=5.00,
    quality_validation_mode='strict',
    enable_domain_routing=True,
    domain_strategies={'code': CODE_DOMAIN_STRATEGY},
    enable_multi_step_cascade=True,
)

# ==================== PRESET 2.0: MEDICAL AI ====================
PRESET_MEDICAL_AI = CascadePreset(
    name='medical_ai',
    description='Medical responses with fact-checking and safety validation',
    models=[
        ModelConfig(name='gpt-3.5-turbo', provider='openai', cost=0.002),
        ModelConfig(name='med-palm-2', provider='vertex_ai', cost=0.025, domains=['medical']),
        ModelConfig(name='claude-opus', provider='anthropic', cost=0.015),
    ],
    enable_cost_tracking=True,
    default_budget_daily=50.00,
    quality_validation_mode='strict',
    enable_ml_quality=True,
    enable_domain_routing=True,
    domain_strategies={'medical': MEDICAL_DOMAIN_STRATEGY},
    enable_multi_step_cascade=True,
)

# ==================== PRESET 2.0: ENTERPRISE GRADE ====================
PRESET_ENTERPRISE_GRADE = CascadePreset(
    name='enterprise_grade',
    description='Complete enterprise setup with all features',
    models=[
        # Full range (free → premium)
        ModelConfig(name='llama-3.3-70b-versatile', provider='groq', cost=0.00069),
        ModelConfig(name='claude-3-5-haiku', provider='anthropic', cost=0.0008),
        ModelConfig(name='deepseek-coder', provider='deepseek', cost=0.0014, domains=['code']),
        ModelConfig(name='gpt-4o', provider='openai', cost=0.0025),
        ModelConfig(name='claude-sonnet-4', provider='anthropic', cost=0.009),
    ],
    enable_cost_tracking=True,
    default_budget_daily=100.00,
    enable_cost_forecasting=True,
    quality_validation_mode='balanced',
    enable_domain_routing=True,
    domain_strategies={
        'code': CODE_DOMAIN_STRATEGY,
        'general': GENERAL_DOMAIN_STRATEGY,
    },
    enable_user_tiers=True,
    tier_budgets={
        'free': BudgetConfig(daily=1.00),
        'starter': BudgetConfig(daily=5.00),
        'pro': BudgetConfig(daily=20.00),
        'enterprise': BudgetConfig(daily=100.00),
    },
)
```

### Usage: Zero-Config Production

```python
# ==================== BEFORE (v0.1.1) - 20+ lines ====================
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.telemetry import CostTracker, BudgetConfig
from cascadeflow.quality import QualityValidator

agent = CascadeAgent(
    models=[
        ModelConfig(...), ModelConfig(...), ModelConfig(...)
    ],
    cost_tracker=CostTracker(...),
    quality_validator=QualityValidator(...)
)

# ==================== AFTER (v0.2.0) - 2 lines ====================
from cascadeflow import CascadeAgent, PRESET_PRODUCTION_READY

agent = CascadeAgent(**PRESET_PRODUCTION_READY.to_agent_config())
# ✅ Full production setup: models + cost + quality + routing
```

---

## Implementation Roadmap (17 Weeks - REFINED)

### Phase 1: Enhanced Cost Control (Weeks 1-4) ✅ NO CHANGES

### Phase 2: Integration Layer (Weeks 5-6) - REFINED
**Week 5: LiteLLM Integration (FREE Library Only)**
- [ ] Create `cascadeflow/integrations/litellm.py`
- [ ] `SUPPORTED_PROVIDERS` dict (9 strategic providers)
- [ ] `LiteLLMCostProvider` class (FREE library only)
- [ ] Provider validation (reject unsupported providers)
- [ ] Documentation: Why each provider? (unique value)
- [ ] Tests

**Week 6: OpenTelemetry Integration**
- [ ] Create `cascadeflow/integrations/otel.py`
- [ ] `OpenTelemetryExporter` class
- [ ] Cost + token metrics export
- [ ] Integration examples (Grafana, Datadog, CloudWatch)
- [ ] Tests

### Phase 3: Intelligence Layer (Weeks 7-9) ✅ NO CHANGES

### Phase 4: Quality System (Weeks 10-12) ✅ NO CHANGES

### Phase 5: Domain Routing + Tier Routing (Weeks 13-15) - REFINED
**Week 13: Rule-Based Domain Detection**
- [ ] Create `cascadeflow/routing/domain.py`
- [ ] `DomainDetector` class
- [ ] Rule-based detection (keywords)
- [ ] Tests

**Week 14: Domain-Specific Cascade Pipelines (NEW)**
- [ ] Create `cascadeflow/routing/domain_cascade.py`
- [ ] `CascadeStep` dataclass
- [ ] `DomainCascadeStrategy` dataclass
- [ ] Built-in strategies: CODE, MEDICAL, GENERAL
- [ ] Multi-step cascade execution logic
- [ ] Step-level validation + fallback
- [ ] Tests

**Week 15: Tier-Aware Routing (NEW)**
- [ ] Create `cascadeflow/routing/tier_routing.py`
- [ ] `TierModelPolicy` dataclass
- [ ] `TierAwareRouter` class
- [ ] Built-in tier policies (free, pro, enterprise)
- [ ] Budget-aware model filtering
- [ ] Complexity-aware selection
- [ ] Tests

### Phase 6: Presets 2.0 + Testing (Weeks 16-17) - REFINED
**Week 16: Presets 2.0 (NEW)**
- [ ] Create `cascadeflow/utils/presets_v2.py`
- [ ] `CascadePreset` class (full-stack configs)
- [ ] Built-in presets:
  - `PRESET_PRODUCTION_READY`
  - `PRESET_COST_OPTIMIZED_SAAS`
  - `PRESET_CODE_SPECIALIST`
  - `PRESET_MEDICAL_AI`
  - `PRESET_ENTERPRISE_GRADE`
- [ ] `to_agent_config()` converter
- [ ] Tests

**Week 17: Integration Testing + Docs**
- [ ] End-to-end preset testing
- [ ] Domain-specific cascade testing
- [ ] Tier routing testing
- [ ] Performance benchmarking
- [ ] Complete API documentation
- [ ] Migration guide (v0.1.1 → v0.2.0)
- [ ] Cookbook with examples
- [ ] Release prep

---

## File Structure (REFINED)

```
cascadeflow/
├── telemetry/
│   ├── __init__.py (existing - enhance)
│   ├── cost_calculator.py (existing - keep as-is)
│   ├── cost_tracker.py (existing - ENHANCE)
│   ├── enforcement.py (NEW)
│   ├── forecasting.py (NEW)
│   └── anomaly.py (NEW)
├── quality/
│   ├── __init__.py (existing)
│   ├── validation.py (existing - ENHANCE)
│   ├── semantic.py (NEW - opt-in)
│   └── presets.py (NEW)
├── routing/
│   ├── __init__.py (NEW)
│   ├── domain.py (NEW - domain detection)
│   ├── domain_cascade.py (NEW - multi-step strategies)
│   ├── tier_routing.py (NEW - tier-aware routing)
│   ├── complexity.py (NEW - code complexity)
│   └── semantic_router.py (NEW - opt-in)
├── integrations/
│   ├── __init__.py (NEW)
│   ├── litellm.py (NEW - FREE library only, 9 providers)
│   └── otel.py (NEW - OpenTelemetry)
├── utils/
│   ├── presets.py (existing - v0.1.1 presets)
│   └── presets_v2.py (NEW - full-stack presets)
└── core/
    └── agent.py (existing - ENHANCE)
```

---

## Dependencies (REFINED)

### Core (Required) - No New Dependencies ✅
```python
# Builds on existing: httpx, pydantic, etc.
```

### Optional (Opt-In) ✅
```bash
# Semantic quality features
pip install cascadeflow[semantic]
# Adds: fastembed>=0.2.0 (80MB), transformers>=4.30.0

# Integration features
pip install cascadeflow[integrations]
# Adds: litellm>=1.0.0 (FREE library), opentelemetry-api>=1.20.0, opentelemetry-sdk>=1.20.0

# Domain routing features
pip install cascadeflow[routing]
# Adds: semantic-router>=0.0.20

# Everything
pip install cascadeflow[all]
```

---

## Success Metrics (3 Months Post-Launch)

### Technical ✅
- All 4 feature areas + 3 strategic additions implemented
- 100% backward compatibility with v0.1.1
- Support 9 strategic providers (each with unique value)
- <200ms overhead (rule-based mode)
- <10% forecasting error
- >90% domain detection accuracy

### Adoption ✅
- 60% use Presets 2.0 (vs 30% manual config)
- 50% adopt per-user tracking
- 40% enable domain routing
- 30% use tier-aware routing
- 25% enable multi-step cascading
- >4.5/5 developer satisfaction

### Business ✅
- 83-90% average cost savings (vs direct GPT-4)
- 95% cost savings for code domain (deepseek vs GPT-4)
- Zero budget bypass incidents
- >50 production deployments in 3 months
- 90% reduction in config code (presets 2.0)

---

## Our Unique Value Proposition (Validated)

### CascadeFlow = Intelligent Cost Optimization Through Domain-Aware Cascading

**What makes us irreplaceable:**

1. **Draft-Verify Cascading** (60-90% cost savings)
   - No other framework does automatic draft-verify
   - Quality validation built-in

2. **Domain-Aware Routing** (10x cost savings for specialized domains)
   - Code → Deepseek-Coder (95% cheaper than GPT-4)
   - Medical → MedPaLM (specialized model)
   - Automatic domain detection

3. **Multi-Step Validation Pipelines** (Quality + Cost)
   - Domain-specific strategies (code, medical, legal)
   - Custom validation per step

4. **Production-Ready Budget Management** (Zero overages)
   - Per-user tracking + forecasting
   - Graceful degradation (not hard blocks)
   - Tier-aware routing

5. **Zero-Config Production Presets** (2 lines of code)
   - Full-stack configs (models + cost + quality + routing)
   - 90% less config code

**No other framework provides this combination.**

---

## Status: ✅ READY FOR IMPLEMENTATION

**Timeline:** 17 weeks (refined from 16)
**Risk:** Low (building on validated v0.1.1 architecture)
**Value:** High (unique developer experience, 90% cost savings)

**Next Step:** Begin Phase 1 (Weeks 1-4) - Enhanced Cost Control Foundation

**Supporting Documents:**
- `STRATEGIC_ENHANCEMENTS_V0.2.0.md` - Deep analysis of strategic additions
- `V0.2.0_PLAN_VALIDATED.md` - High-level validation
- `INTEGRATION_CORRECTIONS.md` - Integration strategy (FREE libraries only)
- `WHY_CASCADEFLOW_VS_LITELLM.md` - Value proposition
- `LITELLM_FEATURES_ANALYSIS.md` - Feature scope decisions

**All questions answered. All concerns addressed. Strategic additions validated. Plan is ready.**
