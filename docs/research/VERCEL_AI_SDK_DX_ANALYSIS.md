# Vercel AI SDK → cascadeflow DX Analysis

## Scope
This document analyzes the **winning developer experience** for Vercel AI SDK users adopting cascadeflow, focusing on practical migration steps, friction points, and how to make the switch feel effortless.

## 1) Typical Vercel AI SDK usage today (single provider)
A common Vercel AI SDK pattern is a server route that instantiates a provider (e.g., OpenAI) and calls `generateText` or `streamText`.

**Before (single-provider OpenAI via Vercel AI SDK):**
```ts
// app/api/chat/route.ts
import { openai } from '@ai-sdk/openai';
import { generateText } from 'ai';

export async function POST(req: Request) {
  const { prompt } = await req.json();

  const result = await generateText({
    model: openai('gpt-4o-mini'),
    prompt,
  });

  return Response.json({ text: result.text });
}
```

**Developer expectations in this flow:**
- Single file change (often just the API route).
- Provider configured via environment variables.
- No extra infrastructure beyond the runtime route itself.

## 2) Minimum code change to switch to cascadeflow
There are two “minimum change” options, depending on whether you want to keep Vercel AI SDK calls or adopt cascadeflow directly.

### Option A — **OpenAI-compatible adapter** (1-line change)
If you expose cascadeflow behind an OpenAI-compatible endpoint (or proxy), you can keep the Vercel AI SDK usage intact and only change the model config to point at the new base URL.

**After (1-line change in the provider config):**
```ts
// app/api/chat/route.ts
import { openai } from '@ai-sdk/openai';
import { generateText } from 'ai';

export async function POST(req: Request) {
  const { prompt } = await req.json();

  const result = await generateText({
    model: openai('gpt-4o-mini', {
      baseURL: process.env.CASCADEFLOW_OPENAI_BASE_URL, // ← one-line change
    }),
    prompt,
  });

  return Response.json({ text: result.text });
}
```

**Why this is minimal:**
- No refactor of response handling.
- No change to the request/response schema.
- Lets teams keep existing AI SDK abstractions.

### Option B — **Direct cascadeflow usage** (multi-line change)
If you adopt cascadeflow directly, you replace `generateText` with a `CascadeAgent` call. This trades a small refactor for access to cascade-native features (routing, cost tracking, multi-model strategies).

**After (direct cascadeflow usage):**
```ts
// app/api/chat/route.ts
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.000375 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
});

export async function POST(req: Request) {
  const { prompt } = await req.json();

  const result = await agent.run(prompt);

  return Response.json({
    text: result.content,
    model: result.modelUsed,
    draftAccepted: result.draftAccepted,
  });
}
```

## 3) Integration effort comparison
**One-line change vs multi-file refactor**

| Path | Typical edits | DX level | Notes |
| --- | --- | --- | --- |
| **Option A: OpenAI-compatible adapter** | 1 line | ✅ “Wow, that was easy” | Keep AI SDK, swap baseURL. |
| **Option B: Direct cascadeflow usage** | 10–20 lines | ⚠️ “Small refactor” | Replace `generateText` with `CascadeAgent`. |
| **Option C: Edge function proxy** | Multi-file | ⚠️ “Infrastructure” | Add proxy route + env + deploy changes. |

## 4) What makes developers say “wow, that was easy”
**The winning DX bar:**
1. **1-line change** (swap `baseURL` or model provider) without changing route structure.
2. **No breaking changes** to the JSON response shape.
3. **Immediate proof of value** in a single response:
   - show `draftAccepted`, `modelUsed`, and `totalCost` in logs.
4. **No extra runtime setup** (works in Next.js Edge or Node without extra config).

## 5) Friction points with current integration options (A/B/C)
These friction points are framed as the current options a Vercel AI SDK user might face when adopting cascadeflow.

### Option A — OpenAI-compatible adapter
**Friction:**
- Requires a hosted proxy or base URL for cascadeflow.
- Developers may not know what endpoint to use without a clear guide.

### Option B — Direct cascadeflow usage
**Friction:**
- Requires swapping SDK calls and response shape (ex: `result.text` → `result.content`).
- Requires manual model/cost configuration before first run.
- No “drop-in” migration from Vercel AI SDK abstractions.

### Option C — Edge function proxy
**Friction:**
- Adds multi-file infra changes (proxy route + environment + deployment).
- Harder to validate locally if the proxy is hosted in a platform runtime.
- Extra operational burden for small teams.

## 6) Line-count diff for migration
**Base file length (single-provider Vercel AI SDK route):** 14 lines

**Option A (1-line change):**
- **1 line modified** (baseURL added to provider config)

**Option B (direct cascadeflow usage):**
- **~12 lines added** (CascadeAgent + model config + response fields)
- **~3 lines removed** (OpenAI SDK import + generateText usage)

## 7) Recommended “golden path” for adoption
**Best DX path for Vercel AI SDK users:**
1. **Start with Option A** (OpenAI-compatible adapter) to minimize code change.
2. Add a minimal “cascadeflow feature flag”:
   - Only route to cascadeflow for select environments (e.g., staging).
3. Offer an optional migration path to **Option B** once teams want deeper cost/quality signals.

## 8) Competitive comparison (routing tool integrations)
**Pattern match for other routing tools:**
- **Proxy/adapter approach:** Often easiest to adopt (1-line base URL change).
- **SDK replacement approach:** Most powerful but highest migration cost.
- **Middleware/edge proxy:** Best for centralized policy but operationally heavy.

**Implication for cascadeflow:**
- The **adapter path** should be the default DX for Vercel AI SDK users.
- Direct SDK usage should be offered as an “advanced” path with clear value props.

## 9) Notes & assumptions
- The “before” code reflects a standard Vercel AI SDK route shape.
- The “after” examples mirror cascadeflow’s TypeScript API and model configuration shape.
