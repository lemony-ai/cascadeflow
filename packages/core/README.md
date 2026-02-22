<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../.github/assets/CF_logo_bright.svg">
  <source media="(prefers-color-scheme: light)" srcset="../../.github/assets/CF_logo_dark.svg">
  <img alt="cascadeflow Logo" src="../../.github/assets/CF_logo_dark.svg" width="80%" style="margin: 20px auto;">
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
      name: 'claude-haiku-4-5',
      provider: 'anthropic',
      cost: 0.001  // Fast, high-quality drafter
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

### Quality Configuration

Control when the cascade uses the drafter vs. verifier with quality thresholds:

```typescript
// Recommended: Complexity-aware thresholds
const agent = new CascadeAgent({
  models: [
    { name: 'claude-haiku-4-5', provider: 'anthropic', cost: 0.001 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }
  ],
  quality: {
    confidenceThresholds: {
      simple: 0.6,      // "What is Python?" - Accept 60%+ confidence
      moderate: 0.7,    // "Compare Python vs Java" - Accept 70%+
      hard: 0.8,     // "Analyze quantum computing" - Accept 80%+
      expert: 0.85      // "Implement distributed cache" - Accept 85%+
    }
  }
});
```

**Quick Configuration Options:**

```typescript
// Option 1: Use CASCADE_QUALITY_CONFIG (optimized for 50-60% acceptance)
import { CascadeAgent, CASCADE_QUALITY_CONFIG } from '@cascadeflow/core';
const agent = new CascadeAgent({
  models: [...],
  quality: CASCADE_QUALITY_CONFIG  // Lower threshold (0.40) = more cost savings
});

// Option 2: Simple flat threshold
const agent = new CascadeAgent({
  models: [...],
  quality: {
    threshold: 0.7,              // 70% confidence required (default)
    requireMinimumTokens: 10     // Minimum response length
  }
});

// Option 3: Use defaults (no quality config needed)
const agent = new CascadeAgent({
  models: [...]
  // Automatically uses threshold: 0.7
});
```

**When to adjust:**
- **Lower thresholds (0.4-0.6)**: More drafts accepted → higher cost savings, slightly lower quality
- **Higher thresholds (0.8-0.9)**: Fewer drafts accepted → lower savings, maximum quality
- **Complexity-aware**: Best balance → adjusts automatically based on query difficulty

> **⚠️ GPT-5 Requires Organization Verification**
>
> To use GPT-5, your OpenAI organization must be verified:
> 1. Go to https://platform.openai.com/settings/organization/general
> 2. Click "Verify Organization"
> 3. Wait ~15 minutes for access to propagate
>
> **Works immediately:** The cascade above works right away! Claude Haiku handles 75% of queries, GPT-5 only called when needed.

> **📝 Model Naming**
>
> Both naming conventions work with CascadeFlow:
> - `claude-haiku-4-5` (used in presets, recommended)
> - `claude-3-5-haiku-20241022` (Anthropic API format)
>
> The library accepts both formats and routes them correctly.

### OpenAI Only

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }  // Requires org verification
  ]
});
```

### Even Easier: Use Presets

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
| `PRESET_ULTRA_FAST` | Real-time apps | Ultra-fast (~1-2s) | ~$0.0002 | Groq |
| `PRESET_ULTRA_CHEAP` | High volume | Very fast (~1-3s) | ~$0.00008 | Groq + OpenAI |
| `PRESET_OPENAI_ONLY` | Single provider | Fast (~2-4s) | ~$0.0004 | OpenAI |
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

## Advanced Features

### 🎚️ Quality Profiles

Control quality validation with predefined profiles optimized for different use cases:

```typescript
import { CascadeAgent, QualityValidator } from '@cascadeflow/core';

// Strict Mode: Maximum quality with semantic validation
const strictAgent = new CascadeAgent({
  models: [...],
  cascade: {
    enabled: true,
    qualityConfig: {
      useProductionConfidence: true,
      strictMode: true,
      useSemanticValidation: true,
      minConfidence: 0.85,
      provider: 'openai',
    },
  },
});

// Or use factory methods
const strictValidator = QualityValidator.strict();
const prodValidator = QualityValidator.forProduction();    // Multi-signal confidence
const devValidator = QualityValidator.forDevelopment();     // Lenient for testing
const cascadeValidator = QualityValidator.forCascade();     // Optimized for 50-60% acceptance
const permissiveValidator = QualityValidator.permissive();  // Maximum throughput
```

**Available Profiles:**
- **Strict**: 85% confidence + semantic validation (maximum quality)
- **Production**: 70% confidence with multi-signal estimation (balanced)
- **Development**: 50% confidence, minimal word count (fast iteration)
- **Cascade**: 40% confidence, optimized for cost savings (50-60% draft acceptance)
- **Permissive**: 30% confidence, maximum throughput (highest savings)

[📖 Full example](examples/nodejs/quality-profiles.ts)

### 📡 Telemetry & Callbacks

Monitor cascade operations with event-driven callbacks:

```typescript
import { CascadeAgent, CallbackManager, CallbackEvent } from '@cascadeflow/core';

const callbackManager = new CallbackManager(true); // verbose=true

// Track query lifecycle
callbackManager.register(CallbackEvent.QUERY_START, (data) => {
  console.log(`Query started: "${data.query}"`);
});

callbackManager.register(CallbackEvent.COMPLEXITY_DETECTED, (data) => {
  console.log(`Complexity: ${data.data.complexity} (confidence: ${data.data.confidence})`);
});

callbackManager.register(CallbackEvent.DRAFT_ACCEPTED, (data) => {
  console.log(`Draft accepted! Savings: $${data.data.savings}`);
});

const agent = new CascadeAgent({
  models: [...],
  callbacks: callbackManager,
  cascade: { enabled: true },
});
```

**Available Events:**
- `QUERY_START` / `QUERY_COMPLETE` - Query lifecycle
- `COMPLEXITY_DETECTED` - Query complexity analysis
- `CASCADE_DECISION` - Routing decisions
- `QUALITY_VALIDATION` - Quality checks
- `DRAFT_ACCEPTED` / `DRAFT_REJECTED` - Draft outcomes
- `VERIFIER_CALLED` - Verifier invocations

[📖 Full example](examples/nodejs/telemetry-callbacks.ts)

### 📦 Batch Processing

Process multiple queries with progress tracking and analytics:

```typescript
const queries = [
  'What is TypeScript?',
  'Explain async/await.',
  'What are design patterns?',
];

const batchResult = await agent.runBatch(queries, {
  strategy: BatchStrategy.SEQUENTIAL,
  continueOnError: true,
  onProgress: (completed, total, currentQuery) => {
    console.log(`[${(completed/total*100).toFixed(0)}%] ${completed}/${total}`);
  },
});

// Analyze results
console.log(`Success rate: ${(batchResult.successCount / queries.length * 100).toFixed(1)}%`);
console.log(`Total cost: $${batchResult.results.reduce((sum, r) => sum + (r.result?.totalCost || 0), 0)}`);
console.log(`Draft acceptance: ${batchResult.results.filter(r => r.result?.draftAccepted).length}`);
```

[📖 Full example](examples/nodejs/batch-processing.ts)

### 🔀 Router Integration

Intelligent routing with complexity analysis and capability filtering:

```typescript
// PreRouter: Automatically routes based on query complexity
const simpleResult = await agent.run('What is 2 + 2?');
// → Uses draft model (simple query)

const complexResult = await agent.run(
  'Explain quantum computing theory with recent research references.'
);
// → Routes directly to best model (complex query)

// ToolRouter: Filters to tool-capable models
// Use a strict parser helper (see examples/nodejs/safe-math.ts).
const calculatorTool = createTool({
  name: 'calculator',
  description: 'Perform calculations',
  function: async ({ expression }) => safeCalculateExpression(expression),
});

const toolResult = await agent.run('Calculate 125 * 47', {
  tools: [calculatorTool],
});
// → Automatically excludes models without tool support

// Get router statistics
const stats = agent.getRouterStats();
console.log(stats.preRouter);  // Complexity-based routing stats
console.log(stats.toolRouter);  // Tool filtering stats
```

[📖 Full example](examples/nodejs/router-integration.ts)

### 👤 User Profiles & Workflows

Manage user tiers, budgets, and optimization preferences:

```typescript
import { createUserProfile, createWorkflowProfile, TIER_PRESETS, WORKFLOW_PRESETS } from '@cascadeflow/core';

// Tier-based profiles
const freeProfile = createUserProfile({
  tier: TIER_PRESETS.free,  // Max budget: $0.01, Quality: 0.60
});

const premiumProfile = createUserProfile({
  tier: TIER_PRESETS.premium,  // Max budget: $0.10, Quality: 0.80
});

// Custom profile with optimization weights
const customProfile = createUserProfile({
  tier: { name: 'custom', maxBudget: 0.05, qualityThreshold: 0.75 },
  optimizationWeights: {
    cost: 0.5,    // 50% weight on cost
    speed: 0.3,   // 30% weight on speed
    quality: 0.2, // 20% weight on quality
  },
});

// Latency-aware profiles
const lowLatencyProfile = createUserProfile({
  tier: TIER_PRESETS.premium,
  latencyProfile: {
    maxTotalMs: 2000,      // 2 second total limit
    maxPerModelMs: 1000,   // 1 second per model
    preferParallel: true,  // Prefer parallel execution
    skipCascadeThreshold: 1500,
  },
});

// Use with agent
const agent = new CascadeAgent({
  models: [...],
  profile: premiumProfile,
  cascade: { enabled: true },
});
```

**Workflow Presets:**
- `WORKFLOW_PRESETS.production` - High quality, reasonable latency
- `WORKFLOW_PRESETS.realtime` - Ultra-low latency, single model
- `WORKFLOW_PRESETS.batch` - Maximum throughput, relaxed constraints

[📖 Full example](examples/nodejs/user-profiles-workflows.ts)

### 🏭 Factory Methods

Simplified agent creation with auto-configuration:

```typescript
import { CascadeAgent } from '@cascadeflow/core';

// Auto-detect providers from environment variables
const envAgent = CascadeAgent.fromEnv({
  quality: 'production',  // 'strict' | 'production' | 'development'
});
// Checks for: OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, etc.

// Create from user profile
const profileAgent = CascadeAgent.fromProfile({
  profile: premiumProfile,
  preferredModels: ['gpt-4o-mini', 'gpt-4o', 'claude-3-5-haiku-20241022'],
});

// Traditional manual configuration (full control)
const manualAgent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
  cascade: { enabled: true },
});
```

**Benefits:**
- `fromEnv()`: Auto-detects available providers, sensible defaults
- `fromProfile()`: Multi-tenant applications, per-user configuration
- Manual config: Full control for production requirements

[📖 Full example](examples/nodejs/factory-methods.ts)

### 🌊 Enhanced Streaming

Event-driven streaming with real-time progress:

```typescript
const stream = agent.streamEvents('What is TypeScript?', {
  forceDirect: true,
});

for await (const event of stream) {
  switch (event.type) {
    case StreamEventType.START:
      console.log(`Streaming from: ${event.data.model}`);
      break;
    case StreamEventType.CHUNK:
      process.stdout.write(event.data.content);
      break;
    case StreamEventType.COMPLETE:
      console.log(`\nCost: $${event.data.totalCost?.toFixed(6)}`);
      console.log(`Time: ${event.data.timing?.total}ms`);
      break;
    case StreamEventType.ERROR:
      console.error(`Error: ${event.data.error}`);
      break;
  }
}

// Or collect the full result
import { collectResult } from '@cascadeflow/core';
const result = await collectResult(stream);
console.log(`Content: ${result.content}`);
console.log(`Model: ${result.modelUsed}`);
```

**Use Cases:**
- Interactive chat applications
- Real-time content generation
- Progressive content display
- Long-form content (articles, essays)

[📖 Full example](examples/nodejs/enhanced-streaming.ts)

## Features

- 🎯 **Smart Cascading**: Automatically tries smaller models first
- 💰 **Cost Optimization**: Save 40-85% on LLM costs
- ⚡ **Fast**: 2-10x faster responses with small models
- 🔀 **Multi-Provider**: OpenAI, Anthropic, Groq, and more
- ✅ **Quality Validation**: Multi-signal confidence with semantic analysis
- 📊 **Telemetry**: Event-driven monitoring with callbacks
- 📦 **Batch Processing**: Sequential processing with analytics
- 🔀 **Intelligent Routing**: Complexity-based and capability-aware
- 👤 **User Profiles**: Tier-based access control and budgets
- 🌊 **Enhanced Streaming**: Event-driven streaming with progress
- 🏭 **Factory Methods**: Simplified setup with auto-configuration
- 📈 **Cost Tracking**: Detailed metrics and savings analysis

## Examples

All examples are available in the [`examples/nodejs`](examples/nodejs) directory:

- [**quality-profiles.ts**](examples/nodejs/quality-profiles.ts) - Quality validation profiles (strict, production, development, cascade, permissive)
- [**telemetry-callbacks.ts**](examples/nodejs/telemetry-callbacks.ts) - Event-driven monitoring and callbacks
- [**batch-processing.ts**](examples/nodejs/batch-processing.ts) - Batch processing with progress tracking
- [**router-integration.ts**](examples/nodejs/router-integration.ts) - PreRouter and ToolRouter integration
- [**user-profiles-workflows.ts**](examples/nodejs/user-profiles-workflows.ts) - User profiles, tiers, and workflows
- [**factory-methods.ts**](examples/nodejs/factory-methods.ts) - Factory methods (fromEnv, fromProfile)
- [**enhanced-streaming.ts**](examples/nodejs/enhanced-streaming.ts) - Enhanced streaming with events

Run any example with:
```bash
npx tsx examples/nodejs/<example-name>.ts
```

## Documentation

See the [main cascadeflow documentation](https://github.com/lemony-ai/cascadeflow) for complete guides and examples.

## License

MIT © Lemony Inc.
