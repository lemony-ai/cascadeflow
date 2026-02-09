# @cascadeflow/vercel-ai

Integration helpers for using **cascadeflow** with the **Vercel AI SDK**.

This package is intentionally thin: it re-exports the Vercel AI SDK integration surface from `@cascadeflow/core` so you can treat it as an explicit integration dependency.

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

See `examples/vercel-ai-nextjs/` for a complete runnable example.

