# Integrate cascadeflow Fast (Tomorrow-Ready)

This guide is optimized for teams who already have an app (Next.js, an agent, or an API route) and want to try cascadeflow with minimal change.

## Option 1 (Recommended): Next.js `useChat` Drop-In (Vercel AI SDK)

Best when you already use Vercel AI SDK UI hooks like `useChat`.

Install:
```bash
pnpm add @cascadeflow/core @cascadeflow/vercel-ai ai @ai-sdk/react
```

```ts
import { CascadeAgent } from '@cascadeflow/core';
import { createChatHandler } from '@cascadeflow/vercel-ai';

export const runtime = 'edge';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY },
  ],
});

const handler = createChatHandler(agent); // default: `protocol: 'data'`

export async function POST(req: Request) {
  return handler(req);
}
```

Why it’s fast:
- No provider rewrite.
- Compatible with `useChat` default `streamProtocol: 'data'` (AI SDK v4). On newer AI SDK versions, the handler automatically uses the UI message stream when available.

See: `examples/vercel-ai-nextjs/`.

## Option 2: “Keep Your SDK” via Proxy (Minimal Code Changes)

Best when you already have:
- OpenAI SDK, Anthropic SDK, or any OpenAI-compatible client
- Your own router/agent framework

You run cascadeflow’s routing proxy and point your existing client’s base URL at it.

Typical change:
- Set `OPENAI_BASE_URL` / `baseURL` to your proxy URL
- Keep everything else the same

See: `docs/guides/proxy.md`.

## Option 3: Use cascadeflow Directly (Library)

Best when you can change the call site to use cascadeflow’s agent.

```ts
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'claude-3-5-sonnet-20241022', provider: 'anthropic', cost: 0.003, apiKey: process.env.ANTHROPIC_API_KEY },
  ],
});

const result = await agent.run('Ship tomorrow. What should I cut?');
console.log(result.content);
```

## What We Deliberately Don’t Require

- No Vercel marketplace listing
- No Vercel partner approval
- No “official provider” registration

## Current Limits (Honest)

- The `useChat` integration streams via Vercel AI SDK protocols (AI SDK v4: **data stream**; AI SDK v5+/v6: **UI message stream**, auto-detected when available).
- Token usage is not currently emitted in the stream (cascadeflow doesn’t expose it mid-stream yet).
- Tool-call streaming is supported when cascadeflow emits tool calls during streaming:
  - AI SDK v4: `tool_call_streaming_start` / `tool_call_delta` / `tool_call`
  - AI SDK v5+/v6: `tool-input-*` chunks
- The `useChat` handler does not execute tools: it can stream tool calls, but tool execution is still up to your app.
  - If you want server-side tool execution loops, use the agent tool-loop APIs (`toolExecutor` in TypeScript, `tool_executor` in Python) for non-streaming runs.
