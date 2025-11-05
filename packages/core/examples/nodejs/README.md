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

The simplest introduction to cascadeflow.

**What it shows:**
- Setting up a two-tier cascade
- Automatic query routing
- Cost tracking

**Run:**
```bash
export OPENAI_API_KEY="your-key"
npx tsx basic-usage.ts
```

### 2. Tool Calling (`tool-calling.ts`)

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

### 3. Multi-Provider (`multi-provider.ts`)

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

### 4. Reasoning Models (`reasoning-models.ts`)

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

### 5. Production Patterns (`production-patterns.ts`)

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
    qualityThreshold: 0.7,
    apiKey: process.env.ANTHROPIC_API_KEY,
  },
  {
    name: 'gpt-5',
    provider: 'openai',
    cost: 0.00125,
    qualityThreshold: 0.95,
    apiKey: process.env.OPENAI_API_KEY,
  },
];

const agent = new CascadeAgent({ models });
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
