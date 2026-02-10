# Extended Testing And Benchmarking (Real APIs)

This guide describes how to run an extended end-to-end (E2E) validation session for cascadeflow using **real provider APIs**.

Goals:
- Validate correctness, routing logic, and cost optimization in the ways developers actually use cascadeflow:
  - Apps (Next.js API routes, Vercel AI SDK `useChat`)
  - Agents (tools, multi-turn, structured outputs)
  - Routers/proxies (OpenAI-compatible HTTP, existing SDKs)
- Produce numbers you can share: **accuracy**, **drafter acceptance**, **cost reduction**, latency.

## Setup

1. Load provider keys (repo root `.env`):
```bash
set -a && source .env && set +a
```

2. Install deps:
```bash
pnpm install
python3 -m pip install -r requirements-dev.txt
```

## What We Measure

- **Accuracy**: dataset-specific correctness (e.g. GSM8K exact match, MMLU multiple-choice, tool-call correctness).
- **Drafter acceptance**: how often the cheap model is accepted without escalation.
- **Cost reduction**: savings vs a verifier-only baseline.
- **Latency**: end-to-end time per request (where available).

## Benchmark Coverage Map

Python benchmark suite (see `tests/benchmarks/`):
- `run_benchmarks.py`: GSM8K + MMLU + MT-Bench (cost reduction + quality retention targets).
- `run_all.py`: broad coverage:
  - HumanEval (code)
  - GSM8K (math)
  - MT-Bench (multi-turn)
  - TruthfulQA (factual)
  - Banking77 (classification)
  - Customer support (real-world Q&A)
  - BFCL agentic tool calling (multi-turn + dependencies)
  - Tool calling (single + multi-turn tool selection correctness)
  - Agentic multi-agent (router + tool call correctness)
  - Provider comparison (quality engine consistency across providers)

TypeScript coverage (monorepo tests):
- `pnpm test`: builds + tests all TS packages and the Next.js `useChat` example.
- Vercel AI SDK handler E2E tests:
  - `packages/core/src/vercel-ai/__tests__/e2e.test.ts`
  - `packages/core/src/__tests__/vercel-ai-chat-handler.e2e.test.ts`
- Optional real API smoke:
  - `pnpm -C packages/core run real-api:smoke`

## Recommended Sessions

### 1) Smoke (Fast Signal, Low Spend)

One-command runner (writes logs/results under `benchmark_results/sessions/`):
```bash
set -a && source .env && set +a
./scripts/extended-e2e-session.sh smoke
```

Manual steps:
```bash
pnpm test
python3 -m pytest

pnpm -C packages/core exec vitest run \
  src/vercel-ai/__tests__/e2e.test.ts \
  src/__tests__/vercel-ai-chat-handler.e2e.test.ts

python3 tests/benchmarks/run_benchmarks.py --quick --output benchmark_results/e2e_quick.json || true
python3 -m tests.benchmarks.run_all --profile smoke --output-dir benchmark_results/smoke
```

### 2) Standard (Shareable Numbers)

```bash
set -a && source .env && set +a
./scripts/extended-e2e-session.sh standard
```

### 3) Overnight (Stress + Agentic)

```bash
python3 -m tests.benchmarks.run_all --profile overnight --output-dir benchmark_results/overnight
```

## Developer DX Validation (Out Of The Box)

Minimal “does it work for users tomorrow” checks:
1. `docs/guides/integrate_fast.md` paths:
   - Vercel AI SDK `useChat` drop-in: build the example `examples/vercel-ai-nextjs/`
   - Proxy: validate OpenAI-compatible endpoint behavior (see `docs/guides/proxy.md`)
2. Agent tools:
   - Tool-call generation correctness: `python3 -m tests.benchmarks.tool_calls`
   - Multi-turn tool history: `python3 -m tests.benchmarks.tool_calls_agentic`

## Notes / Current Limits

- Tool-call *generation* is benchmarked heavily.
- Full tool *execution loops* depend on the integration path:
  - Streaming tool execution exists via the streaming tool manager.
  - Non-streaming multi-step tool execution is supported for direct routing; cascade tool paths currently focus on tool-call correctness and verification.

