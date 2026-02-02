# n8n v2 Integration Strategy (Planning Only)

## Research limitations

External access to `docs.n8n.io` and GitHub-hosted n8n docs is blocked in this environment (HTTP 403 via proxy). This plan is based on:

- The current cascadeflow n8n node implementation and documentation in this repo.
- General knowledge of n8n’s AI/LangChain architecture.

**Action required:** validate all “v2 capability” claims against the official n8n v2 documentation once network access is available.

## 1) n8n v2 capabilities overview (to validate)

Based on n8n’s current AI/LangChain architecture (and expectations for v2), the following capabilities matter most for cascadeflow:

- **AI Chat Model nodes** as first-class building blocks feeding Chain / Prompt / Tools nodes.
- **AI Agent nodes** (LangChain-based) with tool integration and orchestration.
- **Native AI nodes** for prompt templating, memory, document loaders, vector stores, and agent execution.
- **Model registry / provider selection** surfaced via credentials and model-specific nodes.
- **Execution logs + metadata** for observability (request/response data, token usage, costs when available).

**Validate in v2:**

- Whether AI Agent nodes still restrict model inputs to a whitelist and whether custom community models can be attached.
- Whether v2 introduces a **“model provider” abstraction** or **AI node SDK** for exposing custom models/tools with richer metadata.
- Any official support for **per-step cost breakdown** or **model routing visualization** in the UI.

## 2) Current n8n integration (baseline)

### What we have now

- **Node type:** Language Model sub-node that accepts **Verifier** and **Drafter** model connections, and optional domain-model inputs. This places cascadeflow between model nodes and downstream chain nodes. 【F:packages/integrations/n8n/README.md†L31-L43】【F:packages/integrations/n8n/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.ts†L12-L81】
- **Agent limitation:** The current node **does not work with n8n AI Agent nodes** due to whitelisted model restrictions. 【F:packages/integrations/n8n/README.md†L64-L67】
- **Domain routing:** 16 supported domains with UI toggles and per-domain routing. 【F:packages/integrations/n8n/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.ts†L12-L81】
- **Observability:** Detailed logs in the n8n UI show cascade decisions, confidence, cost savings, and latency breakdowns. 【F:packages/integrations/n8n/README.md†L200-L244】

### Relevant core capability notes

- **Alignment scoring version:** TypeScript alignment scorer is based on Python v10; missing v14 improvements. 【F:packages/core/src/alignment.ts†L1-L37】

## 3) Gap analysis (current vs needed)

### A) n8n v2 capability gaps (TBD by validation)

1. **Agent compatibility**
   - **Current:** Not supported due to whitelist. 【F:packages/integrations/n8n/README.md†L64-L67】
   - **Needed:** A pathway for cascadeflow to participate in AI Agent workflows (either as a model or as a tool/agent node).

2. **Model metadata visibility**
   - **Current:** Logs show selected model path and costs, but not a standardized UI indicator in node connections. 【F:packages/integrations/n8n/README.md†L200-L244】
   - **Needed:** UI-level “model used” indicator + cost breakdown at execution step/trace granularity.

3. **Native AI node integration**
   - **Current:** Works as Language Model sub-node in Chain nodes, not native AI Agent nodes. 【F:packages/integrations/n8n/README.md†L64-L67】
   - **Needed:** Seamless compatibility with native AI nodes and LangChain agents (see section 6).

### B) Python SDK feature gaps for n8n (priority list)

Feature gaps called out in the request, with current TS status:

1. **Alignment scorer v14**
   - **Current TS:** v10 in TypeScript. 【F:packages/core/src/alignment.ts†L1-L37】
   - **Gap:** Port Python v14 features and thresholds to TS.

2. **All 16 domains support**
   - **Current n8n:** 16 domain constants exist, but only a subset exposed as toggles in UI (e.g., code, math, data, creative, legal, medical, financial, science). 【F:packages/integrations/n8n/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.ts†L12-L81】【F:packages/integrations/n8n/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.ts†L988-L1068】
   - **Gap:** Surface full 16-domain toggles + descriptions and allow connections for all.

3. **Confidence thresholds (per complexity tier + domain-specific)**
   - **Current TS:** Supported in core; n8n node exposes a single quality threshold and optional domain thresholds. 【F:packages/integrations/n8n/README.md†L124-L144】【F:packages/integrations/n8n/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.ts†L618-L623】
   - **Gap:** Expose full confidence-threshold table and complexity-aware routing in UI.

4. **Cost tracking**
   - **Current:** Logs show cost savings; cost tracking is in TS core and LangChain integration, but n8n does not surface a standardized per-model cost panel. 【F:packages/integrations/n8n/README.md†L200-L244】
   - **Gap:** Add UI surfaced fields / JSON metadata for downstream nodes to read cost breakdowns.

## 4) Architecture options (model vs agent vs both)

### Option A — “Model” node only (current pattern)

**Description:** Continue exposing cascadeflow as a Language Model node, used by Chain and non-agent AI nodes.

**Pros**
- Compatible with current n8n architecture (sub-node model connector). 【F:packages/integrations/n8n/README.md†L31-L43】
- Minimal disruption; aligns with current implementation.

**Cons**
- Blocks AI Agent node usage due to model whitelist. 【F:packages/integrations/n8n/README.md†L64-L67】
- Harder to show cascade decisions beyond logs.

### Option B — “Agent” node

**Description:** Expose cascadeflow as an AI Agent node that orchestrates drafter/verifier models internally (and optionally tools).

**Pros**
- First-class integration with n8n AI Agent workflows.
- Can surface cascade routing as part of agent trace (if v2 supports it).

**Cons**
- Requires alignment with n8n’s agent model contract and tool call expectations.
- Must implement tool interaction semantics carefully to preserve downstream agent behavior.

### Option C — Both (recommended)

**Description:**
- Keep the **Model node** for Chain and generic AI nodes.
- Add an **Agent node** for agent workflows and tool orchestration.

**Pros**
- Covers all n8n AI flows (native AI nodes + agents + LangChain chains).
- Gives users choice and a migration path.

**Cons**
- More surface area to maintain.

### Option D — “Routing service” node (non-model)

**Description:** A standalone node that receives text input, routes internally, and outputs text + metadata.

**Pros**
- Works with all n8n workflows, regardless of AI node constraints.

**Cons**
- Loses Language Model connector semantics (tool calls, streaming, token tracking via n8n’s LM pipeline).

## 5) UI/UX for model tracking & cost visibility

### Goals

- **Visible model used** (drafter vs verifier vs domain model).
- **Cost breakdown per step** (drafter cost, verifier cost, total, savings).
- **Cascade decision visibility** (why did it escalate?).

### Proposed UI/UX patterns

1. **Execution log summary block**
   - Add a concise, structured log summary at end of each run:
     - `selected_model`, `fallback_model`, `domain`, `confidence`, `threshold`, `costs`.
   - Use log formatting in n8n to enable quick scan (already partially implemented). 【F:packages/integrations/n8n/README.md†L200-L244】

2. **Output metadata fields**
   - Include JSON metadata in the node output data structure:
     - `cf.model_used`, `cf.domain`, `cf.confidence`, `cf.costs`, `cf.savings`.
   - Downstream nodes can render in UI or export.

3. **UI indicators (if v2 supports)**
   - Use node badges for “Drafter” vs “Verifier” used.
   - Link to a “Cascade Trace” panel in execution view.

## 6) Working with native AI nodes and LangChain agents

### A) Native AI nodes

- **Model node path:** Keep `LmChatCascadeFlow` as the sub-node for AI Chat Model inputs.
- **Compatibility with prompt/chain nodes:** Continue ensuring it meets `BaseChatModel` expectations. 【F:packages/integrations/n8n/N8N_COMPATIBILITY_VALIDATION.md†L17-L43】

### B) LangChain agents

- **Short term:** Provide a “routing service” node alternative for agent workflows that can accept text input and return text + metadata.
- **Long term:** Implement a dedicated **AI Agent** node, if v2 provides an extension point for community agent nodes.

### C) Dual-mode strategy (if v2 supports)

- Add a **Model node** for LM workflows.
- Add an **Agent node** for agent workflows with tool routing.
- Add a **shared config** for model/cost/routing settings to keep consistency.

## 7) Implementation roadmap (planning only)

### Phase 0 — Validation & discovery (1-2 weeks)

- Validate n8n v2 AI node architecture and any SDKs/extension points.
- Confirm agent model whitelist behavior and any changes in v2.
- Identify available UI hooks for cost/trace visualization.

### Phase 1 — Feature parity (2-4 weeks)

- Port **alignment scorer v14** from Python to TS.
- Expose all **16 domains** in n8n UI with per-domain config.
- Add **per-tier confidence thresholds** in node config.
- Emit structured output metadata for costs and model usage.

### Phase 2 — Agent integration (3-6 weeks)

- Add cascadeflow **AI Agent node** (if v2 allows custom agent nodes).
- Implement tool-call compatibility and streaming behavior.
- Ensure metadata flows into agent execution traces.

### Phase 3 — UX polish & docs (1-2 weeks)

- Create UI usage guide for model tracking + cost visibility.
- Update n8n integration docs with v2 capabilities and examples.
- Add sample workflows (model-only + agent + mixed).

## 8) Recommendation

**Recommended approach:** **Option C (Model + Agent)** with a staged rollout:

1. **Immediate:** Improve Model node parity (alignment v14, full 16 domains, confidence thresholds, cost metadata).
2. **Short term:** Add a routing service node as a stopgap for AI Agent workflows.
3. **Mid term:** Implement a dedicated AI Agent node once n8n v2 extension points are confirmed.

This ensures cascadeflow remains the best-in-class model routing solution for both traditional chain workflows and agent-based flows as n8n v2 evolves.
