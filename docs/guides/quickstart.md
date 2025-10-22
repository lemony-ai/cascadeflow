# CascadeFlow Quick Start Guide

Get started with CascadeFlow in 5 minutes. This guide walks you through the basics of intelligent model cascading.

---

## 📚 Table of Contents

- [What is CascadeFlow?](#what-is-cascadeflow)
- [Installation](#installation)
- [Your First Cascade](#your-first-cascade)
- [How It Works](#how-it-works)
- [Understanding Costs](#understanding-costs)
- [Configuration Options](#configuration-options)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## What is CascadeFlow?

**CascadeFlow** is an intelligent model router that saves you 40-60% on AI costs by automatically using cheaper models when possible and only escalating to expensive models when needed.

### The Problem

Using GPT-4 for everything is expensive:
```
10,000 queries/month × $0.005/query = $50/month
```

But using GPT-3.5 for everything sacrifices quality.

### The Solution

CascadeFlow tries the cheap model first, checks quality, and only uses the expensive model if needed:

```
Simple query → GPT-3.5 ✅ (draft accepted) → Cost: $0.001
Complex query → GPT-3.5 ❌ (draft rejected) → GPT-4 ✅ → Cost: $0.006
```

**Result:** 40-60% savings while maintaining quality!

---

## Installation

### Step 1: Install CascadeFlow

```bash
pip install cascadeflow[all]
```

### Step 2: Set Up API Key

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Or add to your .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Step 3: Verify Installation

```bash
python -c "import cascadeflow; print(cascadeflow.__version__)"
```

---

## Your First Cascade

Create a file called `my_first_cascade.py`:

```python
import asyncio
from cascadeflow import CascadeAgent, ModelConfig

async def main():
    # Configure cascade with two tiers
    agent = CascadeAgent(models=[
        # Tier 1: Cheap model (tries first)
        ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.001,  # per 1K tokens
        ),

        # Tier 2: Expensive model (only if needed)
        ModelConfig(
            name="gpt-4o",
            provider="openai",
            cost=0.005,  # per 1K tokens
        ),
    ])
    # Quality validation uses default cascade-optimized config (0.7 threshold)
    # See "Quality Configuration" section below to customize

    # Try a simple query
    result = await agent.run("What color is the sky?")

    print(f"Response: {result.content}")
    print(f"Model used: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Draft accepted: {result.draft_accepted}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python my_first_cascade.py
```

Expected output:
```
Response: The sky is typically blue during the day.
Model used: gpt-3.5-turbo
Cost: $0.000014
Draft accepted: True
```

**What happened?**
1. Query sent to GPT-3.5 (cheap)
2. Response passed quality check
3. GPT-4 was NOT called (saved money!)

---

## How It Works

### The Cascade Process

```
┌─────────────────┐
│  Your Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Complexity     │ ─────► Simple/Moderate/Complex
│  Detection      │
└────────┬────────┘
         │
         ▼
   ┌─────────────┐
   │ Direct to   │ ───► Very simple → GPT-3.5 only
   │ GPT-3.5?    │ ───► Very complex → GPT-4 directly
   └──────┬──────┘
          │ Maybe cascade
          ▼
┌─────────────────┐
│  GPT-3.5 Draft  │ ────► Generate response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Quality Check   │ ────► Confidence > threshold?
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  PASS      FAIL
    │         │
    │    ┌────────────────┐
    │    │  GPT-4 Verify  │
    │    └────────┬───────┘
    │             │
    └─────────────┘
         │
         ▼
   ┌──────────────┐
   │  Final       │
   │  Response    │
   └──────────────┘
```

### Key Concepts

#### 1. Draft Model (Tier 1)
- **Purpose:** Try to answer with cheap model
- **Cost:** Low (~$0.001 per 1K tokens)
- **Speed:** Fast
- **Quality:** Good for simple queries

#### 2. Verifier Model (Tier 2)
- **Purpose:** Verify draft or handle complex queries
- **Cost:** Higher (~$0.005 per 1K tokens)
- **Speed:** Slower
- **Quality:** Best quality

#### 3. Quality Check
- **Checks:** Confidence score, alignment, coherence
- **Threshold:** Configurable (default: 0.7)
- **Result:** Pass → use draft, Fail → use verifier

#### 4. Draft Accepted vs Rejected

**Draft Accepted** ✅
- Cheap model response is good enough
- Verifier is NOT called
- Cost = cheap model only
- **This is where you save money!**

**Draft Rejected** ❌
- Cheap model response not good enough
- BOTH models are called
- Cost = cheap + expensive
- Quality is ensured

---

## Understanding Costs

### Token-Based Pricing

CascadeFlow uses **actual token-based pricing**, not flat rates:

```python
# Your query
query = "What is Python?"  # ~4 tokens

# Model's response
response = "Python is a programming language..."  # ~50 tokens

# Total tokens
total = 4 (input) + 50 (output) = 54 tokens

# Cost calculation (GPT-3.5 example)
input_cost  = (4 / 1000) × $0.0005 = $0.000002
output_cost = (50 / 1000) × $0.0015 = $0.000075
total_cost  = $0.000077
```

### Cost Breakdown by Scenario

#### Scenario 1: Draft Accepted (Best Case)
```
Query → GPT-3.5 ✅ (accepted)

Costs:
  GPT-3.5: $0.000077
  GPT-4:   $0.000000 (not called)
  ─────────────────
  Total:   $0.000077

Savings: ~85% vs GPT-4 only
```

#### Scenario 2: Draft Rejected (Worst Case)
```
Query → GPT-3.5 ❌ (rejected) → GPT-4 ✅

Costs:
  GPT-3.5: $0.000077
  GPT-4:   $0.000385
  ─────────────────
  Total:   $0.000462

Savings: -20% vs GPT-4 only (paid extra for GPT-3.5)
```

#### Scenario 3: Direct Routing
```
Query → GPT-4 directly (complex query)

Costs:
  GPT-3.5: $0.000000 (not called)
  GPT-4:   $0.000385
  ─────────────────
  Total:   $0.000385

Savings: 0% (same as GPT-4 only)
```

### Expected Savings

Your savings depend on your query mix:

| Query Mix | Draft Acceptance Rate | Expected Savings |
|-----------|----------------------|------------------|
| 80% simple, 20% complex | 80% | 60-70% |
| 50% simple, 50% complex | 50% | 40-50% |
| 20% simple, 80% complex | 20% | 10-20% |

**Rule of thumb:** The more simple queries, the more you save!

---

## Configuration Options

### Model Configuration

```python
ModelConfig(
    name="gpt-3.5-turbo",           # Model name
    provider="openai",              # Provider (openai, anthropic, groq, ollama)
    cost=0.001,                     # Cost per 1K tokens (blended estimate)
    speed_ms=500,                   # Expected latency (optional)
    supports_tools=True,            # Whether model supports tool calling (optional)
)
```

### Agent Configuration

```python
agent = CascadeAgent(
    models=[tier1, tier2],          # List of models (ordered by cost)
    verbose=True,                   # Enable logging
    enable_cascade=True,            # Enable cascade system
)
```

### Quality Configuration

Quality validation is controlled via `QualityConfig`, not individual models:

```python
from cascadeflow import CascadeAgent, ModelConfig, QualityConfig

# Option 1: Use preset configurations
agent = CascadeAgent(
    models=[...],
    quality_config=QualityConfig.for_cascade()     # Optimized for cascading (default)
)

# Option 2: Use other presets
quality_config = QualityConfig.for_production()    # Balanced (0.80 threshold)
quality_config = QualityConfig.for_development()   # Lenient (0.65 threshold)
quality_config = QualityConfig.strict()            # Rigorous (0.95 threshold)

# Option 3: Customize thresholds by complexity
quality_config = QualityConfig(
    confidence_thresholds={
        'trivial': 0.6,    # Very simple queries
        'simple': 0.7,     # Simple queries
        'moderate': 0.75,  # Moderate complexity
        'hard': 0.8,       # Hard queries
        'expert': 0.85     # Expert-level queries
    }
)

agent = CascadeAgent(models=[...], quality_config=quality_config)
```

**Quality Threshold Trade-offs:**
- **Higher threshold (0.8+)** → Better quality, fewer drafts accepted, lower savings
- **Medium threshold (0.7)** → Balanced quality and savings (recommended)
- **Lower threshold (0.6-)** → More drafts accepted, higher savings, occasional quality issues

---

## Best Practices

### 1. Choose the Right Models

**Good Combinations:**
- GPT-3.5 Turbo → GPT-4o (balanced)
- GPT-3.5 Turbo → GPT-4 Turbo (quality-focused)
- Llama 3.1 8B → GPT-4o (maximum savings)

**Avoid:**
- Similar-tier models (GPT-3.5 → GPT-3.5 Turbo)
- Reverse ordering (GPT-4 → GPT-3.5)

### 2. Tune Quality Thresholds

Start with default (0.7) and adjust based on your needs:

```python
# Track acceptance rates
results = []
for query in your_queries:
    result = await agent.run(query)
    results.append(result.draft_accepted)

acceptance_rate = sum(results) / len(results)
print(f"Draft acceptance rate: {acceptance_rate:.1%}")
```

**If acceptance rate is:**
- < 30% → Lower threshold (0.6) or use better draft model
- 30-70% → Perfect! (balanced)
- > 70% → Can raise threshold (0.75) for better quality

### 3. Monitor Costs

```python
# Track costs over time
total_cost = 0
for query in your_queries:
    result = await agent.run(query)
    total_cost += result.total_cost

print(f"Total cost: ${total_cost:.6f}")
print(f"Average per query: ${total_cost/len(your_queries):.6f}")
```

### 4. Handle Failures Gracefully

```python
try:
    result = await agent.run(query)
except Exception as e:
    print(f"Error: {e}")
    # Fallback logic here
```

### 5. Use Appropriate Max Tokens

```python
# Short responses (save cost)
result = await agent.run(query, max_tokens=50)

# Medium responses (balanced)
result = await agent.run(query, max_tokens=150)

# Long responses (quality)
result = await agent.run(query, max_tokens=500)
```

---

## Troubleshooting

### Issue: All Queries Go to Expensive Model

**Symptoms:**
- Draft acceptance rate < 10%
- Costs almost same as GPT-4 only

**Solutions:**
1. Lower quality threshold via QualityConfig:
   ```python
   quality_config = QualityConfig(confidence_thresholds={'moderate': 0.6})
   agent = CascadeAgent(models=[...], quality_config=quality_config)
   ```
2. Use better draft model: Try GPT-3.5 Turbo instead of GPT-3.5
3. Check query complexity: Ensure you have simple queries in your mix

### Issue: Poor Quality Responses

**Symptoms:**
- Draft acceptance rate > 80%
- Responses are incorrect or low quality

**Solutions:**
1. Raise quality threshold via QualityConfig:
   ```python
   quality_config = QualityConfig(confidence_thresholds={'moderate': 0.75})
   agent = CascadeAgent(models=[...], quality_config=quality_config)
   ```
2. Use better verifier model: Try GPT-4o instead of GPT-4
3. Enable verbose mode to see quality scores: `verbose=True`

### Issue: High Latency

**Symptoms:**
- Responses take too long
- Users complaining about wait times

**Solutions:**
1. Use faster models: Groq Llama for draft, GPT-3.5 for verifier
2. Enable streaming: `enable_streaming=True`
3. Reduce max_tokens: `max_tokens=100`
4. Skip cascade for time-critical queries

### Issue: Costs Higher Than Expected

**Symptoms:**
- Savings < 30%
- Many drafts rejected

**Possible Causes:**
1. Query mix too complex (mostly hard queries)
2. Quality threshold too high (rejecting good drafts)
3. Token estimates inaccurate

**Solutions:**
1. Analyze your query complexity distribution
2. Lower quality threshold slightly
3. Use cheaper draft model (Groq Llama, Ollama)

---

## Next Steps

### 1. Run the Basic Example
```bash
python examples/basic_usage.py
```

### 2. Customize for Your Use Case
- Modify models
- Adjust thresholds
- Add your queries

### 3. Read Advanced Guides
- [Streaming Responses](./streaming.md) (coming soon)
- [Tool Calling](./tools.md) (coming soon)
- [Multi-Provider Setup](./multi-provider.md) (coming soon)

### 4. Deploy to Production
- Set up monitoring
- Configure logging
- Implement fallbacks
- Track costs

### 5. Join the Community
- ⭐ Star the [GitHub repo](https://github.com/yourusername/cascadeflow)
- 💬 Join [Discussions](https://github.com/yourusername/cascadeflow/discussions)
- 🐛 Report issues
- 🤝 Contribute examples

---

## Quick Reference

### Common Commands

```bash
# Install
pip install cascadeflow[all]

# Run example
python examples/basic_usage.py

# Check version
python -c "import cascadeflow; print(cascadeflow.__version__)"

# Run with verbose logging
python examples/basic_usage.py --verbose
```

### Code Snippets

**Basic Usage:**
```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig("gpt-3.5-turbo", "openai", cost=0.001),
    ModelConfig("gpt-4o", "openai", cost=0.005),
])

result = await agent.run("Your query here")
```

**Check Result:**
```python
print(f"Response: {result.content}")
print(f"Model: {result.model_used}")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Draft accepted: {result.draft_accepted}")
```

**Track Costs:**
```python
total = sum(r.total_cost for r in results)
print(f"Total: ${total:.6f}")
```

---

## Support

Need help?
- 📖 Read the [FAQ](./faq.md)
- 💬 Ask in [Discussions](https://github.com/yourusername/cascadeflow/discussions)
- 🐛 Report a [bug](https://github.com/yourusername/cascadeflow/issues)
- 📧 Email: support@cascadeflow.ai

---

**Happy Cascading! 🌊**