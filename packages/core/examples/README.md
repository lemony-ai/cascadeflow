# cascadeflow TypeScript Examples

Examples for using `@cascadeflow/core` in TypeScript/JavaScript environments.

## 📁 Example Categories

### Node.js Examples (`nodejs/`)

Server-side TypeScript examples for Node.js applications:

- **basic-usage.ts** - Simple two-tier cascade setup
- **tool-calling.ts** - Function calling with type-safe tools
- **multi-provider.ts** - Using multiple AI providers together
- **reasoning-models.ts** - OpenAI o1/o3, Claude 3.7 Sonnet, DeepSeek-R1 reasoning models
- **production-patterns.ts** - Error handling, caching, rate limiting, monitoring

[→ See nodejs/README.md for details](./nodejs/README.md)

### Browser Examples (`browser/`)

Client-side examples for browser and edge runtimes:

- **vercel-edge/** - Deploy as Vercel Edge Function
- More browser examples coming soon!

[→ See browser/README.md for details](./browser/README.md)

## 🚀 Quick Start

### Node.js

```bash
cd nodejs/
npm install
export OPENAI_API_KEY="your-key"
npx tsx basic-usage.ts
```

### Browser (Vercel Edge)

```bash
cd browser/vercel-edge/
npm install
vercel dev
```

## 📚 All Features Demonstrated

| Feature | Node.js | Browser |
|---------|---------|---------|
| Basic Cascade | ✅ | ✅ |
| Tool Calling | ✅ | 🔜 |
| Multi-Provider | ✅ | ✅ |
| Reasoning Models | ✅ | 🔜 |
| Production Patterns | ✅ | 🔜 |
| Streaming | 🔜 | 🔜 |
| Cost Tracking | ✅ | ✅ |

## 🔑 Environment Setup

All examples require API keys for the providers you use:

```bash
# OpenAI (most examples use this)
export OPENAI_API_KEY="sk-..."

# Optional: Other providers
export ANTHROPIC_API_KEY="sk-ant-..."
export GROQ_API_KEY="gsk_..."
export HUGGINGFACE_API_KEY="hf_..."
```

## 💡 Example Code

### Minimal Example (Recommended Setup)

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// Recommended: Claude Haiku + GPT-5
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },  // Requires org verification
  ],
});

const result = await agent.run('What is TypeScript?');
console.log(`Savings: ${result.savingsPercentage}%`);
```

> **Note:** GPT-5 requires [organization verification](../../docs/GPT-5-SETUP.md). The cascade works immediately - Claude Haiku handles 75% of queries!

### OpenAI Only

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
});
```

### With Full Configuration

```typescript
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

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
const result = await agent.run('Explain quantum computing');

console.log(result.content);
console.log(`Cost: $${result.totalCost}, Saved: ${result.savingsPercentage}%`);
```

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

## 📖 Documentation

- **Main Docs**: [/docs/](../../docs/)
- **TypeScript Guide**: [/docs/guides/typescript.md](../../docs/guides/typescript.md)
- **API Reference**: Check TypeScript definitions in `packages/core/src/`
- **Python Examples**: [/examples/](../../../examples/) for production patterns

## 🔧 Running Examples

### Using tsx (recommended)

```bash
npm install -g tsx
tsx basic-usage.ts
```

### Using ts-node

```bash
npm install -g ts-node
ts-node basic-usage.ts
```

### Compile first

```bash
tsc basic-usage.ts
node basic-usage.js
```

## ❓ Support

- **GitHub**: https://github.com/lemony-ai/cascadeflow
- **Issues**: https://github.com/lemony-ai/cascadeflow/issues
- **npm Package**: https://www.npmjs.com/package/@cascadeflow/core
