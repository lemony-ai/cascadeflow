# CascadeFlow v0.2.0 - Option 3: Full Vision Plan

**Status:** Complete 4-Feature-Area Implementation
**Timeline:** 14-16 weeks
**Approach:** Build on existing telemetry architecture (v2.4)

---

## Existing Foundation (v0.1.1 - Already Built)

### ✅ What We Already Have

**In `cascadeflow/telemetry/`:**

1. **CostCalculator** (v2.4, Oct 2025)
   - Stateless cost calculation
   - Handles accepted/rejected drafts
   - Input + output token support
   - `calculate()` and `calculate_from_tokens()`

2. **CostBreakdown** (v2.4)
   - Structured cost data
   - Draft vs verifier costs
   - Savings analysis
   - Token breakdown

3. **CostTracker** (Basic version)
   - Single global budget limit
   - Warn threshold (80%)
   - By-model and by-provider tracking
   - Cost entries history
   - `add_cost()` method

4. **CostEntry**
   - Timestamp, model, provider, tokens, cost
   - Query ID support
   - Metadata support

5. **MetricsCollector**
   - Aggregates statistics
   - Performance metrics
   - Uses CostCalculator

6. **CallbackManager**
   - Event callbacks

---

## What Needs to Be Added (v0.2.0)

### Feature Area 1: Enhanced Cost Control

#### 1.1 Per-User Budget Tracking
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
        # Existing initialization
        self.budget_limit = budget_limit
        self.warn_threshold = warn_threshold
        self.verbose = verbose

        # Existing tracking
        self.total_cost = 0.0
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_provider: dict[str, float] = defaultdict(float)
        self.entries: list[CostEntry] = []

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
        # Existing logic
        entry = CostEntry(...)
        self.total_cost += cost
        self.by_model[model] += cost
        self.by_provider[provider] += cost
        self.entries.append(entry)

        # NEW: Per-user tracking
        if user_id:
            self.by_user[user_id] += cost
            self.user_entries[user_id].append(entry)
            self._check_user_budget(user_id)

        # Existing budget check
        self._check_budget()

    def _check_user_budget(self, user_id: str) -> None:
        """NEW: Check per-user budget."""
        if user_id not in self.user_budgets:
            return

        budget = self.user_budgets[user_id]
        user_cost = self.by_user[user_id]

        # Check against limits
        if budget.daily and user_cost >= budget.daily:
            logger.warning(f"User {user_id} exceeded daily budget")

    def get_user_summary(self, user_id: str) -> dict:
        """NEW: Get per-user cost summary."""
        return {
            "user_id": user_id,
            "total_cost": self.by_user[user_id],
            "entries": len(self.user_entries[user_id]),
            "budget": self.user_budgets.get(user_id),
            # ... more details
        }
```

#### 1.2 Enforcement Callbacks
**NEW module: `cascadeflow/telemetry/enforcement.py`**

```python
# cascadeflow/telemetry/enforcement.py (NEW FILE)

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

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

    def filter_models(self, ctx: EnforcementContext, models: list) -> list:
        """Filter available models based on user."""
        if self.on_model_filter:
            return self.on_model_filter(ctx, models)
        return models  # Default: no filtering
```

#### 1.3 Intelligent Enforcement (Graceful Degradation)
**ENHANCE existing CostTracker**

```python
# cascadeflow/telemetry/cost_tracker.py (ENHANCE)

class CostTracker:
    def __init__(
        self,
        budget_limit: Optional[float] = None,
        user_budgets: Optional[Dict[str, BudgetConfig]] = None,
        enforcement_mode: str = 'warn',  # NEW: 'warn', 'block', 'degrade'
        enforcement_callbacks: Optional[EnforcementCallbacks] = None,  # NEW
        degrade_at: float = 0.9,  # NEW: Switch to cheaper models at 90%
        block_at: float = 1.0,  # NEW: Hard block at 100%
        warn_threshold: float = 0.8,
        verbose: bool = False,
    ):
        # ... existing + new parameters
        self.enforcement_mode = enforcement_mode
        self.enforcement_callbacks = enforcement_callbacks
        self.degrade_at = degrade_at
        self.block_at = block_at

    def can_afford(
        self,
        user_id: str,
        estimated_cost: float
    ) -> Tuple[bool, str, Optional[str]]:
        """
        NEW: Check if user can afford request.

        Returns:
            (can_proceed, action, message)
            action: 'allow', 'warn', 'block', 'degrade'
        """
        if user_id not in self.user_budgets:
            return True, 'allow', None

        budget = self.user_budgets[user_id]
        current = self.by_user[user_id]
        remaining = budget.daily - current
        pct_used = current / budget.daily if budget.daily else 0

        # Build context
        ctx = EnforcementContext(
            user_id=user_id,
            budget_limit=budget.daily,
            budget_remaining=remaining,
            budget_used=current,
            budget_pct_used=pct_used,
            current_cost=estimated_cost,
            total_requests=len(self.user_entries[user_id])
        )

        # Use callbacks if provided
        if self.enforcement_callbacks:
            action, message = self.enforcement_callbacks.check_budget(ctx)
            return action != 'block', action, message

        # Default enforcement logic
        if pct_used >= self.block_at:
            return False, 'block', f"Budget exceeded ({pct_used:.0%})"
        elif pct_used >= self.degrade_at:
            return True, 'degrade', f"Switching to cheaper models ({pct_used:.0%} budget used)"
        elif pct_used >= self.warn_threshold:
            return True, 'warn', f"Budget {pct_used:.0%} used"
        else:
            return True, 'allow', None
```

#### 1.4 LiteLLM Integration
**NEW module: `cascadeflow/integrations/litellm.py`**

```python
# cascadeflow/integrations/litellm.py (NEW FILE)

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

class LiteLLMCostProvider:
    """Cost calculation using LiteLLM's pricing database."""

    def __init__(self):
        if not LITELLM_AVAILABLE:
            raise ImportError("Install litellm: pip install litellm")

    def get_model_cost(self, model: str, provider: str) -> float:
        """Get cost per 1K tokens from LiteLLM."""
        try:
            return litellm.get_model_cost_map(model)
        except:
            return 0.0  # Fallback

    def calculate_cost(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost using LiteLLM."""
        return litellm.completion_cost(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens
        )
```

#### 1.5 OpenTelemetry Integration
**NEW module: `cascadeflow/integrations/otel.py`**

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
    """Export cost metrics to OpenTelemetry."""

    def __init__(self, endpoint: str = "http://localhost:4318"):
        if not OTEL_AVAILABLE:
            raise ImportError("Install opentelemetry: pip install opentelemetry-api opentelemetry-sdk")

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

#### 1.6 Cost Forecasting
**NEW module: `cascadeflow/telemetry/forecasting.py`**

```python
# cascadeflow/telemetry/forecasting.py (NEW FILE)

from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass
class CostPrediction:
    """Cost forecast prediction."""
    mean: float
    std: float
    lower: float
    upper: float
    risk_score: float  # Probability of exceeding budget

class CostForecaster:
    """Forecast future costs based on historical data."""

    def __init__(self, history: List[CostEntry]):
        self.history = history

    def predict_monthly_cost(
        self,
        user_id: Optional[str] = None,
        confidence_interval: float = 0.95
    ) -> CostPrediction:
        """
        Predict monthly cost using exponential smoothing.

        Args:
            user_id: Optional user ID for per-user forecast
            confidence_interval: Confidence level (0.95 = 95%)

        Returns:
            Cost prediction with confidence interval
        """
        # Filter by user if specified
        entries = [e for e in self.history if user_id is None or e.metadata.get('user_id') == user_id]

        if len(entries) < 7:  # Need at least 1 week of data
            return CostPrediction(0, 0, 0, 0, 0)

        # Group by day
        daily_costs = self._group_by_day(entries)

        # Simple exponential smoothing
        alpha = 0.3  # Smoothing factor
        forecast = daily_costs[0]
        for cost in daily_costs[1:]:
            forecast = alpha * cost + (1 - alpha) * forecast

        # Scale to monthly (30 days)
        monthly = forecast * 30

        # Calculate std dev
        std = np.std(daily_costs) * np.sqrt(30)

        # Confidence interval
        z = 1.96 if confidence_interval == 0.95 else 2.576
        lower = monthly - z * std
        upper = monthly + z * std

        # Risk score (mock - would need proper distribution)
        risk_score = 0.0

        return CostPrediction(
            mean=monthly,
            std=std,
            lower=max(0, lower),
            upper=upper,
            risk_score=risk_score
        )

    def _group_by_day(self, entries: List[CostEntry]) -> List[float]:
        """Group costs by day."""
        by_day = defaultdict(float)
        for entry in entries:
            day = entry.timestamp.date()
            by_day[day] += entry.cost
        return list(by_day.values())
```

#### 1.7 Anomaly Detection
**NEW module: `cascadeflow/telemetry/anomaly.py`**

```python
# cascadeflow/telemetry/anomaly.py (NEW FILE)

@dataclass
class Anomaly:
    """Detected cost anomaly."""
    timestamp: datetime
    user_id: str
    expected: float
    actual: float
    severity: str  # 'low', 'medium', 'high'
    description: str

class AnomalyDetector:
    """Detect unusual spending patterns."""

    def __init__(
        self,
        history: List[CostEntry],
        sensitivity: str = 'medium'  # 'low', 'medium', 'high'
    ):
        self.history = history
        self.sensitivity = sensitivity

    def detect_anomalies(
        self,
        user_id: Optional[str] = None,
        window_days: int = 7
    ) -> List[Anomaly]:
        """
        Detect anomalies using z-score method.

        Args:
            user_id: Optional user ID to check
            window_days: Rolling window size in days

        Returns:
            List of detected anomalies
        """
        # Filter by user
        entries = [e for e in self.history if user_id is None or e.metadata.get('user_id') == user_id]

        if len(entries) < window_days:
            return []

        # Group by day
        daily_costs = self._group_by_day(entries)

        # Calculate rolling mean and std
        mean = np.mean(daily_costs)
        std = np.std(daily_costs)

        # Z-score threshold based on sensitivity
        thresholds = {'low': 3.0, 'medium': 2.5, 'high': 2.0}
        threshold = thresholds[self.sensitivity]

        # Detect anomalies
        anomalies = []
        for i, cost in enumerate(daily_costs):
            z_score = abs((cost - mean) / std) if std > 0 else 0

            if z_score > threshold:
                severity = 'high' if z_score > 3.0 else 'medium' if z_score > 2.5 else 'low'

                anomalies.append(Anomaly(
                    timestamp=entries[i].timestamp,
                    user_id=user_id or 'global',
                    expected=mean,
                    actual=cost,
                    severity=severity,
                    description=f"Cost {z_score:.1f}σ above mean"
                ))

        return anomalies
```

---

### Feature Area 2: User Tier Management

**Implementation: Enforcement Callbacks (already covered in 1.2)**

The user tier management is implemented via the callback system, NOT static tiers. Developers integrate with their existing user systems (Stripe, Auth0, Firebase) via callbacks.

**No additional code needed** - covered by `EnforcementCallbacks` above.

---

### Feature Area 3: Semantic Quality System

#### 3.1 Rule-Based Quality (Enhance Existing)
**Location: `cascadeflow/quality/` (Already exists)**

```python
# cascadeflow/quality/validation.py (ENHANCE EXISTING)

class QualityValidator:
    """Quality validation (rule-based by default)."""

    def __init__(
        self,
        enable_hedging_check: bool = True,
        enable_coherence_check: bool = True,
        enable_semantic_similarity: bool = False,  # Opt-in ML
        enable_toxicity_detection: bool = False,   # Opt-in ML
    ):
        self.enable_hedging_check = enable_hedging_check
        self.enable_coherence_check = enable_coherence_check
        self.enable_semantic_similarity = enable_semantic_similarity
        self.enable_toxicity_detection = enable_toxicity_detection

        # Load ML models only if enabled
        if enable_semantic_similarity or enable_toxicity_detection:
            self._load_ml_models()

    def _load_ml_models(self):
        """Load ML models (opt-in)."""
        try:
            from fastembed import TextEmbedding
            self.embedder = TextEmbedding('all-MiniLM-L6-v2')
        except ImportError:
            raise ImportError(
                "ML quality features require: pip install cascadeflow[semantic]"
            )

    def validate(self, query: str, response: str) -> QualityScore:
        """
        Validate response quality.

        Returns quality score with confidence.
        """
        score = QualityScore()

        # Rule-based checks (always run)
        if self.enable_hedging_check:
            score.hedging = self._check_hedging(response)

        if self.enable_coherence_check:
            score.coherence = self._check_coherence(response)

        # ML checks (opt-in only)
        if self.enable_semantic_similarity:
            score.semantic_similarity = self._check_semantic_similarity(query, response)

        if self.enable_toxicity_detection:
            score.toxicity = self._check_toxicity(response)

        return score
```

#### 3.2 Optional ML Quality (Opt-In)
**NEW module: `cascadeflow/quality/semantic.py`**

```python
# cascadeflow/quality/semantic.py (NEW FILE - OPT-IN)

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False

class SemanticQualityChecker:
    """ML-based quality validation (opt-in)."""

    def __init__(self):
        if not FASTEMBED_AVAILABLE:
            raise ImportError(
                "Install semantic features: pip install cascadeflow[semantic]"
            )

        self.embedder = TextEmbedding('all-MiniLM-L6-v2')  # 80MB

    def check_semantic_similarity(
        self,
        query: str,
        response: str,
        threshold: float = 0.7
    ) -> float:
        """
        Check if response is semantically similar to query.

        Returns similarity score (0-1).
        """
        query_emb = self.embedder.embed([query])[0]
        response_emb = self.embedder.embed([response])[0]

        # Cosine similarity
        similarity = np.dot(query_emb, response_emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(response_emb)
        )

        return float(similarity)
```

#### 3.3 Quality Presets
**NEW: `cascadeflow/quality/presets.py`**

```python
# cascadeflow/quality/presets.py (NEW FILE)

@dataclass
class QualityPreset:
    """Quality validation preset."""
    name: str
    enable_hedging_check: bool
    enable_coherence_check: bool
    enable_semantic_similarity: bool
    enable_toxicity_detection: bool

    @classmethod
    def fast(cls):
        """Fast mode: Rule-based only (3-5ms)."""
        return cls(
            name='fast',
            enable_hedging_check=True,
            enable_coherence_check=True,
            enable_semantic_similarity=False,
            enable_toxicity_detection=False
        )

    @classmethod
    def balanced(cls):
        """Balanced mode: Rules + ML (50-100ms)."""
        return cls(
            name='balanced',
            enable_hedging_check=True,
            enable_coherence_check=True,
            enable_semantic_similarity=True,
            enable_toxicity_detection=False
        )

    @classmethod
    def strict(cls):
        """Strict mode: All validations (500-1000ms)."""
        return cls(
            name='strict',
            enable_hedging_check=True,
            enable_coherence_check=True,
            enable_semantic_similarity=True,
            enable_toxicity_detection=True
        )
```

---

### Feature Area 4: Domain-Aware Routing

#### 4.1 Rule-Based Domain Detection
**NEW module: `cascadeflow/routing/domain.py`**

```python
# cascadeflow/routing/domain.py (NEW FILE)

from typing import Optional, Tuple
import re

class DomainDetector:
    """Detect query domain (rule-based by default)."""

    # Domain keywords
    CODE_KEYWORDS = [
        'function', 'class', 'method', 'variable', 'implement',
        'algorithm', 'code', 'programming', 'debug', 'error',
        'syntax', 'compile', 'runtime', 'api', 'library'
    ]

    MEDICAL_KEYWORDS = [
        'diagnosis', 'treatment', 'patient', 'symptom', 'disease',
        'medication', 'doctor', 'hospital', 'medical', 'health',
        'clinical', 'therapy', 'prescription'
    ]

    LEGAL_KEYWORDS = [
        'contract', 'law', 'legal', 'court', 'judge', 'attorney',
        'plaintiff', 'defendant', 'liability', 'statute', 'regulation'
    ]

    def __init__(
        self,
        domains: List[str] = ['code', 'medical', 'legal', 'general'],
        enable_semantic: bool = False  # Opt-in ML
    ):
        self.domains = domains
        self.enable_semantic = enable_semantic

        if enable_semantic:
            self._load_semantic_model()

    def detect(
        self,
        query: str,
        min_confidence: float = 0.7
    ) -> Tuple[str, float]:
        """
        Detect query domain.

        Returns:
            (domain, confidence)
        """
        # Rule-based detection (fast, <1ms)
        domain, confidence = self._detect_by_rules(query)

        if confidence >= min_confidence:
            return domain, confidence

        # Semantic detection (opt-in, slower)
        if self.enable_semantic:
            return self._detect_by_semantic(query)

        # Fallback
        return 'general', 0.5

    def _detect_by_rules(self, query: str) -> Tuple[str, float]:
        """Rule-based detection using keywords."""
        query_lower = query.lower()

        # Count matches for each domain
        code_matches = sum(1 for kw in self.CODE_KEYWORDS if kw in query_lower)
        medical_matches = sum(1 for kw in self.MEDICAL_KEYWORDS if kw in query_lower)
        legal_matches = sum(1 for kw in self.LEGAL_KEYWORDS if kw in query_lower)

        # Determine domain
        max_matches = max(code_matches, medical_matches, legal_matches)

        if max_matches == 0:
            return 'general', 0.5

        if code_matches == max_matches:
            return 'code', min(0.9, code_matches / 5)
        elif medical_matches == max_matches:
            return 'medical', min(0.9, medical_matches / 5)
        elif legal_matches == max_matches:
            return 'legal', min(0.9, legal_matches / 5)
        else:
            return 'general', 0.5
```

#### 4.2 Domain-Aware Model Routing
**ENHANCE: `cascadeflow/core/agent.py`**

```python
# cascadeflow/core/agent.py (ENHANCE)

class CascadeAgent:
    def __init__(
        self,
        models: List[ModelConfig],
        cost_tracker: Optional[CostTracker] = None,
        domain_detector: Optional[DomainDetector] = None,  # NEW
        domain_model_map: Optional[Dict[str, List[str]]] = None,  # NEW
        # ... existing parameters
    ):
        self.models = models
        self.cost_tracker = cost_tracker
        self.domain_detector = domain_detector
        self.domain_model_map = domain_model_map or {}

    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        domain: Optional[str] = None,  # NEW: Explicit domain override
        # ... existing parameters
    ):
        """Run cascade with domain-aware routing."""

        # Detect domain if not specified
        if not domain and self.domain_detector:
            domain, confidence = self.domain_detector.detect(query)

        # Filter models by domain
        available_models = self._filter_models_by_domain(domain)

        # Continue with existing cascade logic...

    def _filter_models_by_domain(self, domain: str) -> List[ModelConfig]:
        """Filter models appropriate for domain."""
        if domain not in self.domain_model_map:
            return self.models  # All models

        allowed_models = self.domain_model_map[domain]
        return [m for m in self.models if m.name in allowed_models]
```

#### 4.3 Code Complexity Analysis (Optional)
**NEW module: `cascadeflow/routing/complexity.py`**

```python
# cascadeflow/routing/complexity.py (NEW FILE - OPTIONAL)

class CodeComplexityAnalyzer:
    """Analyze code query complexity."""

    # Simple keywords
    SIMPLE_KEYWORDS = ['hello', 'print', 'add', 'subtract']

    # Medium complexity
    MEDIUM_KEYWORDS = ['loop', 'array', 'list', 'dictionary', 'function']

    # High complexity
    COMPLEX_KEYWORDS = [
        'algorithm', 'optimize', 'concurrent', 'async', 'database',
        'architecture', 'design pattern', 'refactor'
    ]

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Analyze code query complexity.

        Returns:
            {
                'complexity': 'simple' | 'medium' | 'high',
                'requires_reasoning': bool,
                'suggested_model': str,
                'estimated_tokens': int
            }
        """
        query_lower = query.lower()

        # Check complexity level
        if any(kw in query_lower for kw in self.COMPLEX_KEYWORDS):
            complexity = 'high'
            model = 'gpt-4'
            tokens = 500
        elif any(kw in query_lower for kw in self.MEDIUM_KEYWORDS):
            complexity = 'medium'
            model = 'gpt-3.5-turbo'
            tokens = 200
        else:
            complexity = 'simple'
            model = 'gpt-3.5-turbo'
            tokens = 100

        return {
            'complexity': complexity,
            'requires_reasoning': complexity == 'high',
            'suggested_model': model,
            'estimated_tokens': tokens
        }
```

#### 4.4 Semantic Domain Detection (Opt-In ML)
**NEW module: `cascadeflow/routing/semantic_router.py`**

```python
# cascadeflow/routing/semantic_router.py (NEW FILE - OPT-IN)

try:
    from semantic_router import Route, RouteLayer
    SEMANTIC_ROUTER_AVAILABLE = True
except ImportError:
    SEMANTIC_ROUTER_AVAILABLE = False

class SemanticDomainRouter:
    """Semantic domain routing using pre-trained models."""

    def __init__(self):
        if not SEMANTIC_ROUTER_AVAILABLE:
            raise ImportError(
                "Install semantic routing: pip install cascadeflow[semantic]"
            )

        # Pre-configured routes
        self.routes = [
            Route(
                name="code",
                utterances=[
                    "How do I implement quicksort?",
                    "What's wrong with my code?",
                    "Write a function to reverse a string",
                    # ... more examples
                ]
            ),
            Route(
                name="medical",
                utterances=[
                    "What are the symptoms of diabetes?",
                    "How is pneumonia treated?",
                    # ... more examples
                ]
            ),
            # ... more routes
        ]

        self.router = RouteLayer(routes=self.routes)

    def detect(self, query: str) -> Tuple[str, float]:
        """Detect domain using semantic similarity."""
        result = self.router(query)
        return result.name, result.score
```

---

## Implementation Roadmap (14-16 Weeks)

### Phase 1: Enhanced Cost Control Foundation (Weeks 1-4)

**Week 1: Per-User Budget Tracking**
- [ ] Enhance `CostTracker` with per-user budgets
- [ ] Add `user_budgets` parameter
- [ ] Add `by_user` tracking
- [ ] Add `_check_user_budget()` method
- [ ] Add `get_user_summary()` method
- [ ] Tests

**Week 2: Enforcement Callbacks**
- [ ] Create `cascadeflow/telemetry/enforcement.py`
- [ ] `EnforcementContext` dataclass
- [ ] `EnforcementCallbacks` class
- [ ] `check_budget()` method
- [ ] `filter_models()` method
- [ ] Integration examples (Stripe, Auth0, Firebase)
- [ ] Tests

**Week 3: Intelligent Enforcement**
- [ ] Enhance `CostTracker` with enforcement modes
- [ ] Add `can_afford()` method
- [ ] Implement graceful degradation logic
- [ ] Add `enforcement_mode` parameter ('warn', 'block', 'degrade')
- [ ] Add `degrade_at` and `block_at` thresholds
- [ ] Tests

**Week 4: Local Storage & Export**
- [ ] Add JSON export (`export_json()`)
- [ ] Add CSV export (`export_csv()`)
- [ ] Add SQLite storage option
- [ ] Add `load_from_file()` method
- [ ] Tests

### Phase 2: Integration Layer (Weeks 5-6)

**Week 5: LiteLLM Integration**
- [ ] Create `cascadeflow/integrations/litellm.py`
- [ ] `LiteLLMCostProvider` class
- [ ] Integrate with `CostCalculator`
- [ ] Support 100+ providers
- [ ] Tests

**Week 6: OpenTelemetry Integration**
- [ ] Create `cascadeflow/integrations/otel.py`
- [ ] `OpenTelemetryExporter` class
- [ ] Cost metrics export
- [ ] Token metrics export
- [ ] Integration examples (Datadog, Grafana, CloudWatch)
- [ ] Tests

### Phase 3: Intelligence Layer (Weeks 7-9)

**Week 7: Cost Forecasting**
- [ ] Create `cascadeflow/telemetry/forecasting.py`
- [ ] `CostPrediction` dataclass
- [ ] `CostForecaster` class
- [ ] Exponential smoothing algorithm
- [ ] Per-user forecasting
- [ ] Tests

**Week 8: Anomaly Detection**
- [ ] Create `cascadeflow/telemetry/anomaly.py`
- [ ] `Anomaly` dataclass
- [ ] `AnomalyDetector` class
- [ ] Z-score detection
- [ ] Per-user anomaly detection
- [ ] Tests

**Week 9: Buffer/Polish**
- [ ] Fix any issues from Weeks 7-8
- [ ] Performance optimization
- [ ] Documentation

### Phase 4: Quality System (Weeks 10-12)

**Week 10: Rule-Based Quality Enhancement**
- [ ] Enhance `cascadeflow/quality/validation.py`
- [ ] `QualityValidator` class
- [ ] Rule-based checks (hedging, coherence)
- [ ] Quality presets (`QualityPreset.fast()`)
- [ ] Tests

**Week 11: Optional ML Quality**
- [ ] Create `cascadeflow/quality/semantic.py`
- [ ] `SemanticQualityChecker` class (opt-in)
- [ ] FastEmbed integration
- [ ] Semantic similarity check
- [ ] Optional dependency handling
- [ ] Tests

**Week 12: Quality Presets & Integration**
- [ ] Create `cascadeflow/quality/presets.py`
- [ ] `QualityPreset.fast()`, `.balanced()`, `.strict()`
- [ ] Integrate quality validation with agent
- [ ] Quality callbacks
- [ ] Tests

### Phase 5: Domain Routing (Weeks 13-15)

**Week 13: Rule-Based Domain Detection**
- [ ] Create `cascadeflow/routing/domain.py`
- [ ] `DomainDetector` class
- [ ] Rule-based detection (keywords)
- [ ] Domain confidence scoring
- [ ] Tests

**Week 14: Domain-Aware Routing**
- [ ] Enhance `CascadeAgent` with domain routing
- [ ] `domain_detector` parameter
- [ ] `domain_model_map` parameter
- [ ] `_filter_models_by_domain()` method
- [ ] Domain override support
- [ ] Tests

**Week 15: Optional ML Domain Routing & Code Complexity**
- [ ] Create `cascadeflow/routing/semantic_router.py` (opt-in)
- [ ] Create `cascadeflow/routing/complexity.py` (optional)
- [ ] Pre-trained domain models
- [ ] Code complexity analyzer
- [ ] Tests

### Phase 6: Testing & Documentation (Week 16)

**Week 16: Integration Testing & Docs**
- [ ] End-to-end integration tests
- [ ] Load testing (10K+ requests)
- [ ] Performance benchmarking
- [ ] Complete API documentation
- [ ] Migration guide from v0.1.1
- [ ] Cookbook with examples
- [ ] Integration examples (Stripe, Auth0, Firebase, Datadog, Grafana)
- [ ] Release prep

---

## File Structure (New Files)

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
│   ├── domain.py (NEW)
│   ├── complexity.py (NEW)
│   └── semantic_router.py (NEW - opt-in)
├── integrations/
│   ├── __init__.py (NEW)
│   ├── litellm.py (NEW)
│   └── otel.py (NEW)
└── core/
    └── agent.py (existing - ENHANCE)
```

---

## Dependencies

### Core (Required)
```
# No new required dependencies (builds on existing)
```

### Optional (Opt-In)
```
# pip install cascadeflow[semantic]
fastembed>=0.2.0
transformers>=4.30.0

# pip install cascadeflow[integrations]
litellm>=1.0.0
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0

# pip install cascadeflow[routing]
semantic-router>=0.0.20

# pip install cascadeflow[all]
# (all of the above)
```

---

## Success Metrics (3 Months Post-Launch)

### Technical
- ✅ All 4 feature areas implemented
- ✅ 100% backward compatibility with v0.1.1
- ✅ Support 100+ providers via LiteLLM
- ✅ <200ms overhead (rule-based mode)
- ✅ <10% forecasting error
- ✅ >90% domain detection accuracy
- ✅ >85% quality validation accuracy

### Adoption
- 50% adopt per-user tracking
- 40% use enforcement callbacks
- 30% enable domain routing
- 25% enable semantic quality
- >4.5/5 developer satisfaction

### Business
- 83-90% average cost savings
- Zero budget bypass incidents
- >50 production deployments in 3 months

---

## Risk Management

**Risk 1: Timeline Slippage**
- **Mitigation:** Weekly progress reviews, adjust scope
- **Fallback:** Ship MVP (8 weeks), defer ML features to v0.2.1

**Risk 2: ML Dependencies**
- **Mitigation:** Optional dependencies, graceful degradation
- **Fallback:** Rule-based only for v0.2.0, ML in v0.2.1

**Risk 3: Performance Overhead**
- **Mitigation:** Benchmarking gates, async validation
- **Target:** <200ms overhead (rule-based), <500ms (ML)

**Risk 4: Complexity**
- **Mitigation:** Extensive examples, presets, clear docs
- **Fallback:** Simplify API, reduce configuration options

---

## Summary

**Option 3: Full Vision** delivers:

1. ✅ **Cost Control** - Enhanced (per-user, enforcement, forecasting, anomaly detection)
2. ✅ **User Tiers** - Flexible (callbacks, not static)
3. ✅ **Quality System** - Complete (rule-based + opt-in ML)
4. ✅ **Domain Routing** - Complete (rule-based + opt-in ML)

**Timeline:** 14-16 weeks (vs. 8 weeks for cost-only)

**Builds on Existing:** All enhancements build on top of existing `CostCalculator`, `CostTracker`, and quality system.

**Backward Compatible:** 100% compatible with v0.1.1 - all existing code continues to work.

**Risk:** Medium (more features, longer timeline, but lower-risk rule-based approach with opt-in ML)

**Result:** Complete optimization platform covering all 4 feature areas.

---

**Status:** ✅ Ready for Implementation
**Recommendation:** Option 3 if 14-16 weeks acceptable, otherwise Option 2 (10-12 weeks)
