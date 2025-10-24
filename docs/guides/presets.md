# Preset Configurations Guide

**NEW in v0.1.1** - Get started in seconds with pre-configured model cascades!

## Overview

Presets eliminate configuration complexity by providing ready-to-use model combinations optimized for common use cases. Instead of manually configuring models, quality thresholds, and performance parameters, just import a preset and start saving money.

## Why Use Presets?

### Before (v0.1.0):
```python
from cascadeflow import CascadeAgent, ModelConfig

# 30+ lines of configuration
agent = CascadeAgent(models=[
    ModelConfig(
        name="claude-3-5-haiku-20241022",
        provider="anthropic",
        cost=0.0008,
        speed_ms=2000,
        quality_score=0.85,
        domains=["general"],
    ),
    ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        cost=0.00015,
        speed_ms=2500,
        quality_score=0.80,
        domains=["general"],
    ),
])
```

### After (v0.1.1):
```python
from cascadeflow import CascadeAgent, PRESET_BEST_OVERALL

# 2 lines - same result
agent = CascadeAgent(models=PRESET_BEST_OVERALL)
```

**Result:** 90% less code, 80% faster time to first result!

---

## Available Presets

### 1. PRESET_BEST_OVERALL (Recommended)

**Best for:** Most use cases, production applications, general queries

**Models:**
- Draft: Claude 3.5 Haiku (fast, high quality)
- Verifier: GPT-4o-mini (excellent reasoning)

**Performance:**
- Cost: ~$0.0008/query
- Speed: Fast (~2-3s)
- Quality: Excellent
- API Keys: Anthropic + OpenAI

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_BEST_OVERALL

agent = CascadeAgent(models=PRESET_BEST_OVERALL)
result = await agent.run("Your query here")
```

```typescript
import { CascadeAgent, PRESET_BEST_OVERALL } from '@cascadeflow/core';

const agent = new CascadeAgent(PRESET_BEST_OVERALL);
const result = await agent.run('Your query here');
```

---

### 2. PRESET_ULTRA_FAST

**Best for:** Real-time applications, chatbots, interactive demos, latency-critical systems

**Models:**
- Draft: Groq Llama 3.1 8B (lightning fast)
- Verifier: Groq Llama 3.3 70B (fast + smart)

**Performance:**
- Cost: ~$0.00005/query (90% cheaper than BEST_OVERALL)
- Speed: Ultra-fast (~1-2s) - **5-10x faster than OpenAI**
- Quality: Good
- API Keys: Groq only

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_ULTRA_FAST

agent = CascadeAgent(models=PRESET_ULTRA_FAST)
# Responses in 1-2s instead of 10s!
```

**When to use:**
- User-facing chat applications
- Real-time content generation
- Interactive demos
- When latency matters more than absolute quality

---

### 3. PRESET_ULTRA_CHEAP

**Best for:** High-volume applications, batch processing, cost-sensitive workloads

**Models:**
- Draft: Groq Llama 3.1 8B (free tier, ultra-fast)
- Verifier: GPT-4o-mini (quality assurance)

**Performance:**
- Cost: ~$0.00008/query (88% cheaper than BEST_OVERALL)
- Speed: Very fast (~1-3s)
- Quality: Good
- API Keys: Groq + OpenAI

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_ULTRA_CHEAP

agent = CascadeAgent(models=PRESET_ULTRA_CHEAP)
# Process millions of queries affordably
```

**Cost comparison (1M queries):**
- GPT-4o only: $2,500
- PRESET_ULTRA_CHEAP: $80
- **Savings: $2,420 (97% reduction)**

---

### 4. PRESET_OPENAI_ONLY

**Best for:** Single-provider preference, simplified billing, teams already using OpenAI

**Models:**
- Draft: GPT-4o-mini
- Verifier: GPT-4o

**Performance:**
- Cost: ~$0.0005/query
- Speed: Fast (~2-4s)
- Quality: Excellent
- API Keys: OpenAI only

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_OPENAI_ONLY

agent = CascadeAgent(models=PRESET_OPENAI_ONLY)
# All queries stay within OpenAI ecosystem
```

**Benefits:**
- Single API key management
- Unified billing
- Consistent model behavior
- No multi-provider complexity

---

### 5. PRESET_ANTHROPIC_ONLY

**Best for:** Claude enthusiasts, teams using Anthropic, projects requiring Claude's strengths

**Models:**
- Draft: Claude 3.5 Haiku
- Verifier: Claude Sonnet 4.5

**Performance:**
- Cost: ~$0.002/query
- Speed: Fast (~2-3s)
- Quality: Excellent (best-in-class reasoning)
- API Keys: Anthropic only

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_ANTHROPIC_ONLY

agent = CascadeAgent(models=PRESET_ANTHROPIC_ONLY)
# Claude all the way
```

**When to use:**
- Complex reasoning tasks
- Long-context applications
- Teams preferring Anthropic
- Compliance requirements for specific providers

---

### 6. PRESET_FREE_LOCAL

**Best for:** Privacy-sensitive applications, offline use, development/testing, zero-cost experimentation

**Models:**
- Draft: Ollama Llama 3.1 8B (local)
- Verifier: Ollama Llama 3.1 70B (local)

**Performance:**
- Cost: $0 (completely free, runs locally)
- Speed: Moderate (~3-5s, hardware dependent)
- Quality: Good
- API Keys: None (requires Ollama installation)

**Setup:**
```bash
# Install Ollama
brew install ollama  # macOS
# or download from https://ollama.com

# Pull models
ollama pull llama3.1:8b
ollama pull llama3.1:70b
```

**Usage:**
```python
from cascadeflow import CascadeAgent, PRESET_FREE_LOCAL

agent = CascadeAgent(models=PRESET_FREE_LOCAL)
# 100% free, 100% private
```

**Benefits:**
- Zero API costs
- Complete data privacy
- Works offline
- No rate limits
- Perfect for development

**Drawbacks:**
- Requires local compute
- Slower than cloud providers
- Quality lower than frontier models

---

## Custom Preset Builder

For advanced users who want control without manual configuration:

### Python
```python
from cascadeflow import create_preset

models = create_preset(
    quality='strict',       # 'cost-optimized' | 'balanced' | 'strict'
    performance='fast',     # 'fast' | 'balanced' | 'reliable'
    include_premium=True    # Add premium tier (gpt-4o)
)

agent = CascadeAgent(models=models)
```

### TypeScript
```typescript
import { createPreset } from '@cascadeflow/core';

const config = createPreset({
  quality: 'strict',
  performance: 'fast',
  includePremium: true
});

const agent = new CascadeAgent(config);
```

### Quality Modes

| Mode | Threshold | Behavior | Best For |
|------|-----------|----------|----------|
| `cost-optimized` | 0.6 | Accept more drafts | High-volume, cost-sensitive |
| `balanced` | 0.7 | Default trade-off | Most use cases |
| `strict` | 0.8 | Higher quality bar | Quality-critical applications |

**Example:**
```python
# Accept more drafts for cost savings
models = create_preset(quality='cost-optimized')

# Higher quality, more escalations
models = create_preset(quality='strict')
```

### Performance Modes

| Mode | Providers | Speed | Best For |
|------|-----------|-------|----------|
| `fast` | Groq | Ultra-fast (~1-2s) | Real-time apps |
| `balanced` | Mixed | Fast (~2-3s) | General use |
| `reliable` | OpenAI/Anthropic | Fast (~2-4s) | Production |

**Example:**
```python
# Maximum speed with Groq
models = create_preset(performance='fast')

# Most reliable providers
models = create_preset(performance='reliable')
```

### Include Premium Tier

Add a premium model for complex queries:

```python
# 3-tier cascade: cheap → mid → premium
models = create_preset(
    quality='balanced',
    performance='balanced',
    include_premium=True  # Adds gpt-4o
)
```

**Result:**
- Tier 1: Claude Haiku (draft)
- Tier 2: GPT-4o-mini (verifier)
- Tier 3: GPT-4o (premium)

---

## Comparison Table

| Preset | Cost/Query | Speed | Quality | API Keys | Best For |
|--------|------------|-------|---------|----------|----------|
| BEST_OVERALL | ~$0.0008 | Fast (2-3s) | ⭐⭐⭐⭐⭐ | 2 | Production |
| ULTRA_FAST | ~$0.00005 | Ultra (1-2s) | ⭐⭐⭐⭐ | 1 | Real-time |
| ULTRA_CHEAP | ~$0.00008 | Very Fast (1-3s) | ⭐⭐⭐⭐ | 2 | High volume |
| OPENAI_ONLY | ~$0.0005 | Fast (2-4s) | ⭐⭐⭐⭐⭐ | 1 | Single provider |
| ANTHROPIC_ONLY | ~$0.002 | Fast (2-3s) | ⭐⭐⭐⭐⭐ | 1 | Claude fans |
| FREE_LOCAL | $0 | Moderate (3-5s) | ⭐⭐⭐ | 0 | Privacy/dev |

---

## Decision Guide

### Choose PRESET_BEST_OVERALL if:
- ✅ You're starting out
- ✅ You want excellent quality
- ✅ You have multiple API keys
- ✅ 2-3s latency is acceptable

### Choose PRESET_ULTRA_FAST if:
- ✅ Latency is critical (<2s)
- ✅ You need real-time responses
- ✅ Good quality is sufficient
- ✅ You have Groq API key

### Choose PRESET_ULTRA_CHEAP if:
- ✅ You process millions of queries
- ✅ Cost is the main concern
- ✅ Good quality is sufficient
- ✅ Speed matters (but not ultra-fast)

### Choose PRESET_OPENAI_ONLY if:
- ✅ You prefer single provider
- ✅ You only want OpenAI models
- ✅ Billing simplicity matters
- ✅ Quality is important

### Choose PRESET_ANTHROPIC_ONLY if:
- ✅ You love Claude
- ✅ Complex reasoning is needed
- ✅ Long context is common
- ✅ Single provider is fine

### Choose PRESET_FREE_LOCAL if:
- ✅ Privacy is critical
- ✅ You want zero costs
- ✅ Offline use is needed
- ✅ You have local compute

---

## Migration from v0.1.0

**Old approach:**
```python
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.0025),
])
```

**New approach:**
```python
from cascadeflow import PRESET_OPENAI_ONLY

agent = CascadeAgent(models=PRESET_OPENAI_ONLY)
```

**Result:** Same functionality, 90% less code!

---

## FAQ

### Can I mix presets with custom models?
Yes! Presets return a list of `ModelConfig` objects:
```python
models = PRESET_ULTRA_FAST + [
    ModelConfig(name="custom-model", provider="custom", cost=0.001)
]
```

### Can I modify preset models?
Yes:
```python
models = PRESET_BEST_OVERALL.copy()
models[0].cost = 0.0009  # Adjust cost
```

### Do presets work with all providers?
Yes! Each preset specifies required providers. Make sure you have the API keys set:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk-..."
```

### What if I don't have the required API keys?
Choose a different preset:
- No keys? → `PRESET_FREE_LOCAL` (Ollama)
- Only OpenAI? → `PRESET_OPENAI_ONLY`
- Only Anthropic? → `PRESET_ANTHROPIC_ONLY`
- Only Groq? → `PRESET_ULTRA_FAST`

### How do I know which preset to use?
Start with `PRESET_BEST_OVERALL`. If:
- Too slow → Switch to `PRESET_ULTRA_FAST`
- Too expensive → Switch to `PRESET_ULTRA_CHEAP`
- Need single provider → Use provider-specific preset

---

## Performance Analysis

Based on real testing with 15 queries (see [QUALITY_AND_LATENCY_ANALYSIS.md](../../.analysis/QUALITY_AND_LATENCY_ANALYSIS.md)):

### Key Finding: Provider Choice Matters 20x More Than Cascade Logic

**Latency Breakdown:**
```
Total: 10,390ms (100%)
├─ Provider API: 9,871ms (95%) ← Choose fast providers!
├─ Cascade logic: 312ms (3%)   ← Minimal overhead
└─ Quality check: 208ms (2%)   ← Minimal overhead
```

**Conclusion:** Use Groq for maximum speed (5-10x faster than OpenAI)

### Provider Speed Comparison

| Provider | Model | Avg Latency | Speed vs OpenAI |
|----------|-------|-------------|-----------------|
| Groq | Llama 3.1 8B | ~1-2s | **5-10x faster** |
| Together | Llama models | ~2-3s | **3-5x faster** |
| Ollama | Local | ~3-5s | **2-3x faster** |
| OpenAI | GPT-4o-mini | ~10s | Baseline |

**Recommendation:** For latency-critical applications, use `PRESET_ULTRA_FAST` with Groq.

---

## Next Steps

- **[Performance Guide](./performance.md)** - Deep dive into provider speeds
- **[Production Guide](./production.md)** - Deploy presets in production
- **[Cost Tracking Guide](./cost_tracking.md)** - Monitor preset performance
- **[Main README](../../README.md)** - Back to overview

---

## Support

Questions? Issues?
- 📖 [Documentation](https://github.com/lemony-ai/cascadeflow)
- 💬 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues)
- 🐛 [Report a Bug](https://github.com/lemony-ai/cascadeflow/issues/new)
