# Custom Cascade Guide

Build custom cascade strategies tailored to your specific use case.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Domain-Specific Routing](#domain-specific-routing)
3. [Time-Based Routing](#time-based-routing)
4. [Budget-Aware Cascades](#budget-aware-cascades)
5. [Custom Quality Thresholds](#custom-quality-thresholds)
6. [Advanced Patterns](#advanced-patterns)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## Overview

While CascadeFlow provides built-in cascade strategies, you can create custom routing logic for specific needs.

### When to Use Custom Cascades

- **Domain-specific workloads** - Route by content type (code, writing, data)
- **Time-sensitive pricing** - Optimize by time of day
- **Budget constraints** - Enforce strict cost limits
- **Compliance requirements** - Different quality bars by domain
- **A/B testing** - Compare cascade strategies

---

## Domain-Specific Routing

Route queries to specialized model configurations based on detected domain.

### Pattern

```python
from cascadeflow import CascadeAgent, ModelConfig

class DomainRouter:
    DOMAIN_KEYWORDS = {
        "code": ["python", "javascript", "function", "bug", "api"],
        "writing": ["write", "essay", "article", "email"],
        "data": ["csv", "dataframe", "sql", "analyze"],
        "general": []
    }
    
    @staticmethod
    def detect_domain(query: str) -> str:
        """Detect query domain from keywords."""
        query_lower = query.lower()
        for domain, keywords in DomainRouter.DOMAIN_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return domain
        return "general"
    
    @staticmethod
    def get_models_for_domain(domain: str) -> List[ModelConfig]:
        """Get optimal models for domain."""
        if domain == "code":
            # OpenAI best for code
            return [
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]
        elif domain == "writing":
            # Anthropic best for writing
            return [
                ModelConfig("claude-3-5-haiku", provider="anthropic", cost=0.001),
                ModelConfig("claude-3-5-sonnet", provider="anthropic", cost=0.003),
            ]
        elif domain == "data":
            # Groq fast enough for data tasks
            return [
                ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0.0),
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
            ]
        else:
            # General: free-first
            return [
                ModelConfig("llama-3.1-8b", provider="groq", cost=0.0),
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]

# Usage
domain = DomainRouter.detect_domain("Fix this Python bug")
models = DomainRouter.get_models_for_domain(domain)
agent = CascadeAgent(models=models)
result = await agent.run(query)
```

### Benefits

- **20-40% better quality** - Right specialist for each task
- **30% cost savings** - Avoid premium for simple domains
- **Flexibility** - Easy to add new domains

### Extending

Add more sophisticated domain detection:

```python
from cascadeflow.quality import ComplexityDetector

class AdvancedDomainRouter:
    def __init__(self):
        self.complexity_detector = ComplexityDetector()
        self.embedding_model = None  # Add semantic similarity
    
    def detect_domain(self, query: str) -> tuple[str, float]:
        """Detect domain with confidence score."""
        # Keyword-based detection
        keyword_domain = self._keyword_detection(query)
        
        # Complexity-based adjustment
        complexity = self.complexity_detector.detect(query)
        
        # Semantic similarity (if available)
        if self.embedding_model:
            semantic_domain = self._semantic_detection(query)
            # Combine signals
            domain = self._combine_signals(keyword_domain, semantic_domain)
        else:
            domain = keyword_domain
        
        return domain, confidence
```

---

## Time-Based Routing

Optimize costs by using cheaper models during off-peak hours.

### Pattern

```python
from datetime import datetime

class TimeBasedRouter:
    @staticmethod
    def is_peak_hours() -> bool:
        """Check if current time is peak (9am-5pm)."""
        hour = datetime.now().hour
        return 9 <= hour < 17
    
    @staticmethod
    def get_models_for_time() -> List[ModelConfig]:
        """Get models optimized for current time."""
        if TimeBasedRouter.is_peak_hours():
            # Peak: prioritize speed
            return [
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]
        else:
            # Off-peak: prioritize cost
            return [
                ModelConfig("llama-3.1-8b", provider="groq", cost=0.0),
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]

# Usage
models = TimeBasedRouter.get_models_for_time()
agent = CascadeAgent(models=models)
```

### Benefits

- **60-80% cost savings** during off-peak
- **Automatic optimization** - No manual intervention
- **User transparency** - Can inform users of wait times

### Advanced: Dynamic Pricing

```python
class DynamicPricingRouter:
    PRICING_TIERS = {
        "peak": 1.0,      # 9am-5pm weekday
        "normal": 0.7,    # Weekday evening
        "discount": 0.5,  # Weekend/night
    }
    
    @staticmethod
    def get_current_tier() -> str:
        """Determine current pricing tier."""
        now = datetime.now()
        is_weekend = now.weekday() >= 5
        hour = now.hour
        
        if is_weekend or hour < 6 or hour >= 22:
            return "discount"
        elif 9 <= hour < 17:
            return "peak"
        else:
            return "normal"
    
    @staticmethod
    def get_budget_adjusted_models(base_budget: float) -> List[ModelConfig]:
        """Adjust model selection based on time-based budget."""
        tier = DynamicPricingRouter.get_current_tier()
        multiplier = DynamicPricingRouter.PRICING_TIERS[tier]
        effective_budget = base_budget * multiplier
        
        # Select models within effective budget
        models = []
        if effective_budget >= 0.001:
            models.append(ModelConfig("llama-3.1-8b", provider="groq", cost=0.0))
        if effective_budget >= 0.002:
            models.append(ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015))
        if effective_budget >= 0.01:
            models.append(ModelConfig("gpt-4o", provider="openai", cost=0.00625))
        
        return models
```

---

## Budget-Aware Cascades

Enforce strict per-query or aggregate budget limits.

### Pattern

```python
class BudgetAwareCascade:
    def __init__(self, max_cost_per_query: float = 0.01):
        self.max_cost = max_cost_per_query
        self.total_spent = 0.0
        self.queries_processed = 0
        self.queries_blocked = 0
    
    def get_models_within_budget(self) -> List[ModelConfig]:
        """Get models that fit within budget."""
        models = []
        
        # Free models (always within budget)
        models.append(ModelConfig("llama-3.1-8b", provider="groq", cost=0.0))
        
        # Add paid models if budget allows
        if self.max_cost >= 0.0002:
            models.append(ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015))
        
        if self.max_cost >= 0.006:
            models.append(ModelConfig("gpt-4o", provider="openai", cost=0.00625))
        
        return models
    
    async def process_with_budget(self, query: str, **kwargs):
        """Process query within budget constraints."""
        models = self.get_models_within_budget()
        
        if not models:
            self.queries_blocked += 1
            raise Exception(f"Budget ${self.max_cost:.6f} too low for any models")
        
        agent = CascadeAgent(models=models)
        result = await agent.run(query, **kwargs)
        
        self.queries_processed += 1
        self.total_spent += result.total_cost
        
        return result
    
    def get_stats(self) -> dict:
        """Get budget statistics."""
        return {
            "queries_processed": self.queries_processed,
            "queries_blocked": self.queries_blocked,
            "total_spent": self.total_spent,
            "avg_cost": self.total_spent / self.queries_processed 
                if self.queries_processed > 0 else 0
        }

# Usage
cascade = BudgetAwareCascade(max_cost_per_query=0.001)
result = await cascade.process_with_budget("What is Python?")
```

### Advanced: Multi-Tier Budgets

```python
class MultiTierBudget:
    def __init__(self, budgets: dict):
        """
        Args:
            budgets: {
                "hourly": 1.0,
                "daily": 10.0,
                "monthly": 250.0
            }
        """
        self.budgets = budgets
        self.spent = {"hourly": 0.0, "daily": 0.0, "monthly": 0.0}
        self.reset_times = {
            "hourly": datetime.now(),
            "daily": datetime.now(),
            "monthly": datetime.now()
        }
    
    def reset_if_needed(self):
        """Reset budgets if time windows passed."""
        now = datetime.now()
        
        # Hourly reset
        if (now - self.reset_times["hourly"]).seconds >= 3600:
            self.spent["hourly"] = 0.0
            self.reset_times["hourly"] = now
        
        # Daily reset
        if (now - self.reset_times["daily"]).days >= 1:
            self.spent["daily"] = 0.0
            self.reset_times["daily"] = now
        
        # Monthly reset (simplified)
        if (now - self.reset_times["monthly"]).days >= 30:
            self.spent["monthly"] = 0.0
            self.reset_times["monthly"] = now
    
    def can_afford(self, estimated_cost: float) -> bool:
        """Check if within all budget limits."""
        self.reset_if_needed()
        
        for period, budget in self.budgets.items():
            if self.spent[period] + estimated_cost > budget:
                return False
        return True
    
    def record_cost(self, cost: float):
        """Record cost across all periods."""
        for period in self.spent:
            self.spent[period] += cost
```

---

## Custom Quality Thresholds

Set different quality requirements by domain or criticality.

### Pattern

```python
class QualityThresholdRouter:
    # Domain-specific thresholds
    THRESHOLDS = {
        "medical": 0.95,    # Very strict
        "legal": 0.92,      # Strict
        "financial": 0.90,  # High
        "general": 0.75,    # Standard
        "casual": 0.60,     # Lenient
    }
    
    @staticmethod
    def get_threshold_for_domain(domain: str) -> float:
        """Get quality threshold for domain."""
        return QualityThresholdRouter.THRESHOLDS.get(domain, 0.75)
    
    @staticmethod
    def get_config_for_domain(domain: str) -> dict:
        """Get complete config including models and settings."""
        threshold = QualityThresholdRouter.get_threshold_for_domain(domain)
        
        # High-stakes domains: use premium models
        if threshold >= 0.90:
            models = [
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]
            temperature = 0.3  # Lower for factual accuracy
        else:
            models = [
                ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
                ModelConfig("gpt-4o", provider="openai", cost=0.00625),
            ]
            temperature = 0.7
        
        return {
            "models": models,
            "threshold": threshold,
            "temperature": temperature
        }

# Usage
config = QualityThresholdRouter.get_config_for_domain("medical")
agent = CascadeAgent(models=config["models"])
result = await agent.run(
    query,
    temperature=config["temperature"]
)
```

### Compliance Requirements

For regulated industries:

```python
class ComplianceRouter:
    REGULATED_DOMAINS = ["medical", "legal", "financial"]
    
    @staticmethod
    def requires_audit_trail(domain: str) -> bool:
        """Check if domain requires audit logging."""
        return domain in ComplianceRouter.REGULATED_DOMAINS
    
    @staticmethod
    async def process_with_compliance(
        query: str,
        domain: str,
        agent: CascadeAgent
    ):
        """Process query with compliance requirements."""
        requires_audit = ComplianceRouter.requires_audit_trail(domain)
        
        # Use premium models for regulated content
        if requires_audit:
            result = await agent.run(
                query,
                force_direct=True,  # Skip cascade for consistency
                temperature=0.2,     # Low variance
            )
            
            # Log for audit
            await ComplianceRouter.log_query(
                query=query,
                result=result,
                domain=domain,
                timestamp=datetime.now()
            )
        else:
            # Standard processing
            result = await agent.run(query)
        
        return result
```

---

## Advanced Patterns

### Adaptive Routing

Learn optimal routing from historical performance:

```python
class AdaptiveRouter:
    def __init__(self):
        self.performance_history = []  # [(domain, model, quality_score)]
        self.model_rankings = {}       # domain -> [models ranked by performance]
    
    def record_performance(self, domain: str, model: str, score: float):
        """Record model performance for domain."""
        self.performance_history.append((domain, model, score))
        self._update_rankings()
    
    def _update_rankings(self):
        """Update model rankings based on history."""
        from collections import defaultdict
        
        # Group by domain
        domain_scores = defaultdict(list)
        for domain, model, score in self.performance_history[-1000:]:  # Last 1000
            domain_scores[domain].append((model, score))
        
        # Rank models for each domain
        for domain, scores in domain_scores.items():
            # Average score per model
            model_avgs = defaultdict(list)
            for model, score in scores:
                model_avgs[model].append(score)
            
            # Sort by average score
            ranked = sorted(
                model_avgs.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True
            )
            self.model_rankings[domain] = [m for m, _ in ranked]
    
    def get_optimal_models(self, domain: str) -> List[ModelConfig]:
        """Get models ranked by historical performance."""
        if domain not in self.model_rankings:
            return self._get_default_models()
        
        # Return top-performing models for domain
        ranked_names = self.model_rankings[domain]
        return [self._name_to_config(name) for name in ranked_names[:3]]
```

### A/B Testing Cascades

Compare different strategies:

```python
class ABTestRouter:
    def __init__(self, strategy_a: callable, strategy_b: callable):
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.results_a = []
        self.results_b = []
    
    async def route_with_ab_test(self, query: str, user_id: str):
        """Route query using A/B test."""
        # Assign to strategy based on user_id hash
        if hash(user_id) % 2 == 0:
            strategy = self.strategy_a
            results = self.results_a
            variant = "A"
        else:
            strategy = self.strategy_b
            results = self.results_b
            variant = "B"
        
        # Execute
        models = strategy(query)
        agent = CascadeAgent(models=models)
        result = await agent.run(query)
        
        # Record metrics
        results.append({
            "cost": result.total_cost,
            "latency": result.latency_ms,
            "quality": result.quality_score,
            "variant": variant
        })
        
        return result
    
    def get_comparison(self) -> dict:
        """Compare A/B test results."""
        return {
            "strategy_a": {
                "avg_cost": sum(r["cost"] for r in self.results_a) / len(self.results_a),
                "avg_latency": sum(r["latency"] for r in self.results_a) / len(self.results_a),
                "samples": len(self.results_a)
            },
            "strategy_b": {
                "avg_cost": sum(r["cost"] for r in self.results_b) / len(self.results_b),
                "avg_latency": sum(r["latency"] for r in self.results_b) / len(self.results_b),
                "samples": len(self.results_b)
            }
        }
```

---

## Best Practices

### 1. Start Simple

Begin with keyword-based routing before adding complexity:

```python
# Good: Simple, maintainable
if "code" in query.lower():
    models = code_models
else:
    models = general_models

# Avoid: Over-engineered initially
models = ml_model.predict_optimal_cascade(
    query_embedding, user_history, time_features, weather_data
)
```

### 2. Monitor Performance

Track metrics for each routing decision:

```python
class MonitoredRouter:
    def __init__(self):
        self.decisions = []
    
    async def route(self, query: str):
        start = time.time()
        domain = self.detect_domain(query)
        models = self.get_models(domain)
        
        self.decisions.append({
            "query": query[:100],
            "domain": domain,
            "models": [m.name for m in models],
            "timestamp": datetime.now(),
            "detection_time_ms": (time.time() - start) * 1000
        })
        
        return models
```

### 3. Provide Fallbacks

Always have a default strategy:

```python
def get_models_safe(domain: str) -> List[ModelConfig]:
    """Get models with fallback."""
    try:
        return DOMAIN_STRATEGIES.get(domain, default_strategy)()
    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return default_strategy()
```

### 4. Test Thoroughly

Test each routing path:

```python
def test_domain_routing():
    router = DomainRouter()
    
    # Test each domain
    assert router.detect_domain("Fix Python bug") == "code"
    assert router.detect_domain("Write essay") == "writing"
    assert router.detect_domain("Analyze CSV") == "data"
    
    # Test fallback
    assert router.detect_domain("Random query") == "general"
```

### 5. Document Decisions

Log why routing decisions were made:

```python
def route_with_logging(query: str):
    domain = detect_domain(query)
    threshold = get_threshold(domain)
    models = get_models(domain, threshold)
    
    logger.info(
        f"Routing decision: domain={domain}, threshold={threshold}, "
        f"models={[m.name for m in models]}"
    )
    
    return models
```

---

## Examples

See [`examples/custom_cascade.py`](../../examples/custom_cascade.py) for complete working examples of all patterns.

---

**Questions?** Check the [FAQ](faq.md) or [Production Guide](production.md).