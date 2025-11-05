# 💰 cascadeflow Cost Tracking Guide

Complete guide to cost tracking and budget management with cascadeflow.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Core Components](#core-components)
4. [Cost Tracking](#cost-tracking)
5. [Budget Management](#budget-management)
6. [Advanced Usage](#advanced-usage)
7. [Integration Patterns](#integration-patterns)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

cascadeflow provides **comprehensive cost tracking** across queries, models, and providers, with budget enforcement and detailed analytics.

### Key Features

- 💰 **Real-time cost tracking** - Monitor spending per query
- 📊 **Detailed breakdowns** - Per-model, per-provider analytics
- 🚨 **Budget alerts** - Warnings to prevent overspending
- 📈 **Cost history** - Track trends over time
- 🔍 **Cost transparency** - See exactly where money goes
- ⚡ **Zero overhead** - Minimal performance impact

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CascadeAgent                            │
│  (Orchestrates queries, handles routing)                     │
└────────────┬────────────────────────────────┬───────────────┘
             │                                │
             ▼                                ▼
    ┌────────────────┐              ┌─────────────────┐
    │ CostCalculator │              │ MetricsCollector│
    │  (Stateless)   │              │   (Stateful)    │
    │                │              │                 │
    │ • Compute costs│              │ • Track metrics │
    │ • From results │              │ • Aggregations  │
    │ • Input+output │              │ • Statistics    │
    └────────┬───────┘              └────────┬────────┘
             │                                │
             └──────────────┬─────────────────┘
                            ▼
                   ┌─────────────────┐
                   │   CostTracker   │
                   │   (Stateful)    │
                   │                 │
                   │ • Track history │
                   │ • Budget alerts │
                   │ • Analytics     │
                   └─────────────────┘
                            ▲
                            │
                   ┌────────┴────────┐
                   │ Result.metadata │
                   │                 │
                   │ • Contains costs│
                   │ • Model info    │
                   │ • Token counts  │
                   └─────────────────┘
```

### Requirements

```bash
# Basic installation
pip install cascadeflow

# With all features
pip install cascadeflow[all]
```

---

## Quick Start

### Basic Cost Tracking (5 Lines)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.telemetry import CostTracker

# Setup tracker with budget
tracker = CostTracker(budget_limit=1.0, warn_threshold=0.8)

# Setup agent
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
])

# Run query
result = await agent.run("What is Python?")

# Extract costs safely from result
total_cost = getattr(result, 'total_cost', 0) or 0
total_tokens = result.metadata.get('total_tokens', 0) or 0

# Track cost
tracker.add_cost(
    model=result.metadata.get('draft_model') or result.model_used,
    provider="openai",
    tokens=total_tokens,
    cost=total_cost
)

# Show summary
tracker.print_summary()
```

### With Budget Alerts

```python
# Setup with strict budget
tracker = CostTracker(
    budget_limit=0.50,      # $0.50 limit
    warn_threshold=0.75,    # Warn at 75%
    verbose=True            # Show logs
)

# Run multiple queries
for i, query in enumerate(queries):
    result = await agent.run(query)
    
    # Extract costs safely
    total_cost = getattr(result, 'total_cost', 0) or 0
    total_tokens = result.metadata.get('total_tokens', 0) or 0
    
    # Check budget status
    summary = tracker.get_summary()
    if summary.get('budget_used_pct', 0) >= 100:
        print("❌ Budget exceeded, stopping")
        break
    
    tracker.add_cost(
        model=result.metadata.get('draft_model') or result.model_used,
        provider="openai",
        tokens=total_tokens,
        cost=total_cost,
        query_id=f"query-{i}"
    )
```

---

## Core Components

### CostCalculator (Stateless)

**Purpose**: Calculate costs from SpeculativeResult objects  
**Location**: `cascadeflow.telemetry.cost_calculator`

```python
from cascadeflow.telemetry import CostCalculator, CostBreakdown

# Initialize with models
calculator = CostCalculator(
    drafter=ModelConfig(name='gpt-4o-mini', cost=0.00015),
    verifier=ModelConfig(name='gpt-4o', cost=0.00625),
    verbose=True
)

# Calculate from SpeculativeResult
breakdown: CostBreakdown = calculator.calculate(
    spec_result,
    query_text="What is 2+2?"  # For input token counting
)

# Access breakdown
print(f"Total: ${breakdown.total_cost:.6f}")
print(f"Draft: ${breakdown.draft_cost:.6f}")
print(f"Verifier: ${breakdown.verifier_cost:.6f}")
print(f"Saved: ${breakdown.cost_saved:.6f}")
print(f"Savings: {breakdown.savings_percent:.1f}%")
```

**Key Features:**
- Stateless calculation (no state persistence)
- Input + output token counting
- Proper cost aggregation (draft + verifier)
- Cost savings calculation vs verifier-only
- Detailed breakdowns with CostBreakdown dataclass

**When to Use:**
- When you need detailed cost breakdowns
- When calculating savings vs verifier-only approach
- When you have SpeculativeResult objects (internal agent results)

**Note**: For basic tracking with regular CascadeAgent results, you can extract costs directly from `result.metadata` without needing CostCalculator.

### Result Metadata (Cost Information)

**Purpose**: Contains all cost and diagnostic information  
**Location**: `result.metadata` dictionary on CascadeAgent results

```python
result = await agent.run(query)

# Core attributes
total_cost = getattr(result, 'total_cost', 0)
model_used = getattr(result, 'model_used', 'unknown')

# Metadata dictionary contains detailed information
draft_cost = result.metadata.get('draft_cost', 0)
verifier_cost = result.metadata.get('verifier_cost', 0)
draft_tokens = result.metadata.get('draft_tokens', 0)
verifier_tokens = result.metadata.get('verifier_tokens', 0)
total_tokens = result.metadata.get('total_tokens', 0)
draft_model = result.metadata.get('draft_model')
verifier_model = result.metadata.get('verifier_model')
cascaded = result.metadata.get('cascaded', False)
draft_accepted = result.metadata.get('draft_accepted', False)
```

**Key Features:**
- All cost data in one place
- Draft and verifier breakdowns
- Token counts for analysis
- Cascade state information

**When to Use:**
- For basic cost tracking (most common use case)
- When working with CascadeAgent.run() results
- When you don't need savings calculations

### CostTracker (Stateful)

**Purpose**: Track costs over time  
**Location**: `cascadeflow.telemetry.cost_tracker`

```python
from cascadeflow.telemetry import CostTracker

# Initialize tracker
tracker = CostTracker(
    budget_limit=10.0,      # Optional budget
    warn_threshold=0.8,     # Warn at 80%
    verbose=True
)

# Add costs
tracker.add_cost(
    model='gpt-4o-mini',
    provider='openai',
    tokens=100,
    cost=0.000015,
    query_id='query-1',
    metadata={'complexity': 'simple'}
)

# Get summary
summary = tracker.get_summary()
print(f"Total: ${summary['total_cost']:.6f}")
print(f"By model: {summary['by_model']}")
print(f"By provider: {summary['by_provider']}")
```

**Key Features:**
- Per-model cost tracking
- Per-provider cost tracking
- Budget alerts (warning only, no hard stops)
- Cost history with metadata
- Query-level tracking

### MetricsCollector (Comprehensive)

**Purpose**: Aggregate all statistics  
**Location**: `cascadeflow.telemetry.collector`

```python
from cascadeflow.telemetry import MetricsCollector

# Initialize collector
metrics = MetricsCollector()

# Record results
metrics.record(
    result,
    routing_strategy='cascade',
    complexity='simple'
)

# Get comprehensive summary
summary = metrics.get_summary()
print(f"Total queries: {summary['total_queries']}")
print(f"Cascade used: {summary['cascade_used']}")  # ✅ Correct key
print(f"Cascade rate: {summary['cascade_rate']:.1f}%")  # Already a %
print(f"Avg latency: {summary['avg_latency_ms']:.0f}ms")
print(f"Total cost: ${summary['total_cost']:.6f}")
```

**Key Features:**
- Tracks ALL metrics (not just costs)
- Routing strategy analysis
- Latency tracking
- Token usage
- Cascade statistics

**Important Note**: Use `cascade_used` not `cascaded_queries` for the summary key.

---

## Cost Tracking

### Basic Tracking

```python
from cascadeflow.telemetry import CostTracker

# Create tracker
tracker = CostTracker(verbose=True)

# Run query and track cost
result = await agent.run("What is Python?")

# Safe extraction
total_cost = getattr(result, 'total_cost', 0) or 0
total_tokens = result.metadata.get('total_tokens', 0) or 0

# If no tokens, estimate from content
if total_tokens == 0:
    content = getattr(result, 'content', '')
    total_tokens = int(len(content.split()) * 1.3)  # Rough estimate

tracker.add_cost(
    model=result.metadata.get('draft_model') or result.model_used,
    provider="openai",
    tokens=total_tokens,
    cost=total_cost
)

# View totals
print(f"Total cost: ${tracker.total_cost:.6f}")
```

### Tracking Draft + Verifier Separately

```python
# Extract metadata safely
draft_cost = result.metadata.get('draft_cost', 0)
verifier_cost = result.metadata.get('verifier_cost', 0)
draft_tokens = result.metadata.get('draft_tokens', 0)
verifier_tokens = result.metadata.get('verifier_tokens', 0)

# Track draft cost if used
if draft_cost > 0:
    tracker.add_cost(
        model=result.metadata.get('draft_model') or agent.models[0].name,
        provider=agent.models[0].provider,
        tokens=draft_tokens if draft_tokens > 0 else int(total_tokens * 0.5),
        cost=draft_cost,
        query_id="query-1",
        metadata={'role': 'draft'}
    )

# Track verifier cost if used (if cascaded)
if verifier_cost > 0:
    tracker.add_cost(
        model=result.metadata.get('verifier_model') or agent.models[-1].name,
        provider=agent.models[-1].provider if len(agent.models) > 1 else agent.models[0].provider,
        tokens=verifier_tokens if verifier_tokens > 0 else int(total_tokens * 0.5),
        cost=verifier_cost,
        query_id="query-1",
        metadata={'role': 'verifier'}
    )
```

### Understanding Cascade States

```python
# Check if cascading occurred
cascaded = result.metadata.get('cascaded', False) or getattr(result, 'cascaded', False)
draft_accepted = result.metadata.get('draft_accepted', False)

if cascaded:
    if draft_accepted:
        # Only cheap model used (draft was good enough)
        print("✅ Draft accepted - cost optimized!")
        actual_model = result.metadata.get('draft_model') or agent.models[0].name
    else:
        # Both models used (draft rejected for quality)
        print("🔄 Draft rejected - quality ensured")
        actual_model = result.metadata.get('verifier_model') or agent.models[-1].name
else:
    # Direct routing - only one model
    print("➡️ Direct routing")
    actual_model = result.model_used
```

### Tracking with Metadata

```python
tracker.add_cost(
    model='gpt-4o',
    provider='openai',
    tokens=500,
    cost=0.003125,
    query_id='query-42',
    metadata={
        'user_id': 'user-123',
        'session_id': 'sess-456',
        'complexity': 'complex',
        'cascaded': True,
        'draft_accepted': False,
        'timestamp': '2025-10-21T10:30:00',
        'query': query[:50]  # First 50 chars
    }
)
```

### Cost History

```python
# Get recent entries
recent = tracker.get_recent_entries(n=10)
for entry in recent:
    print(f"{entry.timestamp.strftime('%H:%M:%S')} | "
          f"{entry.model:15s} | "
          f"${entry.cost:.6f} | "
          f"{entry.tokens:,} tokens")

# Get entries by model (check for partial matches)
mini_entries = [e for e in tracker.entries if 'gpt-4o-mini' in e.model]
gpt4_entries = [e for e in tracker.entries if e.model == 'gpt-4o']

print(f"GPT-4o-mini queries: {len(mini_entries)}")
print(f"GPT-4o queries: {len(gpt4_entries)}")

# Calculate totals
mini_total = sum(e.cost for e in mini_entries)
gpt4_total = sum(e.cost for e in gpt4_entries)
print(f"GPT-4o-mini total: ${mini_total:.6f}")
print(f"GPT-4o total: ${gpt4_total:.6f}")
```

---

## Budget Management

### Setting Budgets

```python
# Development budget
dev_tracker = CostTracker(
    budget_limit=1.0,       # $1 for testing
    warn_threshold=0.8,     # Warn at $0.80
    verbose=True
)

# Production budget
prod_tracker = CostTracker(
    budget_limit=100.0,     # $100/day
    warn_threshold=0.9,     # Warn at $90
    verbose=True
)
```

### Budget Alerts

```python
# Check budget before expensive operations
summary = tracker.get_summary()
budget_pct = summary.get('budget_used_pct', 0)

if budget_pct >= 100:
    print("❌ Budget exceeded!")
    # Stop processing or alert admin
    return
elif budget_pct >= 80:
    print(f"⚠️ Warning: {budget_pct:.1f}% of budget used")
    # Consider switching to cheaper models

# Continue with normal operations
result = await agent.run(query)
```

### Budget Monitoring

```python
async def monitor_budget(tracker, interval=10):
    """Monitor budget every N queries."""
    query_count = 0
    
    for query in queries:
        result = await agent.run(query)
        
        # Extract and track costs
        total_cost = getattr(result, 'total_cost', 0) or 0
        total_tokens = result.metadata.get('total_tokens', 0) or 0
        
        tracker.add_cost(
            model=result.metadata.get('draft_model') or result.model_used,
            provider="openai",
            tokens=total_tokens,
            cost=total_cost
        )
        
        query_count += 1
        
        # Check every N queries
        if query_count % interval == 0:
            summary = tracker.get_summary()
            pct = summary.get('budget_used_pct', 0)
            remaining = summary.get('budget_remaining', 0)
            
            print(f"\n📊 Budget Check (after {query_count} queries):")
            print(f"  Used: {pct:.1f}%")
            print(f"  Remaining: ${remaining:.6f}")
            
            if pct >= 90:
                print("  ⚠️ Approaching budget limit!")
```

### Per-User Budgets

```python
class UserBudgetTracker:
    """Track budgets per user."""
    
    def __init__(self, default_limit=10.0):
        self.trackers = {}
        self.default_limit = default_limit
    
    def get_tracker(self, user_id):
        """Get or create tracker for user."""
        if user_id not in self.trackers:
            self.trackers[user_id] = CostTracker(
                budget_limit=self.default_limit,
                warn_threshold=0.8
            )
        return self.trackers[user_id]
    
    async def run_query(self, user_id, agent, query):
        """Run query with user budget tracking."""
        tracker = self.get_tracker(user_id)
        
        # Check budget first
        summary = tracker.get_summary()
        if summary.get('budget_used_pct', 0) >= 100:
            raise BudgetExceededError(f"User {user_id} exceeded budget")
        
        # Run query
        result = await agent.run(query)
        
        # Track cost
        total_cost = getattr(result, 'total_cost', 0) or 0
        total_tokens = result.metadata.get('total_tokens', 0) or 0
        
        tracker.add_cost(
            model=result.metadata.get('draft_model') or result.model_used,
            provider="openai",
            tokens=total_tokens,
            cost=total_cost,
            metadata={'user_id': user_id}
        )
        
        return result

# Usage
budget_tracker = UserBudgetTracker(default_limit=5.0)
result = await budget_tracker.run_query('user-123', agent, query)
```

---

## Advanced Usage

### Cost Analysis Dashboard

```python
def print_cost_dashboard(tracker, metrics):
    """Print comprehensive cost dashboard."""
    summary = tracker.get_summary()
    metrics_summary = metrics.get_summary()
    
    print("="*60)
    print("COST DASHBOARD")
    print("="*60)
    
    # Overview
    print(f"\nTotal Cost: ${summary['total_cost']:.6f}")
    print(f"Total Queries: {metrics_summary['total_queries']}")
    print(f"Avg Cost/Query: ${summary['total_cost'] / max(metrics_summary['total_queries'], 1):.6f}")
    
    # Model breakdown
    print("\nModel Breakdown:")
    for model, cost in sorted(
        summary['by_model'].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        pct = (cost / summary['total_cost']) * 100
        entries = len([e for e in tracker.entries if model in e.model])
        avg_per_query = cost / entries if entries > 0 else 0
        
        print(f"  {model}:")
        print(f"    Total: ${cost:.6f} ({pct:.1f}%)")
        print(f"    Queries: {entries}")
        print(f"    Avg/query: ${avg_per_query:.6f}")
    
    # Cascade analysis
    print(f"\nCascade Analysis:")
    print(f"  Cascaded: {metrics_summary['cascade_used']}")
    print(f"  Rate: {metrics_summary['cascade_rate']:.1f}%")
    print(f"  Avg Latency: {metrics_summary['avg_latency_ms']:.0f}ms")
    
    # Budget status
    if 'budget_limit' in summary:
        print(f"\nBudget Status:")
        print(f"  Limit: ${summary['budget_limit']:.2f}")
        print(f"  Used: {summary['budget_used_pct']:.1f}%")
        print(f"  Remaining: ${summary['budget_remaining']:.6f}")
    
    print("="*60 + "\n")
```

### Cost Optimization Analysis

```python
def analyze_cost_optimization(tracker, metrics):
    """Analyze potential cost savings."""
    summary = tracker.get_summary()
    metrics_summary = metrics.get_summary()
    
    total_queries = metrics_summary['total_queries']
    cascade_used = metrics_summary['cascade_used']
    cascade_rate = metrics_summary['cascade_rate']
    
    print("COST OPTIMIZATION ANALYSIS")
    print("="*60)
    
    # Calculate what we spent
    actual_cost = summary['total_cost']
    
    # Calculate if we used only cheap model
    mini_entries = [e for e in tracker.entries if 'gpt-4o-mini' in e.model]
    avg_mini_cost = sum(e.cost for e in mini_entries) / len(mini_entries) if mini_entries else 0.000015
    cheap_only_cost = total_queries * avg_mini_cost
    
    # Calculate if we used only expensive model
    gpt4_entries = [e for e in tracker.entries if e.model == 'gpt-4o']
    avg_gpt4_cost = sum(e.cost for e in gpt4_entries) / len(gpt4_entries) if gpt4_entries else 0.003
    expensive_only_cost = total_queries * avg_gpt4_cost
    
    print(f"\nScenario Analysis:")
    print(f"  All cheap (gpt-4o-mini): ${cheap_only_cost:.6f}")
    print(f"  All expensive (gpt-4o):  ${expensive_only_cost:.6f}")
    print(f"  Actual (cascade):        ${actual_cost:.6f}")
    
    if expensive_only_cost > actual_cost:
        savings = expensive_only_cost - actual_cost
        savings_pct = (savings / expensive_only_cost) * 100
        print(f"\n✅ Savings vs all-expensive: ${savings:.6f} ({savings_pct:.1f}%)")
    
    print(f"\nCascade Efficiency:")
    print(f"  Cascade rate: {cascade_rate:.1f}%")
    print(f"  Queries saved: {total_queries - cascade_used}")
    
    # Recommendations
    print(f"\nRecommendations:")
    if cascade_rate > 50:
        print("  ⚠️ High cascade rate - consider:")
        print("    • Adjusting quality thresholds")
        print("    • Using better draft model")
        print("    • Pre-filtering simple queries")
    elif cascade_rate < 10:
        print("  ✅ Low cascade rate - good optimization!")
        print("    • Most queries handled by cheap model")
        print("    • Consider raising quality bar if needed")
    
    print("="*60 + "\n")
```

---

## Integration Patterns

### Pattern 1: Automatic Tracking

```python
class TrackedAgent:
    """Agent with automatic cost tracking."""
    
    def __init__(self, agent, tracker):
        self.agent = agent
        self.tracker = tracker
    
    async def run(self, query, **kwargs):
        """Run query with automatic cost tracking."""
        result = await self.agent.run(query, **kwargs)
        
        # Safely extract costs
        total_cost = getattr(result, 'total_cost', 0) or 0
        total_tokens = result.metadata.get('total_tokens', 0) or 0
        
        # Automatically track costs
        self.tracker.add_cost(
            model=result.metadata.get('draft_model') or result.model_used,
            provider=self.agent.models[0].provider,
            tokens=total_tokens,
            cost=total_cost,
            metadata={
                'cascaded': result.metadata.get('cascaded', False),
                'draft_accepted': result.metadata.get('draft_accepted', False)
            }
        )
        
        return result

# Usage
tracked_agent = TrackedAgent(agent, tracker)
result = await tracked_agent.run("Query")  # Auto-tracked!
```

### Pattern 2: Context Manager

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def track_costs(tracker, **metadata):
    """Context manager for cost tracking."""
    start_cost = tracker.total_cost
    start_count = len(tracker.entries)
    
    yield tracker
    
    # Calculate costs incurred in this context
    cost_delta = tracker.total_cost - start_cost
    queries_added = len(tracker.entries) - start_count
    
    print(f"\nContext Summary:")
    print(f"  Cost: ${cost_delta:.6f}")
    print(f"  Queries: {queries_added}")
    if queries_added > 0:
        print(f"  Avg: ${cost_delta / queries_added:.6f}/query")

# Usage
async with track_costs(tracker, session='abc') as t:
    result1 = await agent.run("Query 1")
    total_cost = getattr(result1, 'total_cost', 0) or 0
    total_tokens = result1.metadata.get('total_tokens', 0) or 0
    t.add_cost(
        model=result1.metadata.get('draft_model') or result1.model_used,
        provider="openai",
        tokens=total_tokens,
        cost=total_cost
    )
    
    result2 = await agent.run("Query 2")
    total_cost = getattr(result2, 'total_cost', 0) or 0
    total_tokens = result2.metadata.get('total_tokens', 0) or 0
    t.add_cost(
        model=result2.metadata.get('draft_model') or result2.model_used,
        provider="openai",
        tokens=total_tokens,
        cost=total_cost
    )
# Prints: Context Summary: Cost: $0.003456, Queries: 2
```

### Pattern 3: Batch Processing

```python
async def process_batch_with_tracking(queries, agent, tracker):
    """Process queries in batch with cost tracking."""
    results = []
    
    for i, query in enumerate(queries):
        # Check budget
        summary = tracker.get_summary()
        if summary.get('budget_used_pct', 0) >= 100:
            print(f"⚠️ Budget exceeded after {i} queries")
            break
        
        # Run query
        result = await agent.run(query, max_tokens=150)
        results.append(result)
        
        # Extract and track costs
        total_cost = getattr(result, 'total_cost', 0) or 0
        total_tokens = result.metadata.get('total_tokens', 0) or 0
        
        tracker.add_cost(
            model=result.metadata.get('draft_model') or result.model_used,
            provider="openai",
            tokens=total_tokens,
            cost=total_cost,
            query_id=f"batch-{i}",
            metadata={'query': query[:50]}
        )
        
        # Progress update every 10 queries
        if (i + 1) % 10 == 0:
            summary = tracker.get_summary()
            print(f"Progress: {i+1}/{len(queries)} | "
                  f"Cost: ${summary['total_cost']:.6f} | "
                  f"Budget: {summary.get('budget_used_pct', 0):.1f}%")
    
    return results
```

---

## Best Practices

### 1. Always Use Safe Extraction

```python
# ✅ GOOD: Safe extraction with fallbacks
total_cost = getattr(result, 'total_cost', 0) or 0
total_tokens = result.metadata.get('total_tokens', 0) or 0

# Handle missing tokens
if total_tokens == 0:
    content = getattr(result, 'content', '')
    total_tokens = int(len(content.split()) * 1.3)

# ❌ BAD: Direct access (will fail if attribute missing)
total_cost = result.total_cost
total_tokens = result.total_tokens
```

### 2. Always Set Budget Limits

```python
# ✅ GOOD: Set reasonable budget
tracker = CostTracker(budget_limit=10.0, warn_threshold=0.8)

# ❌ BAD: No budget protection
tracker = CostTracker()  # Could spend unlimited money
```

### 3. Track with Rich Metadata

```python
# ✅ GOOD: Include context for better analysis
tracker.add_cost(
    model=result.metadata.get('draft_model') or result.model_used,
    provider='openai',
    tokens=total_tokens,
    cost=total_cost,
    query_id=f'query-{i}',
    metadata={
        'query': query[:50],
        'user_id': 'user-123',
        'cascaded': result.metadata.get('cascaded', False),
        'draft_accepted': result.metadata.get('draft_accepted', False),
        'complexity': 'simple'
    }
)

# ❌ WORSE: Minimal tracking
tracker.add_cost(model='gpt-4o', cost=0.003)  # Hard to analyze later
```

### 4. Monitor Budget Regularly

```python
# ✅ GOOD: Check budget periodically
async def process_with_monitoring(queries):
    for i, query in enumerate(queries):
        result = await agent.run(query)
        
        # Extract and track
        total_cost = getattr(result, 'total_cost', 0) or 0
        total_tokens = result.metadata.get('total_tokens', 0) or 0
        tracker.add_cost(
            model=result.metadata.get('draft_model') or result.model_used,
            provider="openai",
            tokens=total_tokens,
            cost=total_cost
        )
        
        # Check every 10 queries
        if (i + 1) % 10 == 0:
            summary = tracker.get_summary()
            pct = summary.get('budget_used_pct', 0)
            if pct >= 80:
                print(f"⚠️ Budget warning: {pct:.1f}% used")

# ❌ BAD: Never check budget
for query in queries:
    result = await agent.run(query)
    # ... could exceed budget without noticing
```

### 5. Use Both CostTracker and MetricsCollector

```python
# ✅ GOOD: Complete visibility
tracker = CostTracker(budget_limit=1.0)
metrics = MetricsCollector()

result = await agent.run(query)

# Extract safely
total_cost = getattr(result, 'total_cost', 0) or 0
total_tokens = result.metadata.get('total_tokens', 0) or 0
cascaded = result.metadata.get('cascaded', False)

# Track in both
tracker.add_cost(
    model=result.metadata.get('draft_model') or result.model_used,
    provider="openai",
    tokens=total_tokens,
    cost=total_cost
)

metrics.record(
    result,
    routing_strategy='cascade' if cascaded else 'direct'
)

# ❌ WORSE: Only track costs
tracker.add_cost(...)  # Missing latency, cascade rate, etc.
```

---

## Troubleshooting

### Issue: Missing Cost Information

**Problem:**
```python
result = await agent.run(query)
total_cost = getattr(result, 'total_cost', 0)
print(total_cost)  # 0 or None
```

**Solution:**
```python
# Try multiple sources for cost
total_cost = getattr(result, 'total_cost', 0) or \
             result.metadata.get('total_cost', 0) or \
             (result.metadata.get('draft_cost', 0) + result.metadata.get('verifier_cost', 0))

# If still 0, check model configuration
if total_cost == 0:
    print("⚠️ Models may not have cost configured")
    # Verify ModelConfig has cost parameter set
    for model in agent.models:
        print(f"{model.name}: cost={model.cost}")
```

### Issue: Missing Token Counts

**Problem:**
```python
total_tokens = result.metadata.get('total_tokens', 0)
print(total_tokens)  # 0
```

**Solution:**
```python
# Try multiple metadata keys
total_tokens = result.metadata.get('total_tokens', 0) or \
               (result.metadata.get('draft_tokens', 0) + result.metadata.get('verifier_tokens', 0)) or \
               getattr(result, 'total_tokens', 0)

# Estimate if still missing
if total_tokens == 0:
    content = getattr(result, 'content', '')
    total_tokens = int(len(content.split()) * 1.3)  # Rough estimate
    print(f"ℹ️ Estimated {total_tokens} tokens from content")
```

### Issue: MetricsCollector KeyError

**Problem:**
```python
summary = metrics.get_summary()
print(summary['cascaded_queries'])  # KeyError!
```

**Solution:**
```python
# Use correct key name
summary = metrics.get_summary()

# ✅ Correct keys:
cascade_used = summary.get('cascade_used', 0)      # Number of cascaded queries
cascade_rate = summary.get('cascade_rate', 0)      # Percentage (0-100)
total_queries = summary.get('total_queries', 0)
avg_latency = summary.get('avg_latency_ms', 0)
total_cost = summary.get('total_cost', 0)

# ❌ Wrong keys (don't exist):
# summary['cascaded_queries']  # Wrong!

# Always use .get() with defaults for safety
print(f"Cascade rate: {summary.get('cascade_rate', 0):.1f}%")
```

### Issue: Budget Warnings Not Showing

**Problem:**
```python
tracker = CostTracker(budget_limit=1.0, warn_threshold=0.8)
# Spend $0.90 without warnings
```

**Solution:**
```python
# Enable verbose mode
tracker = CostTracker(
    budget_limit=1.0,
    warn_threshold=0.8,
    verbose=True  # ← Enable this
)

# Or manually check budget
summary = tracker.get_summary()
if 'budget_used_pct' in summary:
    pct = summary['budget_used_pct']
    if pct >= 80:
        print(f"⚠️ Budget warning: {pct:.1f}% used")
    if pct >= 100:
        print(f"❌ Budget exceeded!")
```

### Issue: Cascade State Confusion

**Problem:**
```python
# Not sure if query was cascaded or which model was used
```

**Solution:**
```python
cascaded = result.metadata.get('cascaded', False) or getattr(result, 'cascaded', False)
draft_accepted = result.metadata.get('draft_accepted', False)

if cascaded:
    if draft_accepted:
        # Only draft model was used (cheap!)
        actual_model = result.metadata.get('draft_model') or agent.models[0].name
        print(f"✅ Draft accepted - used {actual_model}")
        print("   Cost optimized!")
    else:
        # Both models used (expensive but quality assured)
        actual_model = result.metadata.get('verifier_model') or agent.models[-1].name
        print(f"🔄 Draft rejected - used {actual_model}")
        print("   Quality ensured")
else:
    # Direct routing - only one model
    actual_model = result.model_used
    print(f"➡️ Direct routing - used {actual_model}")
```

### Issue: Costs Don't Match Expectations

**Problem:**
```python
result = await agent.run("Simple query")
print(result.total_cost)  # $0.003000 - Expected: ~$0.000150
```

**Solution:**
```python
# Check cascade details
cascaded = result.metadata.get('cascaded', False)
draft_accepted = result.metadata.get('draft_accepted', False)

if cascaded and not draft_accepted:
    print("⚠️ Query was cascaded to expensive model")
    print(f"   Draft cost: ${result.metadata.get('draft_cost', 0):.6f}")
    print(f"   Verifier cost: ${result.metadata.get('verifier_cost', 0):.6f}")
    print("   Reason: Draft quality too low")
    print("   Tip: Adjust quality thresholds if needed")
else:
    print("✅ Used cheap model only")
```

---

## Examples

### Complete Working Example

See [`examples/cost_tracking.py`](../../examples/cost_tracking.py) for a full implementation with:
- Safe metadata extraction
- CostTracker initialization
- Budget management
- Multiple queries with different complexities
- Detailed cost analysis
- MetricsCollector integration
- Cascade state handling

### Quick Reference

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.telemetry import CostTracker, MetricsCollector

# Setup
tracker = CostTracker(budget_limit=1.0, warn_threshold=0.8, verbose=True)
metrics = MetricsCollector()
agent = CascadeAgent(models=[
    ModelConfig("gpt-4o-mini", "openai", cost=0.00015),
    ModelConfig("gpt-4o", "openai", cost=0.00625),
])

# Execute and track
result = await agent.run("What is Python?", max_tokens=150)

# Extract safely
total_cost = getattr(result, 'total_cost', 0) or 0
total_tokens = result.metadata.get('total_tokens', 0) or 0
cascaded = result.metadata.get('cascaded', False)

# If no tokens, estimate
if total_tokens == 0:
    content = getattr(result, 'content', '')
    total_tokens = int(len(content.split()) * 1.3)

# Track
tracker.add_cost(
    model=result.metadata.get('draft_model') or result.model_used,
    provider="openai",
    tokens=total_tokens,
    cost=total_cost,
    metadata={'cascaded': cascaded}
)

metrics.record(
    result,
    routing_strategy='cascade' if cascaded else 'direct'
)

# Analyze
tracker.print_summary()
metrics_summary = metrics.get_summary()
print(f"Total queries: {metrics_summary['total_queries']}")
print(f"Cascade rate: {metrics_summary['cascade_rate']:.1f}%")
```

---

## Related Documentation

- 📖 [Quick Start Guide](quickstart.md) - Getting started with cascadeflow
- 📖 [Streaming Guide](streaming.md) - Real-time streaming
- 📖 [Production Guide](production.md) - Deployment patterns
- 📖 [API Reference](../api/telemetry.md) - Detailed API docs
- 📚 [Examples](../../examples/) - Working code examples

---

**Questions or issues?** Open an issue on GitHub or check the examples directory for working code.