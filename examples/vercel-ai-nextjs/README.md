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

## How It Works

- `app/api/chat/route.ts` uses `VercelAI.createChatHandler(...)` with `protocol: 'data'`.
  - On AI SDK v4, this emits the **data stream protocol** expected by `useChat`.
  - On newer AI SDK versions, the handler automatically uses the **UI message stream** when available.
- `app/page.tsx` uses `useChat()` (default route is `/api/chat`).
