# TypeScript Development Roadmap

Strategic plan for bringing `@cascadeflow/core` to feature parity with the Python library.

---

## 🎯 Recommended Priority Order

### **Phase 1 (v0.2.0): Essential UX** - Ship in 1-2 weeks
Focus: Make TypeScript competitive for modern applications

1. **Streaming Support** ⭐⭐⭐⭐⭐ CRITICAL
2. **Basic Quality Validation** ⭐⭐⭐⭐⭐ CRITICAL
3. **Tool Execution** ⭐⭐⭐⭐ HIGH

### **Phase 2 (v0.3.0): Production Ready** - Ship in 4-6 weeks
Focus: Enable production deployments

4. **Telemetry & Metrics** ⭐⭐⭐ MEDIUM
5. **Complexity Detection** ⭐⭐⭐ MEDIUM
6. **Basic Routing** ⭐⭐⭐ MEDIUM

### **Phase 3 (v0.4.0): Advanced Features** - Ship in 8-12 weeks
Focus: Match Python capabilities

7. **Callbacks System** ⭐⭐ LOW
8. **Response Caching** ⭐⭐ LOW
9. **Presets & Auto-Detection** ⭐⭐ LOW

---

## 📋 Phase 1 Details (v0.2.0)

### 1. **Streaming Support** - ✅ COMPLETE ⭐⭐⭐⭐⭐

**Status:** Implemented in v0.2.0 (2025-10-23)

**What Was Implemented:**
- ✅ `StreamEvent` types (ROUTING, CHUNK, DRAFT_DECISION, SWITCH, COMPLETE, ERROR)
- ✅ `CascadeAgent.runStream()` method with AsyncIterator support
- ✅ Provider streaming for OpenAI, Anthropic, Groq (both Node.js SDK + browser fetch)
- ✅ SSE (Server-Sent Events) parsing for browser environments
- ✅ Helper functions: `collectStream()`, `collectResult()`, event type guards
- ✅ Comprehensive example in `examples/streaming.ts`
- ✅ Full cascade streaming (draft → validate → switch to verifier if needed)

**Why First:**
- ✅ Users expect streaming in 2024 (ChatGPT, Claude all stream)
- ✅ Essential for browser/frontend UX (show progress, not blocking)
- ✅ Differentiates TypeScript (Python streaming works in terminal, TS in browser)
- ✅ Relatively straightforward to implement
- ✅ High perceived value (users see tokens appearing)

**Technical Approach (As Implemented):**
```typescript
// Return AsyncIterator for streaming
async *runStream(
  input: string,
  options?: RunOptions
): AsyncIterableIterator<StreamEvent> {
  // Stream from provider
  const provider = getProvider(model);

  for await (const chunk of provider.stream(request)) {
    yield {
      type: 'token',
      content: chunk.content,
      model: model.name,
      ...
    };
  }
}

// Usage:
for await (const event of agent.runStream('Hello')) {
  console.log(event.content); // Progressive output
}
```

**Effort:** 2-3 days
- Port `streaming/base.py` logic
- Implement for OpenAI (easy), Anthropic (easy), Groq (easy)
- Add TypeScript types for `StreamEvent`
- Update providers to support streaming

**Value:** 🔥🔥🔥🔥🔥 Game changer for UX

---

### 2. **Basic Quality Validation** - SECOND ⭐⭐⭐⭐⭐

**Why Second:**
- ✅ Core to cascading value proposition
- ✅ Without it, cascading is dumb ("try cheap, always escalate")
- ✅ Enables intelligent escalation decisions
- ✅ Python implementation is well-tested
- ✅ Can start simple, add sophistication later

**What to Add:**

**2a. Confidence Scoring (via logprobs)**
```typescript
interface ConfidenceScore {
  score: number; // 0-1
  method: 'logprobs' | 'heuristic';
  details?: {
    avgLogprob?: number;
    minLogprob?: number;
  };
}

// Extract from OpenAI/Anthropic response
function calculateConfidence(response: ProviderResponse): ConfidenceScore {
  if (response.logprobs) {
    const avgLogprob = average(response.logprobs);
    return {
      score: logprobToConfidence(avgLogprob),
      method: 'logprobs',
      details: { avgLogprob }
    };
  }

  // Fallback: heuristic based on length, repetition
  return heuristicConfidence(response.content);
}
```

**2b. Quality Thresholds**
```typescript
interface QualityConfig {
  minConfidence: number; // 0-1, default 0.7
  requireValidation: boolean; // default true
  escalateOnLowConfidence: boolean; // default true
}

// Decide if draft is good enough
function shouldEscalate(
  draftResponse: Response,
  config: QualityConfig
): boolean {
  const confidence = calculateConfidence(draftResponse);
  return confidence.score < config.minConfidence;
}
```

**Effort:** 3-4 days
- Port confidence scoring from `quality/confidence.py`
- Add logprobs extraction for each provider
- Implement quality thresholds
- Update cascade logic to use validation

**Value:** 🔥🔥🔥🔥🔥 Makes cascading actually smart

---

### 3. **Tool Execution** - THIRD ⭐⭐⭐⭐

**Why Third:**
- ✅ TypeScript already supports tool *definitions*
- ✅ Just need execution layer to make them useful
- ✅ High value for agentic workflows
- ✅ Relatively simple to implement
- ✅ Great for n8n integration

**Technical Approach:**
```typescript
interface ToolExecutor {
  execute(toolCall: ToolCall): Promise<ToolResult>;
}

class DefaultToolExecutor implements ToolExecutor {
  private tools: Map<string, ToolFunction>;

  async execute(toolCall: ToolCall): Promise<ToolResult> {
    const func = this.tools.get(toolCall.name);
    if (!func) {
      throw new Error(`Tool not found: ${toolCall.name}`);
    }

    try {
      const result = await func(toolCall.arguments);
      return {
        success: true,
        result,
        toolCallId: toolCall.id
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        toolCallId: toolCall.id
      };
    }
  }
}

// Usage:
const tools = [
  {
    name: 'get_weather',
    description: 'Get weather for a location',
    parameters: { /* schema */ },
    execute: async (args) => {
      // Actual implementation
      return await weatherAPI.get(args.location);
    }
  }
];

const result = await agent.run('What\'s the weather?', { tools });
// Tools are automatically executed
```

**Effort:** 2-3 days
- Port `tools/executor.py` logic
- Add tool execution to cascade flow
- Handle multi-turn conversations
- Add error handling

**Value:** 🔥🔥🔥🔥 Enables agentic workflows

---

## 📊 Phase 1 Impact Summary

**Before Phase 1:**
- Basic cascading only
- Blocking responses
- No intelligence in routing
- Tool definitions but no execution

**After Phase 1 (Partial - Streaming Complete):**
- ✅ Progressive streaming (modern UX) - **COMPLETE**
- ⏳ Smart escalation based on quality - **IN PROGRESS** (basic heuristic implemented)
- ⏳ Full tool execution (agentic) - **PENDING**
- ✨ TypeScript becomes usable for real apps

**Current Status:**
- ✅ Streaming: COMPLETE (1/3 features)
- ⏳ Quality Validation: Basic heuristic (needs logprobs support)
- ❌ Tool Execution: Not started

**Time Spent:** 1 day (streaming implementation)
**Time Remaining:** 6-9 days (quality validation + tool execution)
**Bundle Size Impact:** +~15KB for streaming (~85KB total)
**Feature Parity:** ~8% (up from 3%, streaming adds 5%)

---

## 📋 Phase 2 Details (v0.3.0)

### 4. **Telemetry & Metrics** ⭐⭐⭐

**What to Add:**
```typescript
interface Metrics {
  // Per-request metrics
  totalRequests: number;
  totalCost: number;
  totalTokens: number;
  avgLatency: number;

  // Cascade metrics
  draftAcceptRate: number; // % of drafts accepted
  avgSavings: number; // Average savings %

  // Model usage
  modelUsage: Map<string, {
    requests: number;
    cost: number;
    avgLatency: number;
  }>;
}

class MetricsCollector {
  track(result: CascadeResult): void;
  getMetrics(): Metrics;
  reset(): void;
}
```

**Effort:** 2-3 days
**Value:** 🔥🔥🔥 Enables production monitoring

---

### 5. **Complexity Detection** ⭐⭐⭐

**What to Add:**
```typescript
enum QueryComplexity {
  TRIVIAL = 'trivial',      // "What's 2+2?"
  SIMPLE = 'simple',        // "Explain Python lists"
  MODERATE = 'moderate',    // "Write a function..."
  COMPLEX = 'complex',      // "Design a system..."
  VERY_COMPLEX = 'very_complex' // "Analyze this codebase..."
}

class ComplexityDetector {
  detect(query: string): QueryComplexity {
    // Heuristics:
    // - Length
    // - Keywords (design, analyze, create, etc.)
    // - Question marks
    // - Code blocks
    return complexity;
  }
}
```

**Effort:** 2 days
**Value:** 🔥🔥🔥 Smarter routing

---

### 6. **Basic Routing** ⭐⭐⭐

**What to Add:**
```typescript
interface Router {
  selectModel(
    query: string,
    models: ModelConfig[],
    complexity: QueryComplexity
  ): ModelConfig;
}

class ComplexityRouter implements Router {
  selectModel(query, models, complexity) {
    // Route based on complexity:
    // TRIVIAL/SIMPLE → cheapest model
    // MODERATE → mid-tier model
    // COMPLEX → expensive model

    if (complexity <= QueryComplexity.SIMPLE) {
      return models[0]; // Cheapest
    }

    if (complexity === QueryComplexity.COMPLEX) {
      return models[models.length - 1]; // Most expensive
    }

    return models[Math.floor(models.length / 2)]; // Middle
  }
}
```

**Effort:** 2-3 days
**Value:** 🔥🔥🔥 Intelligent routing

---

## 📊 Phase 2 Impact Summary

**After Phase 2:**
- ✨ Production monitoring (metrics)
- ✨ Smart routing (complexity-based)
- ✨ Cost tracking
- ✨ Performance analytics

**Estimated Time:** 6-8 days total
**Bundle Size Impact:** +~30KB (~130KB total)
**Feature Parity:** ~30% (up from 15%)

---

## 📋 Phase 3 Details (v0.4.0)

### 7. **Callbacks System** ⭐⭐
- Event hooks (onStart, onComplete, onError)
- Real-time monitoring
- Custom integrations

### 8. **Response Caching** ⭐⭐
- Cache identical queries
- TTL-based expiration
- Cost savings on repeated queries

### 9. **Presets & Auto-Detection** ⭐⭐
- Pre-configured cascades
- Auto-detect available models
- Quick setup

**Estimated Time:** 8-10 days total
**Feature Parity:** ~50%

---

## 🎯 Strategic Recommendations

### **Start Immediately:**
1. **Streaming** (Week 1)
   - Biggest UX impact
   - Essential for modern apps
   - Differentiates from Python

2. **Quality Validation** (Week 2)
   - Core value proposition
   - Makes cascading intelligent
   - Well-defined in Python

3. **Tool Execution** (Week 2-3)
   - Completes tool calling story
   - Enables agentic workflows
   - Straightforward implementation

### **Target Timeline:**
- **v0.2.0**: 2-3 weeks (Phase 1)
- **v0.3.0**: 6-8 weeks (Phase 2)
- **v0.4.0**: 12-16 weeks (Phase 3)
- **v1.0.0**: 20-24 weeks (Full parity)

---

## 💡 Why This Order?

### User Experience First
- Streaming immediately improves perceived performance
- Quality validation makes cascading actually work
- Tool execution enables real applications

### Build on Foundations
- Each phase builds on previous
- No major refactoring needed
- Incremental value delivery

### Market Positioning
- v0.2.0: "Modern, streaming-capable cascading"
- v0.3.0: "Production-ready with monitoring"
- v0.4.0: "Feature-rich, Python parity"

---

## 📊 Comparison: TypeScript Versions

| Feature | v0.1.0 | v0.2.0 (Current) | v0.3.0 (Planned) | v0.4.0 (Planned) |
|---------|--------|--------|--------|--------|
| Basic Cascade | ✅ | ✅ | ✅ | ✅ |
| 7 Providers | ✅ | ✅ | ✅ | ✅ |
| Streaming | ❌ | ✅ **NEW** | ✅ | ✅ |
| Quality Check | ❌ | ⏳ Basic | ✅ Full | ✅ Full |
| Tool Execution | ❌ | ⏳ Pending | ✅ | ✅ |
| Metrics | ❌ | ❌ | ✅ | ✅ |
| Routing | ❌ | ❌ | ✅ | ✅ |
| Callbacks | ❌ | ❌ | ❌ | ✅ |
| Caching | ❌ | ❌ | ❌ | ✅ |
| **Lines of Code** | 772 | ~1,200 | ~2,500 | ~4,000 |
| **Feature Parity** | 3% | 8% | 30% | 50% |
| **Bundle Size** | 50KB | 85KB | 130KB | 180KB |

---

## 🚀 Next Steps

### Immediate Actions:
1. ✅ Create this roadmap (done!)
2. ✅ Start streaming implementation (done! 2025-10-23)
3. ⏭️ **NEXT:** Port quality validation logic (with logprobs support)
4. ⏭️ Add tool execution

### Development Process:
- Reference Python implementation
- Adapt for TypeScript/JavaScript patterns
- Maintain type safety
- Keep bundle size small
- Test in browser + Node.js

### Success Metrics:
- Bundle size stays < 200KB
- All features work in browser
- API remains simple
- Type safety maintained
- Performance competitive with Python

---

## 📝 Notes

### Why Not Advanced Features First?
- Streaming/quality/tools have immediate user impact
- Advanced routing/telemetry are "nice to have"
- Better to ship incremental value than wait for perfect

### Why Not Full Parity?
- TypeScript bundle must stay lightweight
- Some Python features (visual UI) don't make sense in browser
- Focus on 80/20: implement 20% of features that deliver 80% of value

### Future Considerations:
- React hooks for streaming (`useCascade()`)
- Svelte stores integration
- Vue composables
- Framework-agnostic core

---

**Document Version**: 1.1
**Last Updated**: 2025-10-23
**Status**: Phase 1 - Streaming Complete (1/3 features done)
