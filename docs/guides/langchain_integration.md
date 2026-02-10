# LangChain Integration Guide

This guide shows how to use cascadeflow with LangChain for intelligent AI model cascading with 40-85% cost savings while maintaining full LangChain compatibility.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Key Features](#key-features)
6. [Use Cases](#use-cases)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The **@cascadeflow/langchain** package brings cascadeflow's intelligent model cascading to LangChain applications as a drop-in replacement for standard LangChain chat models.

### What is Model Cascading?

Instead of always using expensive models:

```
Traditional: Every query → GPT-4o ($0.0025)
```

cascadeflow tries cheap models first:

```
cascadeflow:
  1. Try GPT-4o-mini ($0.00015) ← 70-80% stop here! ✅
  2. Validate quality automatically
  3. If needed → GPT-4o ($0.0025)

Result: 50-85% cost savings
```

### How It Works with LangChain

cascadeflow wraps any LangChain chat model and provides intelligent routing:

**Architecture:**

```
┌─────────────────────────────────────────┐
│         Your LangChain Application       │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │      withCascade (Proxy)        │ │
│  ├────────────────────────────────────┤ │
│  │  1. Route to Drafter (GPT-4o-mini) │ │
│  │  2. Quality Check (90% pass!)      │ │
│  │  3. Escalate to Verifier if needed │ │
│  └────────────────────────────────────┘ │
│                                          │
│  Supports: LCEL, Streaming, Tools, Batch │
└─────────────────────────────────────────┘
```

**Key Benefits:**
- 🎯 **Drop-in Replacement**: Works with all LangChain features
- 💰 **Cost Savings**: 40-85% reduction in API costs
- ⚡ **Speed**: Faster responses (drafter is quicker)
- 🔧 **Zero Config**: Works out of the box with sensible defaults
- 📊 **LangSmith Integration**: Automatic cost tracking metadata

---

## Installation

```bash
npm install @cascadeflow/langchain @langchain/core @langchain/openai
```

Or with yarn:

```bash
yarn add @cascadeflow/langchain @langchain/core @langchain/openai
```

---

## Quick Start

### Basic Usage

```typescript
import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '@cascadeflow/langchain';

// Create your models
const drafter = new ChatOpenAI({
  modelName: 'gpt-4o-mini',
  temperature: 0.7
});

const verifier = new ChatOpenAI({
  modelName: 'gpt-4o',
  temperature: 0.7
});

// Wrap them with cascade
const cascade = withCascade({
  drafter,
  verifier,
  qualityThreshold: 0.8, // 80% of queries will use drafter
});

// Use it like any LangChain chat model
const response = await cascade.invoke('Explain quantum computing');
console.log(response.content);
```

### With LCEL (LangChain Expression Language)

```typescript
import { PromptTemplate } from '@langchain/core/prompts';
import { StringOutputParser } from '@langchain/core/output_parsers';

const prompt = PromptTemplate.fromTemplate(
  'You are a helpful assistant. Answer: {question}'
);

// Chain with cascade using pipe
const chain = prompt
  .pipe(cascade)
  .pipe(new StringOutputParser());

const result = await chain.invoke({
  question: 'What is machine learning?'
});
```

---

## Configuration

### withCascade Options

```typescript
interface CascadeConfig {
  // Required: The fast, cheap model
  drafter: BaseChatModel;

  // Required: The high-quality model (fallback)
  verifier: BaseChatModel;

  // Quality threshold (0-1)
  // Higher = more queries use drafter
  // Default: 0.8
  qualityThreshold?: number;

  // Custom quality check function
  qualityCheck?: (response: BaseMessage) => Promise<number>;

  // Enable debug logging
  verbose?: boolean;
}
```

### Quality Threshold Guide

| Threshold | Drafter Usage | Use Case |
|-----------|---------------|----------|
| 0.9 | ~90% | Simple Q&A, documentation |
| 0.8 | ~80% | General purpose (default) |
| 0.7 | ~70% | More critical tasks |
| 0.6 | ~60% | High-stakes decisions |

### Model Combinations

**OpenAI:**
```typescript
const drafter = new ChatOpenAI({ modelName: 'gpt-4o-mini' });
const verifier = new ChatOpenAI({ modelName: 'gpt-4o' });
```

**Anthropic:**
```typescript
import { ChatAnthropic } from '@langchain/anthropic';

const drafter = new ChatAnthropic({ modelName: 'claude-3-haiku-20240307' });
const verifier = new ChatAnthropic({ modelName: 'claude-3-5-sonnet-20241022' });
```

**Mix and Match:**
```typescript
// Cheap drafter (Haiku), powerful verifier (GPT-4o)
const drafter = new ChatAnthropic({ modelName: 'claude-3-haiku-20240307' });
const verifier = new ChatOpenAI({ modelName: 'gpt-4o' });
```

---

## Key Features

### 1. Streaming Support

Streaming support with automatic pre-routing:

```typescript
// Stream from cascade
const stream = await cascade.stream('Write a story about a robot');

for await (const chunk of stream) {
  process.stdout.write(chunk.content);
}
```

**How it works:**
- Pre-routing: Cascade may choose a single model (direct-to-verifier) before streaming starts.
- Text-only: Cascade streams the drafter optimistically, then escalates to the verifier only if needed.
- Tool-safe: If tools are bound via `bindTools(...)`, Cascade buffers the drafter stream and only emits chunks after the final model decision, so tool call deltas are never "changed mid-flight".
- Clean output by default: Cascade does not inject "switch" messages into the stream unless explicitly enabled.

To enable a debug "switch" message (TypeScript only), pass:
```typescript
await cascade.stream("...", { metadata: { cascadeflow_emit_switch_message: true } })
```

### 2. Tool Calling & Function Calling

Bind tools to cascade - they propagate to both models:

```typescript
const tools = [
  {
    name: 'calculator',
    description: 'Performs arithmetic operations',
    parameters: {
      type: 'object',
      properties: {
        operation: {
          type: 'string',
          enum: ['add', 'subtract', 'multiply', 'divide']
        },
        a: { type: 'number' },
        b: { type: 'number' },
      },
      required: ['operation', 'a', 'b'],
    },
  },
];

// Bind tools to cascade
const boundCascade = cascade.bindTools(tools);

const result = await boundCascade.invoke(
  'What is 15 plus 27?'
);

// Result includes tool calls
console.log(result.tool_calls);
```

**Safety policy (default):**
- Low/medium-risk tool calls are accepted without running the verifier (even if `content` is empty).
- High/critical-risk tool calls force a verifier run before returning a tool call.

Tool risk is classified from tool `name` and `description` (examples: `delete_user`, `send_email`, `payment`, `deploy_production`).

### 3.5 Multi-Agent + LangGraph (Optional)

If you already use LangGraph for multi-agent systems, CascadeFlow can be used as the shared chat model inside nodes/sub-agents.

- TypeScript example: `packages/langchain-cascadeflow/examples/langgraph-multi-agent.ts`
- Python example: `examples/langchain_langgraph_multi_agent.py`

### 3. Structured Output

Extract structured data with schemas:

```typescript
const userSchema = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    age: { type: 'number' },
    email: { type: 'string' },
  },
  required: ['name', 'age'],
};

const structuredCascade = cascade.withStructuredOutput(userSchema);

const result = await structuredCascade.invoke(
  'Extract info: John Smith is 28 years old. Email: john@example.com'
);

// { name: 'John Smith', age: 28, email: 'john@example.com' }
```

### 4. Batch Processing

Process multiple inputs efficiently:

```typescript
const questions = [
  'What is 2+2?',
  'What is the speed of light?',
  'Who wrote Romeo and Juliet?',
];

const results = await cascade.batch(questions);

results.forEach((result, i) => {
  console.log(`Q: ${questions[i]}`);
  console.log(`A: ${result.content}\n`);
});
```

### 5. LCEL Composition Patterns

See runnable examples:
- TypeScript: `packages/langchain-cascadeflow/examples/lcel-pipeline.ts`
- Python: `examples/langchain_lcel_pipeline.py`

**Sequential Chains:**
```typescript
import { RunnableSequence } from '@langchain/core/runnables';

const chain = RunnableSequence.from([
  prompt,
  cascade,
  new StringOutputParser(),
]);
```

**Parallel Branches:**
```typescript
import { RunnablePassthrough } from '@langchain/core/runnables';

const chain = RunnablePassthrough.assign({
  answer: cascade.pipe(new StringOutputParser()),
  context: () => 'Generated by cascadeflow',
});

const result = await chain.invoke('What is AI?');
// { answer: '...', context: 'Generated by cascadeflow' }
```

**Complex Patterns:**
```typescript
// Multi-step reasoning
const analysisChain = RunnableSequence.from([
  // Step 1: Analyze
  RunnablePassthrough.assign({
    analysis: cascade.pipe(new StringOutputParser()),
  }),
  // Step 2: Summarize
  (input) => ({
    question: input.question,
    analysis: input.analysis,
    prompt: `Summarize this analysis: ${input.analysis}`,
  }),
  // Step 3: Summary
  RunnablePassthrough.assign({
    summary: cascade.pipe(new StringOutputParser()),
  }),
]);
```

### 6. LangSmith Integration

CascadeFlow adds LangSmith-friendly `tags` and `metadata` to nested drafter/verifier runs so traces are searchable by:
- `cascadeflow:drafter`, `cascadeflow:verifier`
- `cascadeflow:direct`, `cascadeflow:escalated`
- `cascadeflow:toolrisk=HIGH|CRITICAL|...` (when tool calls occur)

Automatic cost tracking metadata:

```typescript
// Metadata is automatically injected into responses
const result = await cascade.invoke('test');

// Access via response_metadata
console.log(result.response_metadata.cascade);
/*
{
  route: 'drafter',
  model: 'gpt-4o-mini',
  estimated_cost: 0.00015,
  quality_score: 0.85
}
*/
```

View in LangSmith traces:
1. Open LangSmith dashboard
2. View trace for your request
3. Check metadata for cost breakdown
4. Track savings over time

---

## Use Cases

### 1. Customer Support Chatbot

```typescript
import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '@cascadeflow/langchain';
import { PromptTemplate } from '@langchain/core/prompts';

const supportPrompt = PromptTemplate.fromTemplate(`
You are a helpful customer support agent.
Previous context: {context}
User question: {question}

Provide a clear, helpful answer.
`);

const cascade = withCascade({
  drafter: new ChatOpenAI({ modelName: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ modelName: 'gpt-4o' }),
  qualityThreshold: 0.85, // Most queries use cheap model
});

const chain = supportPrompt.pipe(cascade);

// Simple questions → drafter (cheap)
await chain.invoke({
  context: '',
  question: 'What are your business hours?',
});

// Complex questions → verifier (expensive)
await chain.invoke({
  context: 'User has account issues',
  question: 'How do I recover my account with 2FA enabled?',
});
```

**Savings:** 70-80% cost reduction on support queries

### 2. Document Q&A with RAG

```typescript
import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '@cascadeflow/langchain';
import { PromptTemplate } from '@langchain/core/prompts';
import { StringOutputParser } from '@langchain/core/output_parsers';

const ragPrompt = PromptTemplate.fromTemplate(`
Context: {context}

Question: {question}

Answer based on the context above.
`);

const cascade = withCascade({
  drafter: new ChatOpenAI({ modelName: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ modelName: 'gpt-4o' }),
  qualityThreshold: 0.8,
});

const chain = ragPrompt
  .pipe(cascade)
  .pipe(new StringOutputParser());

const answer = await chain.invoke({
  context: retrievedDocs,
  question: userQuestion,
});
```

**Savings:** 60-75% cost reduction on RAG applications

### 3. Data Extraction Pipeline

```typescript
const extractionSchema = {
  type: 'object',
  properties: {
    entities: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          type: { type: 'string' },
          confidence: { type: 'number' },
        },
      },
    },
  },
};

const cascade = withCascade({
  drafter: new ChatOpenAI({ modelName: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ modelName: 'gpt-4o' }),
});

const extractor = cascade.withStructuredOutput(extractionSchema);

// Batch process documents
const documents = [...]; // Your documents
const results = await extractor.batch(
  documents.map(doc => `Extract entities from: ${doc}`)
);
```

**Savings:** 50-70% cost reduction on extraction tasks

### 4. Code Review Assistant

```typescript
const codeReviewPrompt = PromptTemplate.fromTemplate(`
Review this code for best practices, bugs, and improvements:

{code}

Provide:
1. Issues found (if any)
2. Suggested improvements
3. Overall assessment
`);

const cascade = withCascade({
  drafter: new ChatOpenAI({ modelName: 'gpt-4o-mini' }),
  verifier: new ChatOpenAI({ modelName: 'gpt-4o' }),
  qualityThreshold: 0.75, // More critical task
});

const chain = codeReviewPrompt.pipe(cascade);

const review = await chain.invoke({ code: userCode });
```

**Savings:** 60-70% cost reduction on code reviews

---

## Best Practices

### 1. Choose the Right Quality Threshold

```typescript
// High-volume, low-stakes
const chatbot = withCascade({
  drafter, verifier,
  qualityThreshold: 0.9, // 90% use drafter
});

// Critical business logic
const criticalAnalysis = withCascade({
  drafter, verifier,
  qualityThreshold: 0.6, // 60% use drafter
});
```

### 2. Monitor with LangSmith

```typescript
import { LangChainTracer } from 'langchain/callbacks';

const tracer = new LangChainTracer({
  projectName: 'my-cascade-project',
});

const result = await cascade.invoke('test', {
  callbacks: [tracer],
});

// View traces in LangSmith dashboard
// Track: route decisions, costs, quality scores
```

### 3. Custom Quality Checks

```typescript
const cascade = withCascade({
  drafter,
  verifier,
  qualityCheck: async (response) => {
    // Custom logic
    const content = response.content.toString();

    // Check length
    if (content.length < 50) return 0.5;

    // Check for specific keywords
    if (content.includes('I don\'t know')) return 0.3;

    // Check for citations
    if (content.match(/\[\d+\]/)) return 0.9;

    return 0.8; // Default score
  },
});
```

### 4. Optimize Model Selection

**For Simple Tasks:**
```typescript
// Use smallest models
const drafter = new ChatOpenAI({ modelName: 'gpt-4o-mini' });
const verifier = new ChatOpenAI({ modelName: 'gpt-4o-mini' }); // Same model
// Set high threshold
qualityThreshold: 0.95
```

**For Complex Tasks:**
```typescript
// Use model gap
const drafter = new ChatOpenAI({ modelName: 'gpt-4o-mini' });
const verifier = new ChatOpenAI({ modelName: 'o1-preview' }); // Most powerful
// Set moderate threshold
qualityThreshold: 0.7
```

### 5. Streaming Best Practices

```typescript
// Pre-route for consistent streaming
const stream = await cascade.stream(input, {
  // Optional: Force drafter for known simple queries
  metadata: { force_drafter: true },
});

for await (const chunk of stream) {
  // Handle chunks
  process.stdout.write(chunk.content);
}
```

---

## Troubleshooting

### Issue: Too Many Verifier Calls

**Symptom:** Higher costs than expected

**Solution 1:** Increase quality threshold
```typescript
const cascade = withCascade({
  drafter, verifier,
  qualityThreshold: 0.85, // Increased from 0.8
});
```

**Solution 2:** Improve drafter model
```typescript
// Use better drafter
const drafter = new ChatOpenAI({
  modelName: 'gpt-4o-mini',
  temperature: 0.3, // More deterministic
});
```

**Solution 3:** Add custom quality check
```typescript
qualityCheck: async (response) => {
  // More lenient check
  return 0.9; // Accept most responses
}
```

### Issue: Tools Not Working

**Symptom:** Tool calls not appearing

**Solution:** Ensure models support tools
```typescript
// ✅ Good - models support tools
const drafter = new ChatOpenAI({ modelName: 'gpt-4o-mini' });
const verifier = new ChatOpenAI({ modelName: 'gpt-4o' });

// ❌ Bad - model doesn't support tools
const drafter = new ChatOpenAI({ modelName: 'gpt-3.5-turbo' });
```

### Issue: Streaming Not Working

**Symptom:** No chunks received

**Solution:** Check model streaming support
```typescript
// Ensure both models support streaming
const drafter = new ChatOpenAI({
  modelName: 'gpt-4o-mini',
  streaming: true, // Enable streaming
});
```

### Issue: Type Errors with LCEL

**Symptom:** TypeScript errors in chains

**Solution:** Use explicit types
```typescript
import type { Runnable } from '@langchain/core/runnables';

const cascade: Runnable = withCascade({
  drafter, verifier,
});

const chain = cascade.pipe(new StringOutputParser());
```

### Issue: Metadata Not Appearing

**Symptom:** No cascade metadata in responses

**Solution:** Check response_metadata
```typescript
const result = await cascade.invoke('test');

// Access metadata correctly
console.log(result.response_metadata?.cascade);

// Not result.metadata (wrong)
```

---

## Performance Metrics

Real-world results from production usage:

| Use Case | Drafter Usage | Cost Savings | Latency Improvement |
|----------|---------------|--------------|---------------------|
| Customer Support | 82% | 75% | +15% faster |
| Document Q&A | 73% | 65% | +20% faster |
| Data Extraction | 68% | 58% | +10% faster |
| Code Review | 71% | 63% | +18% faster |

---

## Next Steps

1. **Examples**: Check the `examples/` directory for more patterns
2. **API Reference**: See the [package README](../../packages/langchain-cascadeflow/README.md)
3. **LangSmith**: Set up tracing for cost monitoring
4. **Production**: Read the [production guide](./production.md)

---

## Additional Resources

- [LangChain Documentation](https://js.langchain.com/)
- [cascadeflow Core Guide](../README.md)
- [Cost Optimization Guide](./cost_tracking.md)
- [Performance Guide](./performance.md)

---

**Questions or Issues?**
- GitHub: [cascadeflow Issues](https://github.com/lemony-ai/cascadeflow/issues)
- Email: hello@lemony.ai
