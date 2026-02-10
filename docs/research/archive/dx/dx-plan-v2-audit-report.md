# cascadeflow DX Plan V2 Audit Report

Date: 2026-02-05
Scope: Audit-only (no implementation)

## Note on source plan retrieval
The requested fetch commands could not be executed in this environment because no `origin` remote is configured. This audit is therefore based on the itemized P0 checks provided in the task prompt.

## Section 10 P0 Audit

### 1) Measurement Correctness

| Item | Status | Findings |
|---|---|---|
| Usage object canonical (`input_tokens`, `output_tokens`, `cached_input_tokens`) | **PARTIAL** | Proxy usage uses `input_tokens`/`output_tokens`, but no `cached_input_tokens`. Other core provider usage objects still center on `prompt_tokens`/`completion_tokens` naming, so there is no single canonical usage shape across codepaths. |
| Direct routing cost correct | **PARTIAL** | TS direct route cost uses provider-reported usage when present. Python direct route still computes cost from estimated token counts (`tokens_used` fallback or `len(content.split()) * 1.3` in streaming direct), which can diverge from actual provider usage/cached tokens. |
| PriceBook / PricingResolver implemented | **NOT STARTED** | No `PriceBook` or `PricingResolver` symbols found in Python or TypeScript core paths. |

### 2) Tool Loop Engine

| Item | Status | Findings |
|---|---|---|
| `run()` closes tool loops by default | **NOT STARTED** | Default non-streaming `run()` paths return model tool calls but do not execute a full multi-turn tool loop to closure. Streaming tool manager has loop support, but it is opt-in via `execute_tools=True` and defaults off. |
| Parallel tool arrays supported | **PARTIAL** | Multiple tool calls in an array are recognized and processed, but execution is sequential (`for tool_call in tool_calls_found`) rather than parallelized. |
| Canonical transcript format | **PARTIAL** | There is deterministic message normalization plus `messages_to_prompt()` rendering, but no single explicit canonical transcript schema spanning tool loop state/history across all execution paths. |

### 3) Streaming Parity

| Item | Status | Findings |
|---|---|---|
| System prompts normalized before routing | **PARTIAL** | If system content is supplied in `messages`, it is normalized. But `system_prompt`/`systemPrompt` option is passed to provider call-time and is not folded into routing input normalization before route decision. |
| Streaming vs non-streaming produce same routing decisions | **PARTIAL** | Core routing flow is similar, but non-streaming `run()` includes tool-complexity override logic that is not mirrored in `run_streaming()`, so tool-bearing requests can route differently. |

## Remaining Work (for all PARTIAL/NOT STARTED items)

1. Define and enforce a single cross-runtime usage schema with explicit cache fields (including `cached_input_tokens`).
2. Unify direct-route cost accounting on provider usage/pricing metadata (avoid heuristic token estimates where usage exists).
3. Introduce centralized pricing abstractions (`PriceBook` + `PricingResolver`) and wire all cost paths through them.
4. Add default tool-loop closure behavior (or explicit default policy) for non-streaming `run()`.
5. Add optional true parallel execution for tool-call arrays where tools are side-effect-safe.
6. Specify and document a canonical transcript/state format used consistently by direct, cascade, and streaming tool flows.
7. Normalize system prompts into routing input consistently for streaming and non-streaming paths.
8. Align routing decision logic between `run()` and `run_streaming()` (including tool-complexity overrides).
