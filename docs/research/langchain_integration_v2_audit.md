# LangChain Integration V2 Audit (CascadeFlow)

Date: 2026-02-10
Branch: `codex/langchain-integration-v2`

## Current Integration Surfaces

Python:
- `cascadeflow/integrations/langchain/wrapper.py`: `CascadeFlow(BaseChatModel)` wrapper around two LangChain chat models.
- `cascadeflow/integrations/langchain/langchain_callbacks.py`: `CascadeFlowCallbackHandler` + `get_cascade_callback()` cost/token tracker.
- `cascadeflow/integrations/langchain/utils.py`: token usage extraction, heuristic quality scoring, static pricing table.
- `cascadeflow/integrations/langchain/routers/pre_router.py`: optional pre-routing by query complexity.

TypeScript:
- `packages/langchain-cascadeflow/src/wrapper.ts`: `CascadeFlow(BaseChatModel)` wrapper around two LangChain JS chat models.
- `packages/langchain-cascadeflow/src/utils.ts`: token usage extraction, heuristic quality scoring, static pricing table.
- Cost tracking provider mode: `'langsmith'` (default) or `'cascadeflow'`.

## What Works Today

- Drop-in model wrapper for most non-tool calls (sync/async).
- Pre-router direct routing (skip drafter for “hard/expert”).
- Tool binding + structured output binding (Python: `bind_tools`, `with_structured_output`; TS: `bindTools`, `withStructuredOutput`).
- LangSmith visibility via:
  - per-call tags (`drafter` / `verifier`) in Python generate/agenerate path
  - `llm_output["cascade"]` and `message.response_metadata["cascade"]` metadata injection

## Gaps vs “Agentic Future” Requirements

### 1. Tool Calls Should Not Trigger Escalation

Problem:
- Tool-calling responses often have empty/short `content`.
- Current heuristic quality scoring in `utils.py` penalizes short/empty content, which can cause:
  - unnecessary verifier escalation
  - broken closed tool loops (agent executor expects the tool call, not a verifier rewrite)

Target behavior:
- If the drafter returns tool calls (`tool_calls` present), treat it as “high quality” and accept without verifier.

### 2. Streaming Is Not Tool-Safe (Python)

Problem:
- Python streaming currently wraps chunks into `AIMessageChunk(content=...)` and discards structured chunk metadata.
- This can drop tool-call deltas / structured fields needed by LangChain agents, LangGraph, or downstream callbacks.

Target behavior:
- Preserve and forward the underlying chunk message objects whenever possible.
- Avoid emitting extra “switch messages” as normal assistant content in tool/agent contexts (it can corrupt parsers).

### 3. “Optimistic Streaming” Produces Mixed Outputs

Both Python + TS streaming do:
- stream drafter optimistically
- then potentially stream verifier after a “switch” marker

This is good for some UIs, but bad for:
- agent loops
- structured output parsing
- tool-call driven runs

We need an explicit policy/config for streaming:
- `consistent`: pick route before streaming (one model only)
- `optimistic`: current behavior (UI-first)

### 4. LangSmith Labels Should Be First-Class

Today:
- Python relies mostly on `tags=["drafter"]` / `["verifier"]` + `cascade` metadata.
- TS injects metadata but does not consistently attach tags/run names to calls.

Target behavior:
- Stable, queryable LangSmith tags + metadata:
  - tags like `cascadeflow`, `cascadeflow:drafter`, `cascadeflow:verifier`, `cascadeflow:direct`, `cascadeflow:accepted`, `cascadeflow:escalated`
  - metadata fields for decision + routing reason + cost breakdown + quality score
  - ideally `run_name` for drafter/verifier steps so traces are legible

### 5. Price Transparency

We currently have two modes:
- `'langsmith'`: costs are 0 locally (LangSmith computes server-side)
- `'cascadeflow'`: costs estimated via static pricing table

Questions to resolve:
- Do we want to always compute an *estimated* cost locally (for transparency),
  even when LangSmith is enabled (and keep “authoritative cost” in LangSmith)?

## Open Design Decisions

1. Supported ecosystems:
   - Python LangChain only, JS/TS LangChain only, or both at parity?
2. LangGraph expectations:
   - Do we explicitly support LangGraph “agent nodes” patterns and sub-agent graphs?
3. Streaming behavior:
   - default `consistent` (single model stream) vs `optimistic` (switch mid-stream)?
4. Tool calling policy:
   - “tool calls always accepted” vs “tool calls still need verifier gate in some cases”?
5. LangSmith schema:
   - exact tag/metadata contract developers should rely on (docs + tests).

