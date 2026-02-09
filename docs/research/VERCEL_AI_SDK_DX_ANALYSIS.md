# Vercel AI SDK -> cascadeflow DX Analysis (Ship-Tomorrow Path)

## Goal
Enable developers who already use the Vercel AI SDK (`useChat` / `useCompletion`) to adopt cascadeflow with:
- minimal code changes
- no Vercel approvals / marketplace steps
- working streaming in Next.js App Router (Node or Edge runtimes)

This doc focuses on the fastest adoption path we can ship immediately: a `useChat`-compatible route handler.

## What Most Developers Expect
- keep their existing chat UI (`useChat`) and request shape (`{ messages: [...] }`)
- change only the server route (or swap the API URL)
- keep environment variables and deployment flow unchanged
- streaming works locally and on Vercel

## Options Compared

### Option 1: OpenAI-compatible baseURL swap (fastest, if they already have a gateway)
If a team already uses OpenAI-compatible endpoints and can point them at cascadeflow, this is the smallest diff:
- keep Vercel AI SDK `generateText` / `streamText` calls
- change provider `baseURL`

This option depends on having an OpenAI-compatible cascadeflow endpoint available (hosted proxy/gateway).

### Option 2: `useChat` drop-in handler (recommended for “ship tomorrow”)
Keep the client unchanged and swap the server route implementation to cascadeflow:
- client keeps `useChat`
- server route returns an AI SDK streaming `Response`
- no gateway required
- no provider-interface work required

This is implemented in `@cascadeflow/core` as:
- `VercelAI.createChatHandler(agent, { protocol })`

### Option 3: AI SDK provider adapter (native `streamText({ model })` integration)
This would let developers pass cascadeflow as an AI SDK “model” and keep all `ai` server helpers.
It is a larger surface area and depends on tight version alignment with the AI SDK provider/model interfaces.

## Ship-Tomorrow Recommendation
Deliver Option 2 as the default:
- **works with existing `useChat` UIs**
- **does not require any Vercel approvals**
- **Edge-compatible** (no Node-only imports required to bundle `@cascadeflow/core`)
- supports both AI SDK v4 data stream protocol and v5+/v6 UI message streams via runtime feature detection

## Minimal Integration (Next.js App Router)

Server route:
```ts
// app/api/chat/route.ts
import { CascadeAgent, VercelAI } from '@cascadeflow/core';

export const runtime = 'edge'; // optional; works in Node too

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.15 },
    { name: 'gpt-4o', provider: 'openai', cost: 2.5 },
  ],
});

export const POST = VercelAI.createChatHandler(agent, { protocol: 'data' });
```

Client:
```tsx
import { useChat } from '@ai-sdk/react';

export function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat();
  // render messages + input...
}
```

## Safety Notes
- This integration is **handler-level** (it returns the streaming `Response` `useChat` expects).
- It does not require Vercel marketplace approvals because it is just OSS libraries + a Next route.
- Developers can adopt incrementally by switching only one route and leaving the rest of their app unchanged.

