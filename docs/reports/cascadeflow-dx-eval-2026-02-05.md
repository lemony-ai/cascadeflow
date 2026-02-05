# cascadeflow DX + Agentic Readiness Report (Plan V2)

Date: 2026-02-05
Repo: cascadeflow (base: `origin/main` tip: `24bb33d`)
Worktree: `/tmp/cascadeflow-dx` (branch: `codex/holistic-dx-eval`)

This is a single, developer-style evaluation + execution plan (Plan V2) for cascadeflow across:
- 3 forward-deployed engineer profiles
- 7 integration paths per profile (base, LiteLLM, ML, OpenRouter, n8n, Vercel, LangChain)
- 2026 agentic expectations (tool loops, parallel tool calls, message lists, system prompts, cached tokens, tier/KPI rules)
- TS/Python parity

It is validated against the benchmarks actually executed in this worktree and calls out which results are currently not trustworthy (cost/savings artifacts). It proposes concrete, engineered fixes and the validation strategy to prove they work. No code changes are included here.

Section summary: This document is the canonical Plan V2 to get cascadeflow to "agentic-ready" with trustworthy savings and top-tier DX, with explicit pass/fail gates and artifacts per integration path.

---

## 1) Scope, Goals, Profiles

Goals:
- Evaluate cascadeflow the way developers integrate it in 2026, not as a library demo.
- Validate cost transparency: input/output tokens, cached input tokens, per-step and total cost.
- Validate agentic correctness: tool loops close by default, multi-tool arrays, parallel tools, and transcripts are replayable.
- Validate streaming parity: same app, streaming on/off produces consistent routing decisions and comparable results.
- Validate policy enforcement: tier/KPI constraints influence routing/cascading and are auditable.
- Validate TS/Python parity with golden transcripts.

Developer profiles (must be tested end-to-end):
1) Support bot (multi-turn, high volume text queries) with and without streaming in the same app.
2) Agentic payment analytics system (many agents + tool calls) with domain-aware routing and optional domain configs for domain-specific models.
3) Reasoning + tier/KPI routing (management KPIs drive cascading/routing decisions; must be auditable).

Integration paths (per profile; evaluated separately):
1) Base (no integration)
2) + LiteLLM
3) + ML enabled
4) + OpenRouter
5) + n8n
6) + Vercel AI SDK
7) + LangChain

Acceptance criteria (per your requirement, per use case/path):
- Savings >= 60% AND Accuracy >= 90%
- If either fails: root-cause + engineered fix + re-run to validate

Section summary: The plan is profile-driven and path-driven, with explicit acceptance gates that must be met by measurement that is provably correct.

---

## 2) Environment, Constraints, and Version Skew

Environment:
- Worktree: `/tmp/cascadeflow-dx`
- Keys loaded from `.env` (Anthropic + OpenAI available)
- OpenRouter key: missing at time of benchmarks (OpenRouter live runs blocked)
- n8n runtime: not available at time of benchmarks (n8n live runs blocked)

Model IDs validated (Anthropic `/v1/models`):
- Drafter target: `claude-haiku-4-5-20251001`
- Verifier target: `claude-opus-4-5-20251101`
- Also available: `claude-sonnet-4-5-20250929`

Version skew to address before implementation:
- Local `main` was behind `origin/main` by 1 commit (tip `24bb33d`) when this report was drafted.
- Plan execution requires syncing to latest `origin/main` before making changes to avoid chasing already-fixed issues.

Section summary: Some integration-path cells are blocked by missing key/runtime, and the first execution step must align the worktree with latest `origin/main`.

---

## 3) What Was Actually Executed (Evidence)

Python benchmarks executed:
- `tests/benchmarks/customer_support.py` (20 samples)
- `tests/benchmarks/tool_calls_agentic.py` (7 samples)
- `tests/benchmarks/tool_calls.py` (6 samples)
- `tests/benchmarks/mtbench/mtbench.py` (10 samples)
- `tests/benchmarks/gsm8k/gsm8k.py` (10 samples)
- `tests/benchmarks/banking77_benchmark.py` (20 and 50 sample runs)
- `tests/benchmarks/bfcl/agentic_benchmark.py` (5 tasks)

Python integration/unit tests executed:
- `tests/test_ml_integration.py`
- `tests/test_litellm_integration.py`
- `tests/test_domain_detection.py`

TypeScript tests executed:
- `packages/core` (vitest suite)

Section summary: This plan is grounded in real executed runs; it does not assume correctness of any metric that is known to be artifacted.

---

## 4) Benchmark Results (Observed) and Trustworthiness

Observed metrics:
- Customer Support (20): Savings 93.3% (PASS), Accuracy 35.0% (FAIL)
- MT-Bench (10): Savings 58.3% (FAIL), Accuracy 100% (PASS)
- GSM8K (10): Savings 84.3% (PASS), Accuracy 90.0% (PASS)
- ToolCalls-Agentic (7): Savings 93.3% (PASS), Accuracy 100% (PASS)
- ToolCalls-6 (6): Savings 93.3% (PASS), Accuracy 100% (PASS)
- Banking77 (20/50): Savings 100% (ARTIFACT, FAIL), Accuracy 75-80% (FAIL)
- BFCL Agentic (5): Accuracy 0% (FAIL) due to Anthropic 400 + circuit breaker behavior

Known untrustworthy result:
- Banking77 savings is not real. Root cause is cost accounting (direct routing cost derived from `ModelConfig.cost` and `response.tokens_used` which can be 0 or missing). This invalidates savings claims until fixed.

Section summary: Accuracy failures are real; some savings numbers are not. Measurement correctness is a P0 prerequisite.

---

## 5) Validation Against Your Original Requirements (Status)

Done (validated by code inspection and/or executed tests):
- Tool-call arrays in TS tooling layer exist but are not executed in a default loop (TS `ToolStreamManager` is placeholder).
- Python has a real tool streaming module with optional tool execution loops (Python `cascadeflow/streaming/tools.py`), but `CascadeAgent.run()` does not close tool loops by default.
- Direct routing cost calculation is incorrect for real savings claims (`cascadeflow/agent.py` direct path uses `best_model.cost * (tokens_used/1000)`).
- Tier routing exists but is explicitly "stored, not yet active" / "being re-implemented".
- Cached token accounting is missing in results.

Not yet done (must be executed to claim "holistic picture"):
- Per-profile x per-path evaluation across OpenRouter/n8n/Vercel/LangChain with benchmark artifacts.
- Profile 1 A/B runs streaming vs non-streaming as a first-class deliverable artifact.
- TS/Python parity proven via golden transcript suite.
- Legacy/unused/outdated doc scan delivered as an artifact (plan includes, but not executed here).

Section summary: Plan V2 fixes the gap between "observations" and "validated engineered direction" by turning missing requirements into explicit deliverables with gates.

---

## 6) 2026 Developer Expectations Checklist (Expanded, Testable)

This section defines what forward-deployed engineers expect in 2026 and maps current behavior to gaps and concrete fixes.

6.1 Tool-loop closure semantics (agentic baseline)
- Expectation: tool calls execute until completion or `max_steps`; tool_call_id dedupe; retries/backoff; cancellation; partial failure handling; deterministic transcript replay.
- Current: Python tool loop exists inside streaming tool manager (`cascadeflow/streaming/tools.py`) but is not default-integrated in non-streaming `CascadeAgent.run()`; TS tool streaming loop is not implemented (placeholder).
- Fix direction: implement a shared "tool loop engine" that runs in both streaming and non-streaming modes and emits a canonical transcript.

6.2 Parallel tools and tool-call arrays
- Expectation: multiple tool calls in one assistant turn; run parallel when independent; deterministic transcript ordering; support mixed parallel + sequential dependency chains.
- Current: TS tool manager parses but does not execute; Python tool streaming supports executing tool calls, but parallel semantics + transcript guarantees are not formalized and not available in non-streaming default flow.
- Fix direction: first-class multi-tool execution in the loop engine with explicit merge semantics and configurable concurrency.

6.3 Message lists and transcripts (multi-turn, tool turns)
- Expectation: `messages: []` accepted as the primary API, preserving roles; tool call + tool result turns stored as replayable transcript.
- Current: Python supports `messages`, but parts of the system flatten to prompt strings (`messages_to_prompt`) and the direct non-tool path may lose role structure; TS supports `Message[]`.
- Fix direction: canonical transcript model used end-to-end; only flatten at the last possible provider boundary when required.

6.4 System prompt precedence and parity
- Expectation: explicit precedence rules (global system, per-agent system, per-step system) and identical behavior streaming vs non-streaming.
- Current: Python tool streaming explicitly injects `system_prompt` into messages; text streaming passes kwargs through but does not normalize system prompt into transcript; behavior likely diverges by provider.
- Fix direction: always normalize `system_prompt` into the canonical message list before routing/execution, then pass structured messages to providers where possible.

6.5 Cached tokens (accounting + pricing)
- Expectation: output includes `cached_input_tokens` where provider reports it; pricing includes cached token rules; savings attribution separates caching vs routing.
- Current: missing.
- Fix direction: unify a provider-usage schema and a `PriceBook` resolver with cached token support; emit separate savings categories.

6.6 Tier/KPI policy routing (Profile 3)
- Expectation: declarative policy constraints (latency SLOs, cost caps, quality floors) influence routing/cascading; every decision is auditable.
- Current: tier system exists but is not first-class / "being re-implemented".
- Fix direction: policy engine that outputs allowed routes + budgets + escalation constraints and emits a PolicyDecisionRecord.

6.7 Hooks/callbacks + observability
- Expectation: stable, structured events for model/tool/policy/validation steps; trace IDs; replayable transcripts; easy integration (LangChain/Vercel/n8n).
- Current: core callbacks exist, but tool-specific events and policy decision records are missing.
- Fix direction: consistent event schema in TS/Python with tests for ordering and completeness.

Section summary: This checklist becomes acceptance criteria for "agentic-ready" and drives the tests/examples we will ship.

---

## 7) Profile Mapping: Required Capabilities and Current Gaps

Profile 1: Support bot (streaming on/off)
- Must have: stable multi-turn handling, streaming parity, low latency, cost transparency per turn, verifier escalation only when needed.
- Current gap: accuracy on support benchmark is far below 90%; streaming parity not proven; cached token accounting missing.
- Engineered fix direction: improve cost correctness and telemetry first (so we can optimize); add streaming parity tests; add a support-tuned "validation profile" that uses verifier only for low-confidence answers.

Profile 2: Agentic payment analytics (multi-agent + tools + domains)
- Must have: default tool loop closure, parallel tool arrays, per-domain model routing config, strong hooks, multi-agent budget attribution.
- Current gap: TS tool streaming loop missing; Python non-streaming agent doesn't close loops; parallel tool semantics not first-class; BFCL failure handling needs robust fallback/error policy.
- Engineered fix direction: ship the tool loop engine + canonical transcript + event schema, then add domain policies and multi-agent budget ledger.

Profile 3: Reasoning + tier/KPI policy
- Must have: tier policy enforcement (cost/latency/quality), audit records, correct cost accounting, and accuracy floors via verifier escalation.
- Current gap: tier policy not first-class; Banking77 accuracy below 90% and savings is artifacted; cached tokens missing.
- Engineered fix direction: policy engine + audited decisions + fix cost correctness; re-run Banking77 and reasoning packs after measurement is correct.

Section summary: Each profile is currently blocked by at least one P0 capability (measurement correctness or tool-loop closure), so P0 work directly unlocks adoption.

---

## 8) Evaluation Matrix (Per Profile x Integration Path)

Required outputs per cell (Profile x Path):
- Metrics: accuracy, savings, latency p50/p95, verifier escalation rate, tool-loop success rate, model-call counts
- Cost report: input/output/cached tokens, unit prices, total cost, cost split (draft/verifier/tools)
- Artifacts: replayable transcript + structured event log (JSON)
- DX notes: setup time, config complexity, debuggability, failure modes

Benchmark packs per profile:
- Profile 1: customer support + streaming A/B pack + multi-turn regression pack
- Profile 2: tool_calls + tool_calls_agentic + BFCL subset + parallel-tools synthetic pack
- Profile 3: GSM8K + Banking77 + tier policy synthetic pack

Known blockers to close before matrix can be completed:
- OpenRouter: key missing in `.env` (live runs blocked)
- n8n: runtime not available (live runs blocked)

Section summary: This turns "holistic picture" into a reproducible grid of artifacts and gates, rather than anecdotes.

---

## 9) TS/Python Parity Plan (Prove It)

Deliverables:
- Parity matrix (capability-by-capability): tool loops, streaming, cost fields (incl cached), hooks/events, policy/tier routing, transcript schema.
- Golden transcript test suite in both languages:
  - same input transcript + tool stubs -> same routing decisions, same transcript shape, same cost-report schema fields.

Priority parity gaps (validated by inspection):
- Tool loop closure: TS missing, Python limited to streaming tool manager; non-streaming default flow does not close loops.
- Tool streaming: TS placeholder.
- Cost/usage schema: cached tokens missing, direct route cost incorrect.
- System prompt normalization: not canonicalized across streaming/non-streaming.

Section summary: Parity becomes test-driven and release-gated, not a doc claim.

---

## 10) Prioritized Improvement Roadmap (Engineered Fixes + Validation)

P0: Measurement correctness (savings must be real)
- Engineering:
  - Define a canonical `Usage` object: `input_tokens`, `output_tokens`, optional `cached_input_tokens`.
  - Make direct routing cost derive from provider usage; if provider doesn't return usage, explicitly mark "estimated" and never report "savings" as PASS.
  - Add a `PriceBook` + `PricingResolver` with priority: provider-reported cost (if any) -> LiteLLM pricing -> pinned internal defaults.
  - Emit cost breakdown per step (draft, verify, tools) and total.
- Validation:
  - Re-run Banking77 and confirm savings is not artifacted and includes drafter+verifier correctly.

P0: Tool loop engine + tool-call arrays + parallel tools
- Engineering:
  - Implement a shared loop engine used by `run()` and streaming: supports multi-tool arrays, parallel execution, retries, max steps, and transcript emission.
  - Canonical transcript format (assistant tool_calls + tool results).
  - Deterministic ordering + merge semantics for parallel tools.
- Validation:
  - Golden transcript tests: multi-tool arrays, parallel tools, retries, max-step termination.
  - Bench: agentic tool benchmarks must pass without manual wiring.

P0: Streaming parity and system prompts
- Engineering:
  - Normalize system prompts into canonical messages for both streaming and non-streaming paths before routing.
  - Ensure routing/cascade decision is derived from the same pre-execution context for streaming and non-streaming.
- Validation:
  - Profile 1 streaming A/B pack with assertions on decisions and cost fields.

P1: Tier/KPI policy engine (Profile 3 unblock)
- Engineering:
  - Declarative policies: cost cap, latency SLO, quality floor, escalation constraints.
  - Emit PolicyDecisionRecord per run (why chosen, why rejected).
- Validation:
  - Synthetic tier tests + rerun Profile 3 pack with policy enabled.

P1: Hooks/events/observability (integration unlock)
- Engineering:
  - Stable event schema in TS/Python: model_start/end, tool_start/end/error, cascade_decision, policy_decision, validation result, cost report emitted.
  - Trace IDs across all steps.
- Validation:
  - Event ordering/completeness tests; integration example prints structured trace.

P2: Pricing sync (keep prices current) + cached-token pricing
- Engineering:
  - Pricing sync workflow from LiteLLM pricing when configured; versioned pricebook with timestamped source.
- Validation:
  - Resolver unit tests + integration test with LiteLLM enabled.

Section summary: P0 makes metrics trustworthy and agentic flows automatic; P1 makes cascadeflow production-ready for enterprise constraints and integrations; P2 keeps pricing accurate and reduces long-term DX friction.

---

## 11) New Tests and Examples (Both SDKs, Minimal but Complete)

One main agentic example (Python + TS) must cover:
- Multi-turn messages and canonical transcript output
- Tool loop closure with tool-call arrays (>=2) and parallel execution
- Streaming on/off A/B
- Cost report with input/output/cached tokens and per-step cost breakdown
- Tier policy toggle + PolicyDecisionRecord

Small focused examples (few):
- Hooks/events consumption example
- Batch prompt/query arrays (if supported; if not, decide and implement)
- System prompt precedence example

Tests to add (both languages where applicable):
- Tool loop closure test
- Parallel tool array execution test
- Streaming parity test
- Pricing resolver test (including cached tokens)
- Tier policy decision + audit record test
- TS/Python golden transcript tests

Section summary: Examples define the DX surface area; tests make the claims enforceable and prevent regressions.

---

## 12) Repo Hygiene: Legacy/Unused Code, Docs Correctness, Gitignore Audit

Deliverables:
- Legacy/unused scan report: keep/remove/modernize list (with file paths).
- Docs audit: identify guides that claim behaviors that are not true by default (tool loops, cached tokens, streaming parity) and update them or mark as experimental.
- Gitignore audit: ensure local artifacts, dumps, and planning files cannot be committed.

Section summary: Reduce DX tax from stale docs and dead code; keep "what works" aligned with what docs claim.

---

## 13) Immediate Next Actions (Order Matters)

1) Sync `/tmp/cascadeflow-dx` to latest `origin/main` (to remove outdated base)
2) Fix measurement correctness (P0) and re-run Banking77 + cost-focused packs
3) Implement tool loop engine in Python and TS (P0) + add golden transcript tests
4) Fix streaming parity and system prompt normalization (P0) + Profile 1 A/B tests
5) Implement KPI/tier policy engine and audit records (P1) + Profile 3 pack
6) Add examples/tests and update docs (P1/P2)
7) Complete the full Profile x Path evaluation matrix (including OpenRouter/n8n once keys/runtime available)

Section summary: This sequence prevents "optimizing on broken measurement" and gets to agentic-ready behavior fastest with provable parity.
