# Vercel AI SDK Integration - Winning Developer Experience (Planning)

## Status (February 2026)
This doc started as a planning note. As of February 2026, cascadeflow ships a **tomorrow-ready** integration for Vercel AI SDK UI hooks via:
- `@cascadeflow/vercel-ai` -> `createChatHandler(...)` (Next.js `useChat` drop-in backend)

For the recommended “ship tomorrow” path, see:
- `docs/guides/integrate_fast.md`
- `examples/vercel-ai-nextjs/`

## 1. Vercel AI SDK Architecture Overview

**What it is**
- The Vercel AI SDK (`ai` package) is a TypeScript-first toolkit for building AI experiences in Next.js and other runtimes. It provides:
  - **React hooks** (client): `useChat`, `useCompletion` for streaming UI state.
  - **Server helpers**: `streamText`, `generateText` for server-side text generation.
  - **Provider abstraction**: `@ai-sdk/*` adapters for OpenAI, Anthropic, etc.
  - **Streaming primitives**: unified streaming for Node, Edge, and RSC flows (SSE + Web streams under the hood).

**Key architectural pieces**
- **Model interface**: The SDK defines a model API that providers implement, enabling runtime-agnostic text generation and streaming.
- **Streaming pipeline**:
  - Server-side helpers return a stream (ReadableStream) or an object that can be converted to a stream.
  - Client hooks consume streaming responses and update UI state incrementally.
- **Runtime alignment**:
  - The same helpers support Next.js App Router, Pages Router, and serverless/Edge routes.
  - Edge-friendly APIs avoid Node-only modules and use Web APIs where possible.

**Core features to integrate with cascadeflow**
- `useChat`, `useCompletion` for client hooks.
- `streamText`, `generateText` for server.
- Tool calling, structured outputs, and cost metadata where supported by providers.
- Edge runtime compatibility for streaming responses.

## 2. Current cascadeflow Capabilities (Relevant to Vercel AI SDK)

**Edge runtime support**
- cascadeflow already supports edge runtime configurations, including Vercel Edge patterns and deployment configuration. The Node example demonstrates edge runtime configuration, streaming with SSE, and API handler patterns suitable for Vercel Edge Functions.【F:packages/core/examples/nodejs/vercel-edge.ts†L1-L378】
- The browser-oriented Vercel edge example shows a Vercel Edge Function with a frontend, emphasizing global edge deployment, secure key handling, and cost tracking in responses.【F:packages/core/examples/browser/vercel-edge/README.md†L1-L123】

**Streaming support**
- The edge example uses `agent.stream(...)` and emits SSE chunks, including model-switch and completion metadata, which maps well to Vercel AI SDK streaming patterns.【F:packages/core/examples/nodejs/vercel-edge.ts†L120-L214】

**Browser compatibility**
- The TypeScript quickstart explicitly states cascadeflow runs in Node.js, browser, and edge runtimes with the same import, which aligns with Vercel’s mixed runtime environment.【F:docs/guides/quickstart-typescript.md†L677-L691】

**What’s missing today**
- No dedicated cascadeflow package that implements the AI SDK **model interface** (so users can pass cascadeflow directly as `model` into `streamText` / `generateText`).
- No native mapping from cascadeflow costs/metadata into Vercel AI SDK’s response metadata conventions.

## 3. Integration Options (A/B/C)

### Option A: Model/Provider Adapter (Future)
Implement the Vercel AI SDK provider interface so cascadeflow can be passed as a model to `generateText` or `streamText`.

**Pros**
- Native DX: users call Vercel AI SDK helpers directly.
- Works with `useChat`/`useCompletion` and server helpers out of the box.
- Central place to expose cascadeflow metadata in response (cost, model switch, routing decisions).

**Cons**
- Requires deep alignment with Vercel AI SDK provider interfaces and their streaming format.
- May need to support multiple transport flavors (Edge/Node/RSC).

### Option B: Middleware/Wrapper (`wrapWithCascade`)
Wrap any existing Vercel AI SDK provider or model with cascadeflow routing logic.

**Pros**
- Minimal coupling to Vercel AI SDK internals.
- Easy adoption: works with any provider supported by Vercel AI SDK.
- Allows gradual rollout; easy to test by wrapping an existing OpenAI provider.

**Cons**
- Harder to expose cascadeflow-specific metadata downstream.
- Might limit optimizations (e.g., enhanced streaming events).

### Option C: Edge-Compatible Proxy (`@cascadeflow/edge`)
Expose a proxy (Edge Function) that implements Vercel AI SDK-compatible endpoints.

**Pros**
- Extremely simple for users: deploy once and point `useChat` to it.
- Can centralize billing, cost tracking, and routing policies.

**Cons**
- Higher operational overhead (deploy & host).
- Less “library-like” and more “service-like.”

## 4. Integration Options Comparison (Effort / Impact Matrix)

| Option | Effort | DX Impact | Risk | Notes |
|--------|--------|-----------|------|------|
| A: Provider Adapter | Medium-High | Very High | Medium | Best native integration; most future-proof. |
| B: Wrapper | Low-Medium | High | Low | Fastest to ship; could be v1. |
| C: Edge Proxy | Medium | Medium | Medium | Good for enterprises or hosted offering. |

## 5. Recommended Approach

**Recommendation: Start with Option B (Wrapper) + Option A (Provider Adapter)**

Reasoning:
- **Option B** provides the quickest path to integration with minimal risk; it uses existing providers and offers immediate DX wins.
- **Option A** gives the “first-class” experience in Vercel AI SDK. It should be the follow-on once initial usage validates product fit.
- **Option C** can be offered later as a hosted/Edge-first deployment option for teams that want a managed cascadeflow gateway.

## 8. Developer Experience Mockups

### Quickstart (Next.js App Router)
```bash
pnpm add @cascadeflow/core @cascadeflow/vercel-ai ai @ai-sdk/react
```

```ts
// app/api/chat/route.ts
import { CascadeAgent } from '@cascadeflow/core';
import { createChatHandler } from '@cascadeflow/vercel-ai';

export const runtime = 'edge';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY },
  ],
});

export async function POST(req: Request) {
  return createChatHandler(agent)(req);
}
```

### Client Hook (React)
```ts
import { useChat } from '@ai-sdk/react';

export function Chat() {
  const { messages, sendMessage, status } = useChat(); // default route: /api/chat
  return (...);
}
```

### Cost Visibility (Dev Tools)
```
Request: /api/chat
Model route: gpt-4o-mini → gpt-4o
Total cost: $0.00023
Draft accepted: true
```

## 9. Implementation Roadmap

**Phase 0: Discovery (1–2 weeks)**
- Define the exact provider interface required by the Vercel AI SDK.
- Identify streaming formats and metadata hooks that can carry cascadeflow stats.

**Phase 1: Wrapper (2–3 weeks)**
- Implement `wrapWithCascade()` for existing providers.
- Provide examples for `useChat` + App Router.
- Add docs and TypeScript types.

**Phase 2: Provider Adapter (3–4 weeks)**
- Implement `createCascadeFlow()` as a model interface.
- Add stream adapters for Edge and Node.
- Provide cost and model-switch metadata integration.

**Phase 3: Edge Proxy (Optional, 2–4 weeks)**
- Build `@cascadeflow/edge` handler and templates.
- Provide Vercel template + one-click deploy.

## 10. Edge Runtime Considerations

- **Streaming**: use Web streams (ReadableStream) and SSE compatible responses; avoid Node-only dependencies.
- **Cold starts**: cache agent config in module scope to reuse across invocations where possible.
- **Env vars**: rely on `process.env` for edge-supported runtime (Vercel Edge provides env access).
- **Timeouts**: support progressive streaming to avoid timeouts.
- **CORS**: provide a default edge-safe response wrapper with configurable headers.

## 11. Competitive Analysis (High-Level)

- **AI router / cost-optimization tools** typically integrate by:
  1. **Provider adapters** (plug into Vercel AI SDK’s model interface).
  2. **Wrappers** around existing providers.
  3. **Hosted gateways** (centralize routing, logging, billing).
- The most successful integrations expose a *drop-in model* while still allowing advanced metadata (cost, switches, quality scores) for debugging and optimization.

---

## Appendix: Cascadeflow Assets to Reuse

- Vercel edge example (SSE + edge runtime config) can be adapted for the Vercel AI SDK integration docs and tests.【F:packages/core/examples/nodejs/vercel-edge.ts†L1-L378】
- Browser Vercel edge example provides UI ideas and cost tracking language for DX narratives.【F:packages/core/examples/browser/vercel-edge/README.md†L1-L123】
- Universal runtime support statement for messaging in integration docs.【F:docs/guides/quickstart-typescript.md†L677-L691】
