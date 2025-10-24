# Advanced Routing Strategies for CascadeFlow

This guide covers advanced routing patterns for optimizing your AI model cascades based on different use cases and requirements.

## Table of Contents

1. [Cost-First Routing](#cost-first-routing)
2. [Quality-First Routing](#quality-first-routing)
3. [Speed-First Routing](#speed-first-routing)
4. [Domain-Specific Routing](#domain-specific-routing)
5. [Adaptive Routing](#adaptive-routing)
6. [Multi-Tier Cascades](#multi-tier-cascades)

---

## Cost-First Routing

**Use Case**: Maximize cost savings while maintaining acceptable quality

**Strategy**: Start with the cheapest model, escalate only when quality is insufficient

```typescript
const agent = new CascadeAgent({
  models: [
    // Tier 1: Ultra-cheap (Groq free tier)
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },

    // Tier 2: Budget option
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },

    // Tier 3: Quality fallback
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
  quality: {
    threshold: 0.6, // Lower threshold = more cost savings
    requireMinimumTokens: 5,
  },
});
```

**Expected Savings**: 75-95%

**Best For**:
- High-volume applications
- Simple queries (FAQs, translations, summaries)
- Non-critical responses
- MVP/prototyping

---

## Quality-First Routing

**Use Case**: Prioritize response quality over cost

**Strategy**: Use high-quality drafters with strict quality validation

```typescript
const agent = new CascadeAgent({
  models: [
    // Tier 1: High-quality drafter
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },

    // Tier 2: Premium verifier
    { name: 'claude-sonnet-4-5-20250929', provider: 'anthropic', cost: 0.009 },

    // Tier 3: Ultimate fallback (reasoning model)
    { name: 'o1-mini', provider: 'openai', cost: 0.003 },
  ],
  quality: {
    threshold: 0.85, // Higher threshold = more quality focus
    requireMinimumTokens: 20,
  },
});
```

**Expected Savings**: 30-50%

**Best For**:
- Customer-facing content
- Technical documentation
- Code generation
- Professional writing
- Legal/medical content

---

## Speed-First Routing

**Use Case**: Minimize latency for real-time applications

**Strategy**: Use ultra-fast providers with minimal cascading

```typescript
const agent = new CascadeAgent({
  models: [
    // Tier 1: Groq (fastest in the industry)
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },

    // Tier 2: OpenAI (fast and reliable)
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
  ],
  quality: {
    threshold: 0.5, // Lower threshold = less escalation = faster
    requireMinimumTokens: 3,
  },
});

// For streaming responses
for await (const event of agent.runStream(query)) {
  if (event.type === 'chunk') {
    // Stream to user immediately
    process.stdout.write(event.content);
  }
}
```

**Expected Latency**:
- Groq: 50-200ms TTFT (Time To First Token)
- OpenAI: 200-500ms TTFT

**Best For**:
- Chatbots
- Live customer support
- Real-time code completion
- Interactive applications

---

## Domain-Specific Routing

**Use Case**: Route based on query type or domain

**Strategy**: Use different cascades for different query categories

```typescript
// Coding queries → GPT-5 (excels at coding)
const codingAgent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
});

// General queries → Claude (best overall reasoning)
const generalAgent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'claude-sonnet-4-5-20250929', provider: 'anthropic', cost: 0.009 },
  ],
});

// Creative writing → Claude (better at creative tasks)
const creativeAgent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'claude-sonnet-4-5-20250929', provider: 'anthropic', cost: 0.009 },
  ],
  quality: {
    threshold: 0.8, // Higher quality for creative content
  },
});

async function routeQuery(query: string) {
  if (query.includes('code') || query.includes('function') || query.includes('debug')) {
    return codingAgent.run(query);
  } else if (query.includes('write') || query.includes('story') || query.includes('creative')) {
    return creativeAgent.run(query);
  } else {
    return generalAgent.run(query);
  }
}
```

**Best For**:
- Applications with diverse query types
- Multi-purpose AI assistants
- Specialized workflows

---

## Adaptive Routing

**Use Case**: Adjust routing based on real-time performance

**Strategy**: Track success rates and adjust thresholds dynamically

```typescript
class AdaptiveRouter {
  private draftAcceptanceRate = 0.7;
  private threshold = 0.7;
  private recentResults: boolean[] = [];
  private maxHistory = 100;

  async run(agent: CascadeAgent, query: string) {
    const result = await agent.run(query);

    // Track draft acceptance
    this.recentResults.push(result.draftAccepted);
    if (this.recentResults.length > this.maxHistory) {
      this.recentResults.shift();
    }

    // Calculate acceptance rate
    const acceptedCount = this.recentResults.filter(a => a).length;
    this.draftAcceptanceRate = acceptedCount / this.recentResults.length;

    // Adjust threshold based on acceptance rate
    if (this.draftAcceptanceRate < 0.5) {
      // Too many escalations → lower threshold
      this.threshold = Math.max(0.5, this.threshold - 0.05);
      console.log(`📉 Lowered threshold to ${this.threshold}`);
    } else if (this.draftAcceptanceRate > 0.9) {
      // Too few escalations → raise threshold
      this.threshold = Math.min(0.9, this.threshold + 0.05);
      console.log(`📈 Raised threshold to ${this.threshold}`);
    }

    return result;
  }

  getStats() {
    return {
      draftAcceptanceRate: this.draftAcceptanceRate,
      currentThreshold: this.threshold,
    };
  }
}
```

**Best For**:
- Long-running applications
- Variable query complexity
- Production optimization

---

## Multi-Tier Cascades

**Use Case**: Maximize savings with multiple fallback tiers

**Strategy**: Use 3+ models with increasing cost and quality

### Three-Tier Cascade

```typescript
const agent = new CascadeAgent({
  models: [
    // Tier 1: Free/ultra-cheap (Groq)
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },

    // Tier 2: Budget option (Claude Haiku)
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },

    // Tier 3: Premium fallback (GPT-5)
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
  ],
  quality: {
    threshold: 0.7,
  },
});
```

**Expected Flow**:
- 70% handled by Tier 1 ($0.00005)
- 25% escalated to Tier 2 ($0.0008)
- 5% escalated to Tier 3 ($0.00125)
- **Average cost: ~$0.00016** (87% savings vs using GPT-5 directly)

### Five-Tier Cascade (Maximum Savings)

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
    { name: 'claude-sonnet-4-5-20250929', provider: 'anthropic', cost: 0.009 },
  ],
});
```

**Expected Savings**: 90-95%

**Trade-offs**:
- More complexity
- Slightly higher latency
- Better for batch processing than real-time

---

## Routing Decision Tree

```
┌─────────────────────┐
│   Query Received    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ What's the priority?│
└──────────┬──────────┘
           │
     ┌─────┴──────┬───────────┬──────────┐
     ▼            ▼           ▼          ▼
┌────────┐  ┌─────────┐  ┌──────┐  ┌────────┐
│  Cost  │  │ Quality │  │Speed │  │Adaptive│
└────┬───┘  └────┬────┘  └──┬───┘  └───┬────┘
     │           │           │          │
     ▼           ▼           ▼          ▼
  3-5 tiers   High-qual   Fast      Dynamic
  Low thresh  High thresh providers  adjustment
  Max savings Best output Low latency Learn & adapt
```

---

## Choosing the Right Strategy

| Use Case | Strategy | Models | Threshold | Savings |
|----------|----------|--------|-----------|---------|
| MVP/Prototype | Cost-First | Groq → GPT-5 | 0.6 | 90-95% |
| Production App | Recommended | Claude Haiku → GPT-5 | 0.7 | 50-65% |
| Customer Support | Speed-First | Groq → OpenAI | 0.5 | 70-80% |
| Code Generation | Quality-First | GPT-4o-mini → GPT-5 | 0.85 | 30-40% |
| Content Writing | Quality-First | Claude Haiku → Sonnet | 0.85 | 30-50% |
| Batch Processing | Multi-Tier | 5-tier cascade | 0.7 | 90-95% |

---

## Advanced Configuration Examples

### Context-Aware Routing

```typescript
async function contextAwareRouting(query: string, context: string) {
  // Short queries → fast models
  if (query.length < 100) {
    return new CascadeAgent({
      models: [
        { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
      ],
    });
  }

  // Long queries with code → GPT-5
  if (query.length > 500 || query.includes('```')) {
    return new CascadeAgent({
      models: [
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
        { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
      ],
      quality: { threshold: 0.8 },
    });
  }

  // Default: balanced
  return new CascadeAgent({
    models: [
      { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
      { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
    ],
  });
}
```

### Time-of-Day Routing

```typescript
function getTimeBasedAgent() {
  const hour = new Date().getHours();

  // Night time (low traffic) → use slower but cheaper models
  if (hour >= 22 || hour < 6) {
    return new CascadeAgent({
      models: [
        { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
      ],
    });
  }

  // Peak hours → optimize for speed
  return new CascadeAgent({
    models: [
      { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
      { name: 'gpt-5', provider: 'openai', cost: 0.00125 },
    ],
    quality: { threshold: 0.5 }, // Lower threshold for speed
  });
}
```

---

## Monitoring & Optimization

Track these metrics to optimize your routing:

```typescript
interface RoutingMetrics {
  draftAcceptanceRate: number;     // % of queries accepted by drafter
  averageCost: number;              // Average cost per query
  averageLatency: number;           // Average response time
  escalationRate: number;           // % of queries escalated
  savingsPercentage: number;        // Total savings vs direct model
}
```

**Optimization Guidelines**:

- **If draft acceptance < 50%**: Lower quality threshold OR use better drafter
- **If average latency > 2s**: Use faster providers (Groq) OR lower threshold
- **If savings < 30%**: Add cheaper tier OR adjust threshold
- **If quality complaints**: Raise threshold OR use better verifier

---

## Summary

| Strategy | Complexity | Setup Time | Maintenance | Savings | Quality |
|----------|-----------|------------|-------------|---------|---------|
| Cost-First | Low | 5 min | Low | 90-95% | Medium |
| Quality-First | Low | 5 min | Low | 30-50% | High |
| Speed-First | Low | 5 min | Low | 70-80% | Medium |
| Domain-Specific | Medium | 30 min | Medium | 50-70% | High |
| Adaptive | High | 2 hours | High | 60-80% | High |
| Multi-Tier | Medium | 15 min | Medium | 90-95% | Medium-High |

**Recommended Starting Point**: Claude Haiku (drafter) + GPT-5 (verifier) with threshold=0.7

This provides an excellent balance of cost (50-65% savings), quality, and simplicity.
