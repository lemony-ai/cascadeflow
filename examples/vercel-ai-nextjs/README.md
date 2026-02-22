# cascadeflow + Vercel AI SDK (Next.js `useChat`)

This example shows how to use **cascadeflow** as the backend for the Vercel AI SDK UI hook `useChat` in a **Next.js App Router** project running on the **Edge runtime**.

## Run

```bash
pnpm -C ../../packages/core build
pnpm -C ../../packages/integrations/vercel-ai build
cd examples/vercel-ai-nextjs
pnpm install
pnpm dev
```

`pnpm dev` and `pnpm build` auto-build local workspace packages when they exist (monorepo usage), and skip that step in standalone deployments (for example Vercel project-root deploys).
`next.config.js` also auto-switches module resolution: local monorepo builds when present, published npm packages when deployed standalone.

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

### Deployment Protection (SSO) Note

On some Vercel team plans, newly created projects can default to deployment protection (`ssoProtection`).
If enabled, direct API probes to `/api/chat` can return `401` even when the route is healthy.
For sandbox E2E validation, disable protection on the sandbox project (or allow unauthenticated access for its domain).

### Real Deployed `/api/chat` Smoke Test

After deploy, validate the real network path (not only local tests):

```bash
DEPLOY_URL="https://<your-deployment>.vercel.app"
curl -sS -X POST "$DEPLOY_URL/api/chat" \
  -H "content-type: application/json" \
  --data '{"messages":[{"role":"user","content":"Reply with: cascadeflow-ok"}]}'
```

Expected result: a streaming response payload containing assistant text (for example `cascadeflow-ok`).

## How It Works

- `app/api/chat/route.ts` uses `@cascadeflow/vercel-ai` `createChatHandler(...)` with `protocol: 'data'`.
  - On AI SDK v4, this emits the **data stream protocol** expected by `useChat`.
  - On newer AI SDK versions, the handler automatically uses the **UI message stream** when available.
- `app/page.tsx` uses `useChat()` (default route is `/api/chat`).
