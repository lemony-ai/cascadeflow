# cascadeflow Node.js Examples

TypeScript/JavaScript examples for using cascadeflow in Node.js environments.

## Prerequisites

- Node.js 18+
- pnpm, npm, or yarn
- API keys for your chosen providers

## Installation

```bash
# Install cascadeflow core
npm install @cascadeflow/core

# Install peer dependencies for providers you'll use
npm install openai                    # For OpenAI
npm install @anthropic-ai/sdk         # For Anthropic
npm install groq-sdk                  # For Groq
npm install @huggingface/inference    # For HuggingFace
```

## Examples

### 1. Basic Usage (`basic-usage.ts`)

The simplest and most comprehensive introduction to cascadeflow.

**What it shows:**
- Setting up a two-tier cascade (cheap → expensive)
- Processing 8 queries with different complexity levels
- Automatic quality-based routing
- Real-time cost tracking and savings calculation
- Detailed latency breakdowns
- Token-based pricing demonstration

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx basic-usage.ts
```

### 2. Cost Tracking (`cost-tracking.ts`)

Comprehensive cost tracking and budget management.

**What it shows:**
- Real-time cost tracking across multiple queries
- Per-model and per-provider cost analysis
- Budget limits and alerts
- Cost history and trends
- Manual tracking implementation (TypeScript doesn't have telemetry module yet)

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx cost-tracking.ts
```

### 3. Tool Calling (`tool-calling.ts`)

Function/tool calling with cascadeflow.

**What it shows:**
- Defining tools with TypeScript types
- Tool execution across cascade tiers
- Type-safe tool definitions

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx tool-calling.ts
```

### 4. Multi-Provider (`multi-provider.ts`)

Using multiple AI providers together.

**What it shows:**
- Mixing OpenAI, Anthropic, Groq
- Cross-provider cascading
- Provider-specific configurations

**Run:**
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export GROQ_API_KEY="your-key"
npx tsx multi-provider.ts
```

### 5. Reasoning Models (`reasoning-models.ts`)

Use advanced reasoning models across 4 providers with automatic detection.

**What it shows:**
- OpenAI o1, o1-mini, o3-mini with chain-of-thought
- Anthropic claude-3-7-sonnet with extended thinking
- Ollama DeepSeek-R1 (free local inference)
- vLLM DeepSeek-R1 (self-hosted)
- Zero configuration - auto-detects reasoning capabilities

**Supported Models:**
- **OpenAI**: o1, o1-mini, o3-mini
- **Anthropic**: claude-3-7-sonnet-20250219
- **Ollama**: deepseek-r1, deepseek-r1-distill
- **vLLM**: deepseek-r1, deepseek-r1-distill

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx reasoning-models.ts
```

### 6. Semantic Quality (`semantic-quality.ts`)

ML-based semantic validation using embeddings for query-response alignment.

**What it shows:**
- Semantic similarity scoring (BGE-small-en-v1.5 embeddings)
- Off-topic response detection
- Integration with cascade quality validation
- Request-scoped caching for performance
- Comparison with traditional validation

**Features:**
- **Model**: BGE-small-en-v1.5 (~40MB, auto-downloads)
- **Runtime**: CPU-based, fully local inference
- **Latency**: ~50-100ms per check (with caching)
- **Caching**: 50% latency reduction on cache hits

**Installation:**
```bash
npm install @cascadeflow/ml @xenova/transformers
```

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx semantic-quality.ts
```

### 7. Production Patterns (`production-patterns.ts`)

Best practices for deploying cascadeflow in production.

**What it shows:**
- Error handling and automatic retries
- Response caching for performance
- Rate limiting and throttling
- Monitoring and logging
- Cost tracking and budgets
- Failover strategies

**Patterns Covered:**
- Exponential backoff retries
- In-memory and Redis caching
- Token bucket rate limiting
- Structured logging
- Budget enforcement
- Multi-provider fallback

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx production-patterns.ts
```

## Quick Start

### Minimal Example (Recommended Setup)

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// Recommended: Claude Haiku + GPT-5
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
});

const result = await agent.run('What is TypeScript?');
console.log(`Cost: $${result.totalCost}, Savings: ${result.savingsPercentage}%`);
```

### OpenAI Only

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
});
```

### With TypeScript

All examples include full TypeScript types for IDE autocomplete and type checking.

```typescript
import { CascadeAgent, ModelConfig, CascadeResult } from '@cascadeflow/core';

const models: ModelConfig[] = [
  {
    name: 'claude-3-5-haiku-20241022',
    provider: 'anthropic',
    cost: 0.0008,
    apiKey: process.env.ANTHROPIC_API_KEY,
  },
  {
    name: 'gpt-5',
    provider: 'openai',
    cost: 0.00125,
    apiKey: process.env.OPENAI_API_KEY,
  },
];

const agent = new CascadeAgent({
  models,
  quality: {
    threshold: 0.7,  // Quality configured at agent level, not on ModelConfig
    requireMinimumTokens: 10,
  },
});

const result: CascadeResult = await agent.run('Hello!');
```

## Environment Variables

Set API keys as environment variables:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Groq
export GROQ_API_KEY="gsk_..."

# HuggingFace
export HUGGINGFACE_API_KEY="hf_..."
```

Or use a `.env` file:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
```

Then load it:

```typescript
import 'dotenv/config';
```

## Next Steps

- **Production Patterns**: See Python examples for production best practices
- **Browser Examples**: See `../browser/` for edge functions and browser usage
- **Full Documentation**: See `/docs/` for complete guides
- **API Reference**: Full TypeScript definitions in the package

## Support

- GitHub: https://github.com/lemony-ai/cascadeflow
- Issues: https://github.com/lemony-ai/cascadeflow/issues
- Docs: https://github.com/lemony-ai/cascadeflow/tree/main/docs
