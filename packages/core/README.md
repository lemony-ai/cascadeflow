# @cascadeflow/core

TypeScript/JavaScript library for CascadeFlow - Smart AI model cascading for cost optimization.

## Installation

```bash
npm install @cascadeflow/core
# or
pnpm add @cascadeflow/core
# or
yarn add @cascadeflow/core
```

## Quick Start

```typescript
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625
    }
  ]
});

const result = await agent.run('What is artificial intelligence?');

console.log(result.content);
console.log(`Cost: $${result.totalCost}`);
console.log(`Savings: ${result.savingsPercentage}%`);
```

## Features

- 🎯 **Smart Cascading**: Automatically tries smaller models first
- 💰 **Cost Optimization**: Save 40-85% on LLM costs
- ⚡ **Fast**: 2-10x faster responses with small models
- 🔀 **Multi-Provider**: OpenAI, Anthropic, Groq, and more
- ✅ **Quality Validation**: Automatic quality checks and escalation
- 📊 **Cost Tracking**: Built-in metrics and analytics

## Documentation

See the [main CascadeFlow documentation](https://github.com/lemony-ai/cascadeflow) for complete guides and examples.

## License

MIT © Lemony Inc.
