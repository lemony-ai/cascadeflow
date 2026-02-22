# cascadeflow TypeScript Examples

**Complete collection of examples** demonstrating cascadeflow from basics to production deployment.

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Install cascadeflow
npm install @cascadeflow/core

# 2. Set your API key
export OPENAI_API_KEY="sk-..."

# 3. Run your first example
cd packages/core/examples/nodejs
npx tsx basic-usage.ts
```

**That's it!** You'll see cascading in action with cost savings.

---

## 🎯 Quick Reference - Find What You Need

| Example | What It Does | Complexity | Time | Best For |
|---------|--------------|------------|------|----------|
| **basic-usage.ts** | Learn cascading basics | ⭐ Easy | 5 min | First-time users |
| **tool-calling.ts** | Function calling | ⭐⭐ Medium | 15 min | Agent builders |
| **cost-tracking.ts** | Budget management | ⭐⭐ Medium | 15 min | Cost optimization |
| **multi-provider.ts** | Mix AI providers | ⭐⭐ Medium | 10 min | Multi-cloud |
| **reasoning-models.ts** | o1, o3, Claude 3.7, DeepSeek-R1 | ⭐⭐ Medium | 10 min | Complex reasoning |
| **semantic-quality.ts** | ML-based quality validation | ⭐⭐⭐ Advanced | 15 min | Quality assurance |
| **production-patterns.ts** | Enterprise patterns | ⭐⭐⭐ Advanced | 30 min | Production deployment |

**💡 Tip:** Start with `basic-usage.ts`, then explore based on your use case!

---

## 🔍 Find by Feature

**I want to...**
- **Use tools/functions?** → `tool-calling.ts`
- **Track costs?** → `cost-tracking.ts`
- **Enforce budgets?** → `cost-tracking.ts`, `production-patterns.ts`
- **Use multiple providers?** → `multi-provider.ts`
- **Deploy to production?** → `production-patterns.ts`
- **Use reasoning models?** → `reasoning-models.ts`
- **Validate quality with ML?** → `semantic-quality.ts`
- **Access DeepSeek/Gemini/Azure?** → Python examples (LiteLLM integration)

---

## 📋 Table of Contents

- [🌟 Core Examples](#-core-examples-4-examples---start-here) - Basic usage, tools, multi-provider, reasoning
- [💰 Cost Management](#-cost-management-1-example) - Budget tracking
- [🤖 Quality & Validation](#-quality--validation-1-example) - Semantic quality with ML
- [🏭 Production](#-production-1-example) - Enterprise patterns

---

## 📚 Examples by Category

<details open>
<summary><h3>🌟 Core Examples (4 examples) - Start Here</h3></summary>

Perfect for learning cascadeflow basics. Start with these!

#### 1. Basic Usage ⭐ **START HERE**
**File:** [`nodejs/basic-usage.ts`](nodejs/basic-usage.ts)
**Time:** 5 minutes
**What you'll learn:**
- How cascading works (cheap model → expensive model)
- Automatic quality-based routing
- Cost tracking and savings
- When drafts are accepted vs rejected

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
cd packages/core/examples/nodejs
npx tsx basic-usage.ts
```

**Expected output:**
```
Query 1/8: What color is the sky?
   💚 Model: gpt-4o-mini only
   💰 Cost: $0.000081
   ✅ Draft Accepted

Query 5/8: Write a function to reverse a string...
   💛 Model: gpt-4o
   💰 Cost: $0.001320
   🎯 Direct Route (hard complexity)

💰 TOTAL SAVINGS: 48.2% reduction
```

**Key concepts:**
- Token-based pricing (not flat rates)
- PreRouter detects complexity and routes accordingly
- Draft accepted = verifier skipped (saves money!)
- Semantic quality checking with embeddings

---

#### 2. Tool Calling 🎯
**File:** [`nodejs/tool-calling.ts`](nodejs/tool-calling.ts)
**Time:** 15 minutes
**What you'll learn:**
- Define tools with TypeScript types
- Type-safe tool definitions
- Tool execution across cascade tiers
- Universal tool format

**Key features:**
- Full TypeScript type safety
- Weather and calculator tools
- Automatic tool format conversion
- Cross-provider compatibility

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
npx tsx tool-calling.ts
```

---

#### 3. Multi-Provider Cascade 🌐
**File:** [`nodejs/multi-provider.ts`](nodejs/multi-provider.ts)
**Time:** 10 minutes
**What you'll learn:**
- Mix models from different providers
- OpenAI + Anthropic + Groq
- Provider-specific configurations
- Cross-provider cost comparison

**Example setup:**
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },  // Fast & cheap
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },              // Quality
    { name: 'claude-3-5-sonnet', provider: 'anthropic', cost: 0.003 },  // Reasoning
  ],
});
```

**Requirements:**
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
```

---

#### 4. Reasoning Models 🧠
**File:** [`nodejs/reasoning-models.ts`](nodejs/reasoning-models.ts)
**Time:** 10 minutes
**What you'll learn:**
- Use o1, o3-mini, Claude 3.7, DeepSeek-R1
- Extended thinking mode
- Chain-of-thought reasoning
- Zero configuration (auto-detects reasoning capabilities)

**Supported models:**
- **OpenAI:** o1, o1-mini, o3-mini
- **Anthropic:** claude-3-7-sonnet-20250219
- **Ollama:** deepseek-r1, deepseek-r1-distill (free local)
- **vLLM:** deepseek-r1 (self-hosted)

**Example:**
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'o1', provider: 'openai', cost: 0.015 },  // Auto-detected
  ],
});

// Reasoning tokens automatically tracked
const result = await agent.run('Solve the Traveling Salesman Problem');
```

</details>

<details>
<summary><h3>💰 Cost Management (1 example)</h3></summary>

Track costs and manage budgets in production.

#### Cost Tracking
**File:** [`nodejs/cost-tracking.ts`](nodejs/cost-tracking.ts)
**Time:** 15 minutes
**What you'll learn:**
- Real-time cost tracking across queries
- Per-model and per-provider cost analysis
- Budget limits and alerts
- Cost history and trends

**Features:**
- Tracks costs per query, model, and provider
- Manual tracking implementation (TypeScript doesn't have telemetry module yet)
- Budget warnings at configurable thresholds
- Cost breakdown by complexity

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
npx tsx cost-tracking.ts
```

**Output example:**
```
📊 Cost Breakdown:
   GPT-4o-mini: $0.000420 (5 queries)
   GPT-4o:      $0.004650 (3 queries)
   Total:       $0.005070

💰 Budget Status:
   Used:   $0.005070 / $10.00 (0.05%)
   Remaining: $9.995
```

</details>

<details>
<summary><h3>🤖 Quality & Validation (1 example)</h3></summary>

ML-based semantic validation using embeddings.

#### Semantic Quality Validation
**File:** [`nodejs/semantic-quality.ts`](nodejs/semantic-quality.ts)
**Time:** 15 minutes
**What you'll learn:**
- Semantic similarity scoring with BGE-small-en-v1.5
- Off-topic response detection
- Integration with cascade quality validation
- Request-scoped caching for performance

**Features:**
- **Model:** BGE-small-en-v1.5 (~40MB, auto-downloads)
- **Runtime:** CPU-based, fully local inference
- **Latency:** ~50-100ms per check (with caching)
- **Caching:** 50% latency reduction on cache hits

**Installation:**
```bash
npm install @cascadeflow/ml @xenova/transformers
```

**Example:**
```typescript
import { CascadeAgent } from '@cascadeflow/core';
import { UnifiedEmbeddingService } from '@cascadeflow/ml';

const embeddingService = await UnifiedEmbeddingService.getInstance();

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
  quality: {
    semanticThreshold: 0.7,  // Reject if similarity < 70%
    embeddingService,
  },
});
```

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
npx tsx semantic-quality.ts
```

</details>

<details>
<summary><h3>🏭 Production (1 example)</h3></summary>

Deploy cascadeflow to production with enterprise patterns.

#### Production Patterns ⭐
**File:** [`nodejs/production-patterns.ts`](nodejs/production-patterns.ts)
**Time:** 30 minutes
**What you'll learn:**
- Error handling and automatic retries
- Response caching for performance
- Rate limiting and throttling
- Monitoring and logging
- Cost tracking and budgets
- Failover strategies

**Patterns covered:**
- Exponential backoff retries
- In-memory and Redis caching
- Token bucket rate limiting
- Structured logging
- Budget enforcement
- Multi-provider fallback

**Features:**
```typescript
// Error handling with retries
async function withRetry(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await sleep(Math.pow(2, i) * 1000);  // Exponential backoff
    }
  }
}

// Response caching
class ResponseCache {
  cache = new Map();
  ttl = 3600;  // 1 hour

  get(key: string): string | null {
    const entry = this.cache.get(key);
    if (!entry || Date.now() > entry.expiry) return null;
    return entry.value;
  }
}

// Rate limiting
class RateLimiter {
  tokens: number;
  maxTokens: number;
  refillRate: number;  // tokens per second
}
```

**Run it:**
```bash
export OPENAI_API_KEY="sk-..."
npx tsx production-patterns.ts
```

</details>

---

## 🎓 Learning Path

### Step 1: Basics (30 minutes)
1. ✅ Run `basic-usage.ts` - Understand core concepts
2. ✅ Read the code comments - Learn patterns
3. ✅ Try different queries - See routing decisions

**Key concepts:**
- Cascading = cheap model first, escalate if needed
- Draft accepted = money saved ✅
- Draft rejected = quality ensured ✅
- PreRouter detects complexity before calling models

### Step 2: Tools & Multi-Provider (30 minutes)
1. ✅ Run `tool-calling.ts` - Learn tool usage
2. ✅ Run `multi-provider.ts` - Mix providers
3. ✅ Run `reasoning-models.ts` - Try o1/o3

**Key concepts:**
- Type-safe tool definitions
- Universal tool format
- Cross-provider compatibility
- Reasoning token tracking

### Step 3: Cost Management (30 minutes)
1. ✅ Run `cost-tracking.ts` - Learn budget tracking
2. ✅ Implement custom budget logic
3. ✅ Read [Cost Tracking Guide](../../../docs/guides/cost_tracking.md)

**Key concepts:**
- Token-based pricing
- Per-model breakdown
- Budget alerts
- Cost optimization

### Step 4: Production (1 hour)
1. ✅ Run `production-patterns.ts` - Enterprise patterns
2. ✅ Run `semantic-quality.ts` - ML validation
3. ✅ Read [Production Guide](../../../docs/guides/production.md)

**Key concepts:**
- Error handling
- Rate limiting
- Caching
- Monitoring

---

## 🛠️ Running Examples

### Prerequisites

```bash
# Install cascadeflow
npm install @cascadeflow/core

# For semantic quality example
npm install @cascadeflow/ml @xenova/transformers

# Install peer dependencies for providers you'll use
npm install openai                    # OpenAI
npm install @anthropic-ai/sdk         # Anthropic
npm install groq-sdk                  # Groq
```

### Set API Keys

```bash
# OpenAI (most examples)
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Groq (free, fast)
export GROQ_API_KEY="gsk_..."

# Together AI
export TOGETHER_API_KEY="..."

# HuggingFace
export HF_TOKEN="hf_..."
```

### Run Examples

```bash
# Navigate to examples directory
cd packages/core/examples/nodejs

# Run with tsx (recommended)
npx tsx basic-usage.ts
npx tsx tool-calling.ts
npx tsx cost-tracking.ts

# Or install tsx globally
npm install -g tsx
tsx basic-usage.ts
```

---

## 💡 Example Code

### Minimal Example (Recommended Setup)

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// Recommended: Claude Haiku + GPT-5
const agent = new CascadeAgent({
  models: [
    { name: 'claude-haiku-4-5-20251001', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
});

const result = await agent.run('What is TypeScript?');
console.log(`Cost: $${result.totalCost}, Savings: ${result.savingsPercentage}%`);
```

> **Note:** GPT-5 availability depends on your OpenAI account tier. The cascade works immediately - Claude Haiku handles 75% of queries!

### OpenAI Only

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
});
```

### With Full Configuration

```typescript
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

const models: ModelConfig[] = [
  {
    name: 'claude-haiku-4-5-20251001',
    provider: 'anthropic',
    cost: 0.0008,
    apiKey: process.env.ANTHROPIC_API_KEY,
  },
  {
    name: 'gpt-4o',
    provider: 'openai',
    cost: 0.00625,
    apiKey: process.env.OPENAI_API_KEY,
  },
];

const agent = new CascadeAgent({
  models,
  quality: {
    threshold: 0.7,  // Quality configured at agent level
    requireMinimumTokens: 10,
  },
});

const result = await agent.run('Explain quantum computing');

console.log(result.content);
console.log(`Cost: $${result.totalCost}, Saved: ${result.savingsPercentage}%`);
```

---

## 🌐 Universal Browser Support

All 7 providers work in both Node.js and browser:

- ✅ OpenAI
- ✅ Anthropic
- ✅ Groq
- ✅ Together AI
- ✅ Ollama (local)
- ✅ HuggingFace
- ✅ vLLM (local)

cascadeflow automatically detects your runtime environment!

**Browser Example:** See [`browser/vercel-edge/`](browser/vercel-edge/) for edge function deployment.

---

## 🔧 Troubleshooting

<details>
<summary><b>API key errors</b></summary>

```bash
# Check if set
echo $OPENAI_API_KEY

# Set it
export OPENAI_API_KEY="sk-..."

# Windows
set OPENAI_API_KEY=sk-...

# Or use .env file
echo "OPENAI_API_KEY=sk-..." > .env
```
</details>

<details>
<summary><b>Import errors</b></summary>

```bash
# Install core package
npm install @cascadeflow/core

# Install peer dependencies
npm install openai @anthropic-ai/sdk groq-sdk

# For semantic quality
npm install @cascadeflow/ml @xenova/transformers
```
</details>

<details>
<summary><b>Examples run but show errors</b></summary>

```bash
# Check Node.js version (18+ required)
node --version

# Reinstall
rm -rf node_modules package-lock.json
npm install
```
</details>

<details>
<summary><b>tsx command not found</b></summary>

```bash
# Install tsx
npm install -g tsx

# Or use npx
npx tsx basic-usage.ts
```
</details>

<details>
<summary><b>Semantic quality model download fails</b></summary>

```bash
# Model downloads automatically on first run
# If it fails, check internet connection and try again

# Manual cache clear
rm -rf ~/.cache/huggingface
```
</details>

---

## 💡 Pro Tips

### 1. Start Simple
Begin with `basic-usage.ts` before advanced examples.

### 2. Read the Code
All examples are heavily commented. Read through to understand patterns.

### 3. Key Concepts

**Token-Based Pricing:**
- Input and output tokens priced differently
- gpt-4o: $0.0025 input, $0.010 output per 1K tokens
- Actual costs depend on query/response length

**Cost Savings:**
- Draft accepted = only cheap model used (big savings!)
- Draft rejected = both models used (quality ensured)
- Direct routing = only expensive model used (no savings)

**Quality Validation:**
- Logprobs-based (default)
- Semantic similarity with embeddings (optional)
- Custom validators supported

### 4. Watch Statistics

```typescript
const result = await agent.run(query);

// Access result properties
console.log(`Model: ${result.modelUsed}`);
console.log(`Cost: $${result.totalCost}`);
console.log(`Savings: ${result.savingsPercentage}%`);
console.log(`Latency: ${result.latencyMs}ms`);
console.log(`Cascaded: ${result.cascaded}`);
console.log(`Draft Accepted: ${result.draftAccepted}`);
```

### 5. Cost Tracking Pattern

```typescript
// Track costs manually
const costs = {
  total: 0,
  byModel: {} as Record<string, number>,
  queries: 0,
};

for (const query of queries) {
  const result = await agent.run(query);

  costs.total += result.totalCost;
  costs.byModel[result.modelUsed] =
    (costs.byModel[result.modelUsed] || 0) + result.totalCost;
  costs.queries++;
}

console.log(`Average cost per query: $${(costs.total / costs.queries).toFixed(6)}`);
```

---

## 📖 Complete Documentation

### Getting Started Guides
- [Quick Start](../../../docs/guides/quickstart.md) - 5-minute introduction
- [Providers Guide](../../../docs/guides/providers.md) - Configure AI providers
- [Tools Guide](../../../docs/guides/tools.md) - Function calling
- [Cost Tracking](../../../docs/guides/cost_tracking.md) - Budget management
- [TypeScript Quickstart](../../../docs/guides/quickstart-typescript.md) - TypeScript-specific setup

### Advanced Guides
- [Production Guide](../../../docs/guides/production.md) - Enterprise deployment
- [Performance Guide](../../../docs/guides/performance.md) - Optimization
- [Custom Cascade](../../../docs/guides/custom_cascade.md) - Custom routing
- [Custom Validation](../../../docs/guides/custom_validation.md) - Quality control
- [Browser Cascading](../../../docs/guides/browser_cascading.md) - Edge/browser deployment

📚 **[View All Documentation →](../../../docs/)**

---

## 🤝 Contributing Examples

Have a great use case? Contribute an example!

### Template

```typescript
/**
 * Your Example - Brief Description
 *
 * What it demonstrates:
 * - Feature 1
 * - Feature 2
 *
 * Requirements:
 * - npm install @cascadeflow/core
 * - export OPENAI_API_KEY="..."
 *
 * Setup:
 *     npm install @cascadeflow/core
 *     export OPENAI_API_KEY="..."
 *     npx tsx your-example.ts
 *
 * Expected Results:
 *     Description of output
 */

import { CascadeAgent } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('YOUR EXAMPLE TITLE');
  console.log('='.repeat(80));

  // Your code here

  console.log('\nKEY TAKEAWAYS:');
  console.log('- Takeaway 1');
  console.log('- Takeaway 2');
}

main().catch(console.error);
```

See [CONTRIBUTING.md](../../../CONTRIBUTING.md) for guidelines.

---

## 📞 Need Help?

### Documentation
📖 [Complete Guides](../../../docs/guides/)
🛠️ [Tools Guide](../../../docs/guides/tools.md)
💰 [Cost Tracking Guide](../../../docs/guides/cost_tracking.md)
🏭 [Production Guide](../../../docs/guides/production.md)
📘 [TypeScript Quickstart](../../../docs/guides/quickstart-typescript.md)

### Community
💬 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions) - Ask questions
🐛 [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues) - Report bugs
💡 Use "question" label for general questions

---

## 📊 Summary

### ✅ Available Examples (7 total)

**Core (4):** Basic usage, tool calling, multi-provider, reasoning models

**Cost Management (1):** Cost tracking

**Quality & Validation (1):** Semantic quality with ML

**Production (1):** Production patterns

### 📚 Documentation Coverage

- ✅ **7 TypeScript examples** (~2,500+ lines of code)
- ✅ **Comprehensive README** (this file)
- ✅ **Individual example READMEs** (nodejs/README.md, browser/README.md)
- ✅ **Full TypeScript definitions** with IDE autocomplete
- ✅ **10+ comprehensive guides** in main docs

### 🔑 Key Learnings

**Essential Concepts:**
- ✅ Draft accepted = money saved
- ✅ Draft rejected = quality ensured
- ✅ PreRouter detects complexity before cascade
- ✅ Token-based pricing (input/output split)
- ✅ Semantic quality with embeddings
- ✅ Universal tool format

**Production Ready:**
- ✅ Error handling
- ✅ Rate limiting
- ✅ Caching
- ✅ Budget management
- ✅ ML-based validation

---

**💰 Save 40-85% on AI costs with intelligent cascading!** 🚀

[View All Documentation](../../../docs/) • [Python Examples](../../../examples/) • [TypeScript Examples](./nodejs/) • [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions)
