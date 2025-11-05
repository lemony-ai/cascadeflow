# Telemetry API Reference

## Overview

The telemetry module provides comprehensive metrics collection, cost tracking, and monitoring capabilities for cascadeflow applications.

## Core Components

### CostCalculator

Stateless calculator for computing costs from cascade executions.

```python
from cascadeflow.telemetry import CostCalculator
from cascadeflow.schema import ModelConfig

calculator = CostCalculator(
    drafter=ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002),
    verifier=ModelConfig(name="gpt-4o", provider="openai", cost=0.03)
)

# Calculate costs from result
breakdown = calculator.calculate(result, query_text="Your query here")
print(f"Total: ${breakdown.total_cost:.6f}")
print(f"Saved: ${breakdown.cost_saved:.6f} ({breakdown.savings_percent:.1f}%)")
```

**Methods:**

- `calculate(result, query_text="")` - Calculate costs from SpeculativeResult
- `calculate_from_tokens(draft_output_tokens, verifier_output_tokens, draft_accepted, query_input_tokens=0)` - Calculate directly from token counts
- `estimate_tokens(text)` - Estimate token count from text (static method)

### CostBreakdown

Data structure containing detailed cost analysis.

**Attributes:**

- `draft_cost` - Cost of draft model execution
- `verifier_cost` - Cost of verifier model execution
- `total_cost` - Total cost (draft + verifier)
- `cost_saved` - Cost savings vs verifier-only (positive = saved, negative = wasted)
- `bigonly_cost` - Baseline cost using only verifier
- `savings_percent` - Percentage savings
- `draft_tokens` - Draft model tokens (input + output)
- `verifier_tokens` - Verifier model tokens (input + output)
- `total_tokens` - Total tokens across both models
- `was_cascaded` - Whether cascade was used
- `draft_accepted` - Whether draft was accepted
- `metadata` - Additional context

**Methods:**

- `to_dict()` - Convert to dictionary for serialization

### MetricsCollector

Aggregates statistics and performance metrics across multiple queries.

```python
from cascadeflow.telemetry import MetricsCollector

collector = MetricsCollector()
collector.set_cost_calculator(calculator)

# Record results
for result in results:
    collector.record(result, routing_strategy='cascade', complexity='medium')

# Get summary
summary = collector.get_summary()
print(f"Total queries: {summary['total_queries']}")
print(f"Total cost: ${summary['total_cost']:.6f}")
print(f"Average latency: {summary['avg_latency']:.2f}ms")
```

### MetricsSnapshot

Point-in-time snapshot of collected metrics.

## Optional Components

### CostTracker

Track costs across queries over time (if available).

```python
from cascadeflow.telemetry import CostTracker

tracker = CostTracker()
tracker.record_query(result, query_text="...", metadata={...})

# Get totals
print(f"Total cost: ${tracker.get_total_cost():.6f}")
print(f"Queries: {tracker.get_query_count()}")
```

### CallbackManager

Event callbacks for monitoring and observability (if available).

## Checking Available Components

```python
from cascadeflow.telemetry import get_telemetry_info

info = get_telemetry_info()
print(f"Version: {info['version']}")
print(f"Available components: {info['components']}")
print(f"Cost tracking: {info['capabilities']['cost_tracking']}")
print(f"Callbacks: {info['capabilities']['callbacks']}")
```

## Cost Calculation Details

### Token Accounting

CostCalculator properly accounts for both input and output tokens:

- **Input tokens**: Query/prompt tokens (shared across models if both called)
- **Output tokens**: Response tokens (specific to each model)

### Draft Accepted

When draft is accepted:
- Only draft model was called
- `verifier_cost = 0`
- `cost_saved` = What verifier would have cost - actual draft cost
- Typically 30-70% savings

### Draft Rejected

When draft is rejected:
- Both models were called
- `total_cost` = draft_cost + verifier_cost
- `cost_saved` = negative (wasted draft cost)
- Important for monitoring cascade effectiveness

## Usage Example

```python
from cascadeflow import CascadeAgent
from cascadeflow.telemetry import CostCalculator, MetricsCollector

# Setup
agent = CascadeAgent(drafter=drafter, verifier=verifier)
calculator = CostCalculator(drafter=drafter, verifier=verifier)
collector = MetricsCollector()
collector.set_cost_calculator(calculator)

# Run queries
queries = ["What is 2+2?", "Explain quantum physics"]

for query in queries:
    result = agent.query(query)

    # Calculate costs
    breakdown = calculator.calculate(result, query_text=query)

    # Track metrics
    collector.record(result, complexity='auto')

    # Log results
    print(f"Query: {query}")
    print(f"Cost: ${breakdown.total_cost:.6f}")
    print(f"Saved: {breakdown.savings_percent:.1f}%")
    print(f"Draft: {'accepted' if breakdown.draft_accepted else 'rejected'}\n")

# Final summary
summary = collector.get_summary()
print(f"\nTotal Cost: ${summary['total_cost']:.6f}")
print(f"Total Savings: ${summary.get('total_saved', 0):.6f}")
print(f"Queries: {summary['total_queries']}")
```

## Related Documentation

- [Cost Tracking Guide](../guides/cost_tracking.md) - Comprehensive cost tracking patterns
- [Production Guide](../guides/production.md) - Deployment with monitoring
- [Quick Start](../guides/quickstart.md) - Getting started with cascadeflow

## API Version

Current telemetry API version: **2.4.0** (October 2025)

---

**Questions?** Open an issue on [GitHub](https://github.com/lemony-ai/cascadeflow/issues).
