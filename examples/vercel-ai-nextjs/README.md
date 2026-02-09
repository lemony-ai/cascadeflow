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

- `app/api/chat/route.ts` uses `VercelAI.createChatHandler(...)` with `protocol: 'data'` to return the Vercel AI SDK **UI message stream** SSE protocol (default for `useChat`).
- `app/page.tsx` uses `useChat({ api: '/api/chat' })`.
