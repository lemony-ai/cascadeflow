# CascadeFlow Integrations Architecture

**Date**: October 22, 2025
**Status**: Planning Phase
**First Integration**: n8n Community Node
**Planned**: LangChain, LlamaIndex, Haystack, AutoGen

---

## 🎯 Vision

Create a scalable, modular integration system that makes CascadeFlow accessible across all major AI development platforms. Each integration should:

1. **Be Easy to Use** - Drop-in replacement for existing LLM nodes/integrations
2. **Show Value Immediately** - Display cost savings and metrics prominently
3. **Scale with Complexity** - Simple default, powerful when extended
4. **Maintain Independence** - Each integration is self-contained and versioned separately
5. **Share Core Logic** - Leverage CascadeFlow core without duplication

---

## 📁 Directory Structure

### Proposed Architecture

```
cascadeflow/                         # Main Python package (existing)
├── core/
├── providers/
├── quality/
├── routing/
├── telemetry/
├── tools/
└── ...

integrations/                        # NEW: All third-party integrations
├── README.md                        # Integration catalog and overview
├── n8n-nodes-cascadeflow/          # n8n community node (npm package)
│   ├── package.json
│   ├── nodes/
│   │   └── CascadeFlow/
│   │       ├── CascadeFlow.node.ts
│   │       ├── CascadeFlow.node.json
│   │       └── description.ts
│   ├── credentials/
│   │   └── CascadeFlowApi.credentials.ts
│   ├── icons/
│   │   └── cascadeflow.svg
│   ├── tests/
│   ├── README.md
│   └── docs/
│       ├── quickstart.md
│       ├── examples.md
│       └── metrics.md
│
├── langchain/                       # Python LangChain integration
│   ├── pyproject.toml
│   ├── cascadeflow_langchain/
│   │   ├── __init__.py
│   │   ├── llm.py                  # LangChain LLM wrapper
│   │   ├── chat_model.py           # Chat model wrapper
│   │   └── callbacks.py            # Cost tracking callbacks
│   ├── examples/
│   ├── tests/
│   └── README.md
│
├── llamaindex/                      # Python LlamaIndex integration (future)
│   └── ...
│
└── shared/                          # Shared integration utilities
    ├── metrics_formatter.py         # Standard metrics display
    ├── cost_display.py              # Cost comparison visuals
    └── common_types.py              # Shared type definitions
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Root-level `integrations/`** | Separate from core package, independent versioning |
| **One directory per integration** | Self-contained, can be developed/published independently |
| **Shared utilities** | Common logic (metrics, formatting) reused across integrations |
| **Language-specific structure** | n8n (TypeScript/npm), LangChain (Python/pip), etc. |
| **Separate README per integration** | Each integration is documented independently |

---

## 🔌 n8n Integration Design

### 1. Package Structure

**Name**: `n8n-nodes-cascadeflow`
**Type**: n8n Community Node (npm package)
**License**: MIT
**Repository**: `https://github.com/lemony-ai/cascadeflow` (monorepo)

```json
{
  "name": "n8n-nodes-cascadeflow",
  "version": "1.0.0",
  "description": "CascadeFlow AI model cascading for n8n - Save 60-98% on LLM costs",
  "license": "MIT",
  "author": {
    "name": "Lemony Inc.",
    "email": "hello@lemony.ai"
  },
  "repository": {
    "type": "git",
    "url": "https://github.com/lemony-ai/cascadeflow.git",
    "directory": "integrations/n8n-nodes-cascadeflow"
  },
  "main": "index.js",
  "keywords": [
    "n8n-community-node-package",
    "ai",
    "llm",
    "cost-optimization",
    "openai",
    "anthropic",
    "cascade"
  ],
  "n8n": {
    "nodes": [
      "dist/nodes/CascadeFlow/CascadeFlow.node.js"
    ],
    "credentials": [
      "dist/credentials/CascadeFlowApi.credentials.js"
    ]
  }
}
```

### 2. Node Design: "CascadeFlow" Node

#### Visual Design

```
┌─────────────────────────────────────────┐
│   🌊 CascadeFlow                        │
├─────────────────────────────────────────┤
│                                         │
│   Input:  Prompt/Messages ──────────►  │
│                                         │
│   ┌─────────────────────────────────┐  │
│   │ Configuration                   │  │
│   │                                 │  │
│   │ Mode: ⚙️ Simple Cascade         │  │
│   │                                 │  │
│   │ Drafter Model:                  │  │
│   │   ├─ Provider: OpenAI           │  │
│   │   ├─ Model: gpt-4o-mini         │  │
│   │   └─ Cost: $0.00015/1K tokens   │  │
│   │                                 │  │
│   │ Verifier Model:                 │  │
│   │   ├─ Provider: OpenAI           │  │
│   │   ├─ Model: gpt-5               │  │
│   │   └─ Cost: $0.0125/1K tokens    │  │
│   │                                 │  │
│   │ Quality Threshold: 0.75 ────────│  │
│   │                                 │  │
│   │ [Show Advanced Options ▼]       │  │
│   └─────────────────────────────────┘  │
│                                         │
│   Output: ◄────── Response + Metrics   │
│                                         │
│   💰 Cost Savings: $0.0112 (89%)       │
│   ⏱️  Latency: 120ms vs 856ms          │
│   ✅ Quality: Passed with drafter      │
│                                         │
└─────────────────────────────────────────┘
```

#### Operating Modes

**1. Simple Cascade (Default)** 🎯
- **What**: Two-tier cascade (drafter → verifier)
- **Config**: Just pick 2 models and quality threshold
- **Best For**: Most users (90% use case)
- **Example**:
  ```json
  {
    "mode": "simple",
    "drafter": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "cost": 0.00015
    },
    "verifier": {
      "provider": "openai",
      "model": "gpt-5",
      "cost": 0.0125
    },
    "qualityThreshold": 0.75
  }
  ```

**2. Advanced Cascade** ⚡
- **What**: Multi-tier cascade (3-6 models)
- **Config**: Array of models with custom routing rules
- **Best For**: Power users optimizing complex workflows
- **Example**:
  ```json
  {
    "mode": "advanced",
    "models": [
      {"provider": "groq", "model": "llama-3.1-8b", "cost": 0},
      {"provider": "openai", "model": "gpt-4o-mini", "cost": 0.00015},
      {"provider": "anthropic", "model": "claude-sonnet", "cost": 0.003},
      {"provider": "openai", "model": "gpt-5", "cost": 0.0125}
    ],
    "qualityConfig": {
      "confidenceThresholds": {"moderate": 0.75, "high": 0.85}
    }
  }
  ```

**3. Smart Agent Mode** 🤖
- **What**: Specialized drafter/validator pattern for tool calls
- **Config**: Separate models for routing vs execution
- **Best For**: AI agents with tool calling
- **Savings**: 70-80% on agent workloads
- **Example**:
  ```json
  {
    "mode": "agent",
    "toolSelector": {
      "provider": "groq",
      "model": "llama-3.1-8b",
      "cost": 0
    },
    "toolExecutor": {
      "provider": "openai",
      "model": "gpt-4o",
      "cost": 0.00625
    }
  }
  ```

**4. Local-First (Edge)** 🔌
- **What**: Try local models first, cascade to cloud
- **Config**: Local Ollama/vLLM + cloud fallback
- **Best For**: Privacy, offline, edge deployment
- **Example**:
  ```json
  {
    "mode": "edge",
    "localModel": {
      "provider": "ollama",
      "model": "llama3.2:1b",
      "cost": 0
    },
    "cloudFallback": {
      "provider": "openai",
      "model": "gpt-4o",
      "cost": 0.00625
    }
  }
  ```

### 3. Input/Output Schema

#### Input

```typescript
interface CascadeFlowInput {
  // Text input (simple queries)
  prompt?: string;

  // Or structured messages (chat format)
  messages?: Array<{
    role: "system" | "user" | "assistant";
    content: string;
  }>;

  // Tool calling support
  tools?: Array<{
    name: string;
    description: string;
    parameters: object;
  }>;

  // Streaming mode
  stream?: boolean;

  // Override quality threshold per request
  qualityThreshold?: number;

  // Force specific model (bypass cascade)
  forceModel?: string;
}
```

#### Output

```typescript
interface CascadeFlowOutput {
  // Response content
  content: string;

  // Metrics and cost tracking
  metrics: {
    modelUsed: string;
    providerUsed: string;
    totalCost: number;
    draftCost: number;
    verifierCost: number;
    costSaved: number;
    savingsPercentage: number;
    latencyMs: number;
    tokensUsed: {
      input: number;
      output: number;
    };
  };

  // Quality validation
  quality: {
    passed: boolean;
    confidence: number;
    cascaded: boolean;
    reason?: string;
  };

  // Tool calls (if any)
  toolCalls?: Array<{
    name: string;
    arguments: object;
  }>;

  // Original response (for debugging)
  _raw?: any;
}
```

### 4. Metrics Dashboard Panel

**Integrated Metrics Display** (shown below node after execution):

```
┌─────────────────────────────────────────────────────────┐
│ 💰 Cost Analysis                                        │
├─────────────────────────────────────────────────────────┤
│ This request:      $0.0003  (vs $0.0125 without)       │
│ Savings:           $0.0122  (97.6%)                     │
│ Model used:        gpt-4o-mini (drafter ✅)             │
│                                                         │
│ Session totals (last 100 requests):                    │
│ ├─ Total cost:     $0.47                               │
│ ├─ Would cost:     $12.50 (verifier-only)              │
│ ├─ Total saved:    $12.03 (96.2%)                      │
│ └─ Avg latency:    142ms (vs 856ms)                    │
│                                                         │
│ Quality breakdown:                                      │
│ ├─ Passed drafter:  87%  (gpt-4o-mini)                 │
│ ├─ Cascaded:        13%  (needed gpt-5)                │
│ └─ Avg confidence:  0.82                               │
└─────────────────────────────────────────────────────────┘
```

### 5. Credentials Setup

**CascadeFlowApi Credentials**:

```typescript
// credentials/CascadeFlowApi.credentials.ts
class CascadeFlowApi implements ICredentialType {
  name = 'cascadeFlowApi';
  displayName = 'CascadeFlow API';
  documentationUrl = 'https://docs.lemony.ai/cascadeflow/n8n';

  properties = [
    // OpenAI (required for default setup)
    {
      displayName: 'OpenAI API Key',
      name: 'openaiApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
    },

    // Optional providers
    {
      displayName: 'Anthropic API Key',
      name: 'anthropicApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'Optional - for Claude models',
    },
    {
      displayName: 'Groq API Key',
      name: 'groqApiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'Optional - for free Llama models',
    },

    // Local providers (no key needed)
    {
      displayName: 'Ollama Base URL',
      name: 'ollamaUrl',
      type: 'string',
      default: 'http://localhost:11434',
      description: 'Optional - for local Ollama models',
    },
    {
      displayName: 'vLLM Base URL',
      name: 'vllmUrl',
      type: 'string',
      default: 'http://localhost:8000/v1',
      description: 'Optional - for self-hosted vLLM',
    },
  ];
}
```

---

## 🚀 Implementation Plan

### Phase 1: MVP (Weeks 1-2)

**Goal**: Simple working n8n node

**Tasks**:
1. ✅ Set up `integrations/n8n-nodes-cascadeflow/` directory
2. ✅ Create package.json with n8n node config
3. ✅ Implement "Simple Cascade" mode only
4. ✅ Basic input/output handling (text only)
5. ✅ Metrics display (cost, model used, savings)
6. ✅ OpenAI provider support only (minimize complexity)
7. ✅ Local testing with n8n CLI
8. ✅ Documentation (README, quickstart)

**Deliverables**:
- Working node installable via npm
- Supports gpt-4o-mini → gpt-5 cascade
- Shows cost savings prominently
- Basic error handling

---

### Phase 2: Multi-Provider Support (Week 3)

**Goal**: Support all CascadeFlow providers

**Tasks**:
1. ✅ Add Anthropic credentials and provider
2. ✅ Add Groq (free tier!)
3. ✅ Add Ollama (local) support
4. ✅ Add vLLM (self-hosted) support
5. ✅ Provider auto-detection based on credentials
6. ✅ Update UI to show provider selection
7. ✅ Test all provider combinations

**Deliverables**:
- Support for 5 providers (OpenAI, Anthropic, Groq, Ollama, vLLM)
- Users can mix providers in cascade
- Example: Groq (free) → OpenAI (quality)

---

### Phase 3: Advanced Features (Week 4)

**Goal**: Tool calling, streaming, advanced modes

**Tasks**:
1. ✅ Implement tool calling support
2. ✅ Add streaming mode (SSE output)
3. ✅ Implement "Smart Agent Mode"
4. ✅ Implement "Advanced Cascade" (3+ models)
5. ✅ Add quality config options
6. ✅ Session metrics tracking
7. ✅ Export metrics to CSV/JSON

**Deliverables**:
- Full feature parity with CascadeFlow core
- Agent workflows supported
- Streaming responses
- Comprehensive metrics

---

### Phase 4: Publishing & Approval (Week 5)

**Goal**: Get node approved and published

**Tasks**:
1. ✅ Code quality review (ESLint, TypeScript strict)
2. ✅ Security audit (no credentials in logs, proper error handling)
3. ✅ Documentation review (README, examples, troubleshooting)
4. ✅ Create video demo
5. ✅ Submit to n8n Creator Portal for verification
6. ✅ Publish to npm
7. ✅ Announce on n8n community forum

**Deliverables**:
- npm package: `n8n-nodes-cascadeflow`
- n8n verified badge (if approved)
- Listed in n8n community nodes
- Blog post announcing integration

---

## 📋 n8n Approval Process

### Requirements Checklist

**Technical Requirements**:
- [ ] Package name starts with `n8n-nodes-`
- [ ] MIT license
- [ ] Zero external dependencies (except n8n SDK)
- [ ] TypeScript with strict mode
- [ ] Proper error handling
- [ ] No API keys hardcoded
- [ ] Works with n8n 1.0+

**Quality Requirements**:
- [ ] ESLint passing (no warnings)
- [ ] Follows n8n design guidelines
- [ ] Clear, concise UI labels
- [ ] Helpful error messages
- [ ] Parameter validation
- [ ] Loading states for async operations

**Documentation Requirements**:
- [ ] README with clear setup instructions
- [ ] Usage examples (text, tools, streaming)
- [ ] Troubleshooting section
- [ ] API key setup guide
- [ ] Cost savings examples

**Security Requirements**:
- [ ] Credentials stored securely
- [ ] No sensitive data in logs
- [ ] Input sanitization
- [ ] Rate limit handling
- [ ] Timeout configuration

### Submission Process

1. **Develop & Test Locally**
   ```bash
   npm install
   npm run build
   npm link
   cd ~/.n8n
   npm link n8n-nodes-cascadeflow
   n8n start
   ```

2. **Publish to npm**
   ```bash
   npm version 1.0.0
   npm publish
   ```

3. **Submit to n8n Creator Portal**
   - Visit: https://n8n.io/creator-portal
   - Fill submission form
   - Provide npm package URL
   - Include demo video
   - Wait for review (1-2 weeks)

4. **If Approved**
   - Node gets "Verified" badge
   - Listed in n8n community nodes registry
   - Searchable in n8n UI

---

## 🔮 Future Integrations

### LangChain Integration (Month 2)

**Package**: `cascadeflow-langchain`
**Type**: Python pip package
**Location**: `integrations/langchain/`

**Features**:
- Custom `CascadeFlowLLM` class (LangChain LLM wrapper)
- Custom `CascadeFlowChatModel` (Chat model wrapper)
- Callbacks for cost tracking
- Drop-in replacement for existing LLM chains

**Example**:
```python
from cascadeflow_langchain import CascadeFlowChatModel

llm = CascadeFlowChatModel(
    drafter="gpt-4o-mini",
    verifier="gpt-5",
    quality_threshold=0.75
)

# Use like any LangChain LLM
from langchain.chains import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("What is AI?")
```

---

### LlamaIndex Integration (Month 3)

**Package**: `cascadeflow-llamaindex`
**Type**: Python pip package
**Location**: `integrations/llamaindex/`

**Features**:
- Custom `CascadeFlowLLM` (LlamaIndex LLM wrapper)
- Query engine with cascading
- Cost-optimized indexing

---

### Haystack Integration (Month 4)

**Package**: `cascadeflow-haystack`
**Type**: Python pip package
**Location**: `integrations/haystack/`

**Features**:
- Custom `CascadeFlowGenerator` component
- Pipeline integration
- RAG optimization

---

## 📊 Success Metrics

### Phase 1 (MVP) Success Criteria

- [ ] 100+ npm downloads in first month
- [ ] 10+ GitHub stars
- [ ] 5+ community workflows using CascadeFlow
- [ ] Average 60%+ cost savings reported
- [ ] Zero critical bugs reported

### Long-term Goals (6 months)

- [ ] 1,000+ npm downloads
- [ ] n8n verified badge approved
- [ ] 100+ GitHub stars
- [ ] Featured in n8n blog post
- [ ] 5+ integration packages published

---

## 🛠️ Development Setup

### Prerequisites

```bash
# Install n8n globally
npm install -g n8n

# Install n8n node CLI
npm install -g n8n-node-dev
```

### Local Development

```bash
# 1. Create node package
cd integrations/
n8n-node-dev new n8n-nodes-cascadeflow
cd n8n-nodes-cascadeflow/

# 2. Install dependencies
npm install

# 3. Build TypeScript
npm run build

# 4. Link for local testing
npm link

# 5. Link in n8n
cd ~/.n8n/
npm link n8n-nodes-cascadeflow

# 6. Start n8n
n8n start

# 7. Node should appear in n8n UI
```

### Testing Workflow

```bash
# Run unit tests
npm test

# Build and watch for changes
npm run dev

# Lint code
npm run lint
npm run lint:fix

# Type check
npm run typecheck
```

---

## 📚 Resources

### n8n Documentation
- Creating Nodes: https://docs.n8n.io/integrations/creating-nodes/
- Community Nodes: https://docs.n8n.io/integrations/community-nodes/
- Node Design Guidelines: https://docs.n8n.io/integrations/creating-nodes/guidelines/
- Starter Template: https://github.com/n8n-io/n8n-nodes-starter

### CascadeFlow Resources
- Main Docs: https://docs.lemony.ai/cascadeflow
- Provider Guide: https://docs.lemony.ai/cascadeflow/providers
- Cost Tracking: https://docs.lemony.ai/cascadeflow/cost-tracking
- FastAPI Integration: https://docs.lemony.ai/cascadeflow/fastapi

---

## ✅ Next Steps

1. **Review this plan** - Get feedback from team
2. **Set up directory** - Create `integrations/n8n-nodes-cascadeflow/`
3. **Initialize npm package** - Run `n8n-node-dev new`
4. **Start Phase 1** - Build MVP with Simple Cascade mode
5. **Test locally** - Validate with real n8n workflows
6. **Iterate** - Refine based on testing

---

**Questions? Comments? Suggestions?**

Open an issue or reach out to: hello@lemony.ai
