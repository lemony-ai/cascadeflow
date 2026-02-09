# Vercel AI SDK Integration (UI + Edge)

This document captures the current approach for integrating **cascadeflow** with the **Vercel AI SDK** UI hooks (for example `useChat`) in a way that works in **Next.js App Router** and **Edge runtime**.

## What We Support Today

1. **Provider ecosystem via Vercel AI SDK (server-side)**
   - cascadeflow can access additional providers (Perplexity, xAI, Fireworks, etc.) through the Vercel AI SDK by using `VercelAISDKProvider` internally when you pick a provider name that isn't implemented natively.

2. **UI streaming for `useChat` (client-side)**
   - cascadeflow can act as the backend for `useChat` by returning the Vercel AI SDK **UI message stream** SSE protocol.
   - The helper lives under `@cascadeflow/core` as `VercelAI.createChatHandler(...)`.

## Next.js App Router Example (Edge)

```ts
import { CascadeAgent, VercelAI } from '@cascadeflow/core';

export const runtime = 'edge';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY },
  ],
});

const handler = VercelAI.createChatHandler(agent, { protocol: 'data' });

export async function POST(req: Request) {
  return handler(req);
}
```

On the client:

```tsx
'use client';

import { useChat } from '@ai-sdk/react';

export default function Page() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({ api: '/api/chat' });
  // ...
}
```

## Notes / Known Constraints

- cascadeflow streaming is currently driven by `CascadeAgent.runStream(...)`. `CascadeAgent.stream(...)` now accepts both `string` and `Message[]` for chat use cases.
- The UI helper supports:
  - `protocol: 'data'` (default Vercel AI SDK UI stream protocol)
  - `protocol: 'text'` (plain text streaming, requires `useChat({ streamProtocol: 'text' })`)

