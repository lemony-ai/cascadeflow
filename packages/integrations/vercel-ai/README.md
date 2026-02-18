# @cascadeflow/vercel-ai

Integration helpers for using **cascadeflow** with the **Vercel AI SDK**.

This package is intentionally thin: it re-exports the Vercel AI SDK integration surface from `@cascadeflow/core` so you can treat it as an explicit integration dependency.

## What It Supports

- AI SDK v4 `data` stream protocol and AI SDK v5/v6 UI message streams.
- `useChat` multi-turn message lists.
- Incoming UI messages with `parts` (AI SDK v6 format) and classic `content` strings.
- Tool call stream events (`tool_call_delta`, `tool-input-*`) for better debugging and UI rendering.
- Server-side tool execution loops via `toolExecutor` or `toolHandlers`.
- Multi-step loop controls: `maxSteps`, `forceDirect`.

## Feature Matrix

| Capability | Vercel AI Integration | LangChain Integration | Core CascadeAgent |
|---|---|---|---|
| Trivial + multi-turn messages | ✅ | ✅ | ✅ |
| AI SDK `parts` message support | ✅ | N/A | N/A |
| Data/UI streaming protocols | ✅ | ✅ (LangChain streaming) | ✅ |
| Tool call streaming visibility | ✅ | ✅ | ✅ |
| Server-side tool execution loop | ✅ (`toolExecutor` / `toolHandlers`) | ✅ (`bindTools` + runtime tools) | ✅ (`toolExecutor`) |
| Multi-tool loop/message-list continuation | ✅ | ✅ | ✅ |
| Domain-aware cascading (configured on agent) | ✅ | ✅ | ✅ |
| Draft/verifier cascade | ✅ | ✅ | ✅ |
| Per-run observability metadata in framework traces | ⚠️ partial (via agent callbacks) | ✅ LangSmith-first | ⚠️ callback-driven |
| LangGraph/LCEL-native composition | ❌ (not relevant) | ✅ | ❌ (framework-agnostic core) |

## Gaps vs LangChain/Core (and what to integrate next)

These are the highest-value additions that make sense for Vercel AI SDK:

1. Request-level override channel  
Allow controlled per-request overrides (e.g. `forceDirect`, `maxSteps`, domain hint) from signed metadata instead of static handler config only.

2. Cascade decision stream parts  
Emit explicit UI/data stream parts for routing decisions (`direct` vs `cascade`, draft accepted/rejected) to improve frontend debuggability.

3. First-class structured output helpers  
Add Vercel-focused helpers for object generation patterns (AI SDK object workflows) with cascade metadata attached.

4. Turn-key telemetry adapters  
Provide built-in hooks for common observability stacks (OpenTelemetry/Langfuse/etc.) without custom callback plumbing.

## Install

```bash
pnpm add @cascadeflow/core @cascadeflow/vercel-ai ai @ai-sdk/react
```

## Next.js `useChat` drop-in backend (App Router)

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

const handler = createChatHandler(agent);

export async function POST(req: Request) {
  return handler(req);
}
```

## Tool Loop Example (Single Tool -> Multi Tool Progression)

```ts
import { CascadeAgent } from '@cascadeflow/core';
import { createChatHandler } from '@cascadeflow/vercel-ai';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, apiKey: process.env.OPENAI_API_KEY },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, apiKey: process.env.OPENAI_API_KEY },
  ],
});

const tools = [
  {
    type: 'function' as const,
    function: {
      name: 'get_weather',
      description: 'Get weather for a city',
      parameters: {
        type: 'object',
        properties: { location: { type: 'string' } },
        required: ['location'],
      },
    },
  },
];

export const POST = createChatHandler(agent, {
  protocol: 'data',
  tools,
  // Use one of:
  // 1) Provide a full ToolExecutor
  // toolExecutor: new ToolExecutor([...]),
  // 2) Or use simple handler mapping:
  toolHandlers: {
    async get_weather(args) {
      return { location: String(args.location ?? 'unknown'), weather: 'sunny' };
    },
  },
  maxSteps: 5,
  forceDirect: true, // useful for deterministic tool-loop behavior
});
```

## Handler Options

- `protocol`: `'data' | 'text'`
- `stream`: disable streaming and return JSON when `false`
- `systemPrompt`, `maxTokens`, `temperature`
- `tools`, `extra`
- `toolExecutor`: use core `ToolExecutor` for server-side tool loops
- `toolHandlers`: lightweight mapping alternative to `toolExecutor`
- `maxSteps`: max loop turns for tool execution
- `forceDirect`: skip cascade and run direct path
- `userTier`: reserved for tier-aware routing flows

Note: when tool execution loop is enabled, streaming responses are currently buffered through `agent.run(...)` to preserve deterministic loop semantics.

See `examples/vercel-ai-nextjs/` for a complete runnable example.
