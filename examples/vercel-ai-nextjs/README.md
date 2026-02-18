# cascadeflow + Vercel AI SDK (Next.js `useChat`)

This example shows how to use **cascadeflow** as the backend for the Vercel AI SDK UI hook `useChat` in a **Next.js App Router** project running on the **Edge runtime**.

## Run

```bash
cd examples/vercel-ai-nextjs
pnpm install
pnpm dev
```

## Requirements

- `ai` + `@ai-sdk/react` already in your app (this example includes them).
- Any provider keys you want to use (for example `OPENAI_API_KEY`).

## Environment Variables

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
```

## Feature Coverage

- Multi-turn chat (`messages` list) with `useChat`.
- Streaming responses (`data` protocol, plus automatic UI message stream support on newer AI SDKs).
- UI message `parts` payloads are accepted by the backend handler.
- Works with cascadeflow tool loops via `toolExecutor` or `toolHandlers` in `createChatHandler(...)`.

### Integration Progression (Trivial -> Advanced)

1. Trivial text chat: pass plain `messages`.
2. Single tool-call planning: provide `tools` and optional `extra.tool_choice`.
3. Tool-loop execution: add `toolExecutor` or `toolHandlers` plus `maxSteps`.
4. Multi-tool continuation: send assistant/tool message-list turns for closed-loop workflows.

## Deploy As A Separate Vercel Project

```bash
vercel link --yes --project cascadeflow-vercel-ai-nextjs-sandbox
vercel env add OPENAI_API_KEY production
vercel env add OPENAI_API_KEY preview
vercel deploy
```

## How It Works

- `app/api/chat/route.ts` uses `@cascadeflow/vercel-ai` `createChatHandler(...)` with `protocol: 'data'`.
  - On AI SDK v4, this emits the **data stream protocol** expected by `useChat`.
  - On newer AI SDK versions, the handler automatically uses the **UI message stream** when available.
- `app/page.tsx` uses `useChat()` (default route is `/api/chat`).
