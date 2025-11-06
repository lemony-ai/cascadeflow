<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/CF_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset="../../.github/assets/CF_logo_dark.svg">
  <img alt="cascadeflow Logo" src="../../.github/assets/CF_logo_dark.svg" width="533">
</picture>

# @cascadeflow/core

[![npm version](https://img.shields.io/npm/v/@cascadeflow/core?color=red&label=npm)](https://www.npmjs.com/package/@cascadeflow/core)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![Tests](https://github.com/lemony-ai/cascadeflow/actions/workflows/test.yml/badge.svg)](https://github.com/lemony-ai/cascadeflow/actions/workflows/test.yml)

**<img src="../../.github/assets/CF_ts_color.svg" width="22" height="22" alt="TypeScript" style="vertical-align: middle;"/> TypeScript/JavaScript library for cascadeflow**

</div>

---

**Smart AI model cascading for cost optimization.**

Save 40-85% on LLM costs with intelligent model routing. Available for Node.js, browser, and edge environments.

## Installation

```bash
npm install @cascadeflow/core
# or
pnpm add @cascadeflow/core
# or
yarn add @cascadeflow/core
```

## Quick Start

### Recommended Setup (Claude Haiku + GPT-5)

```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'claude-3-5-haiku-20241022',
      provider: 'anthropic',
      cost: 0.00008  // Fast, high-quality drafter
    },
    {
      name: 'gpt-5',
      provider: 'openai',
      cost: 0.00125  // Superior reasoning verifier (50% cheaper than GPT-4o!)
    }
  ]
});

const result = await agent.run('What is artificial intelligence?');

console.log(result.content);
console.log(`Cost: $${result.totalCost}`);
console.log(`Savings: ${result.savingsPercentage}%`);
```

> **⚠️ GPT-5 Requires Organization Verification**
>
> To use GPT-5, your OpenAI organization must be verified:
> 1. Go to https://platform.openai.com/settings/organization/general
> 2. Click "Verify Organization"
> 3. Wait ~15 minutes for access to propagate
>
> **Works immediately:** The cascade above works right away! Claude Haiku handles 75% of queries, GPT-5 only called when needed.

### OpenAI Only

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }  // Requires org verification
  ]
});
```

### Even Easier: Use Presets (NEW in v0.1.1)

**No configuration needed** - just import a preset and go:

```typescript
import { CascadeAgent, PRESET_ULTRA_FAST, PRESET_BEST_OVERALL } from '@cascadeflow/core';

// Ultra-fast with Groq (5-10x faster than OpenAI)
const agent = new CascadeAgent(PRESET_ULTRA_FAST);

// Or best overall (Claude Haiku + GPT-4o-mini)
const agent = new CascadeAgent(PRESET_BEST_OVERALL);

const result = await agent.run('Your query here');
```

**Available Presets:**

| Preset | Best For | Speed | Cost/Query | API Keys |
|--------|----------|-------|-----------|----------|
| `PRESET_BEST_OVERALL` | Most use cases | Fast (~2-3s) | ~$0.0008 | Anthropic + OpenAI |
| `PRESET_ULTRA_FAST` | Real-time apps | Ultra-fast (~1-2s) | ~$0.00005 | Groq |
| `PRESET_ULTRA_CHEAP` | High volume | Very fast (~1-3s) | ~$0.00008 | Groq + OpenAI |
| `PRESET_OPENAI_ONLY` | Single provider | Fast (~2-4s) | ~$0.0005 | OpenAI |
| `PRESET_ANTHROPIC_ONLY` | Claude fans | Fast (~2-3s) | ~$0.002 | Anthropic |
| `PRESET_FREE_LOCAL` | Privacy/offline | Moderate (~3-5s) | $0 (free) | None (Ollama) |

**Custom Presets:**

```typescript
import { CascadeAgent, createPreset } from '@cascadeflow/core';

const agent = new CascadeAgent(
  createPreset({
    quality: 'strict',      // 'cost-optimized' | 'balanced' | 'strict'
    performance: 'fast',    // 'fast' | 'balanced' | 'reliable'
    includePremium: true    // Add premium tier (gpt-4o)
  })
);
```

## Features

- 🎯 **Smart Cascading**: Automatically tries smaller models first
- 💰 **Cost Optimization**: Save 40-85% on LLM costs
- ⚡ **Fast**: 2-10x faster responses with small models
- 🔀 **Multi-Provider**: OpenAI, Anthropic, Groq, and more
- ✅ **Quality Validation**: Automatic quality checks and escalation
- 📊 **Cost Tracking**: Built-in metrics and analytics

## Documentation

See the [main cascadeflow documentation](https://github.com/lemony-ai/cascadeflow) for complete guides and examples.

## License

MIT © Lemony Inc.
