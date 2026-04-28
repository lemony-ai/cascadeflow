---
name: cascadeflow
description: Use when building, extending, or debugging AI agents with cascadeflow (the agent runtime intelligence layer) — installing `cascadeflow` (Python) or `@cascadeflow/core`/`@cascadeflow/langchain` (TypeScript); using `CascadeAgent`/`ModelConfig`; harness APIs `cascadeflow.init`, `cascadeflow.run`, `@cascadeflow.agent`, `simulate`; `withCascade`/`CascadeFlow`; picking drafter+verifier pairs; per-step budget/compliance/KPI enforcement; quality validation; pre-routing by complexity; tool execution and multi-turn agent loops; presets (`auto_agent`, `get_cost_optimized_agent`); user profiles and tiers; decision traces; or wiring cascadeflow into LangChain, OpenAI Agents SDK, CrewAI, PydanticAI, Google ADK, n8n, or Vercel AI SDK. Also use when a user mentions "cascade", "drafter/verifier", "runtime intelligence", "in-process harness", "cost-optimized agent", "agent loop with cost control", or is working inside the lemony-ai/cascadeflow repo.
---

# cascadeflow

## What it is

**Agent runtime intelligence layer.** An in-process harness that sits *inside* the agent execution loop (not at the HTTP boundary) and makes per-step decisions on cost, latency, quality, budget, compliance, and energy. Sub-5ms overhead. Works alongside LangChain, OpenAI Agents SDK, CrewAI, PydanticAI, Google ADK, n8n, and Vercel AI SDK.

Two complementary pieces:

1. **Cascading** — try a cheap "drafter" model first, validate quality, escalate to a "verifier" model only when needed (40–85% cost savings).
2. **Runtime intelligence (harness)** — instrument the agent loop with budget caps, KPI weights, compliance gates, and a full per-step decision trace.

Python (`pip install cascadeflow`) and TypeScript (`@cascadeflow/core`). Docs: https://docs.cascadeflow.ai

## Why "in the loop" matters (the core pitch)

cascadeflow is **not a proxy or a gateway**. It runs inside the agent's process and sees every model call, tool call, and sub-agent handoff as it happens — so it can act on running state (cost so far, tool calls used, compliance flag) at *each step*, not just per HTTP request.

| Dimension | External proxy | cascadeflow harness |
|---|---|---|
| Scope | HTTP request boundary | Inside the agent loop |
| What it can see | One request at a time | Full run state (cost-so-far, step #, tool-calls used, budget remaining) |
| Optimization axes | Cost only | Cost · latency · quality · budget · compliance · energy — simultaneously |
| Latency overhead | 10–50 ms network RTT per call | <5 ms in-process per call |
| 10-step agent loop | +400–600 ms avoidable | negligible |
| Enforcement | Observe only | `allow` · `switch_model` · `deny_tool` · `stop` |
| Auditability | Request logs | Per-step decision trace (one entry per LLM/tool/handoff decision) |
| Business logic | None | Live KPI weights + targets injected at runtime |

This is what unlocks: stop-after-step-7 budget enforcement, deny-this-tool-mid-loop, switch-models-on-this-call, and a full audit trail of *why* every step did what it did. None of that is possible from outside the loop.

## When to use this skill

- User is building an AI agent and wants cost/latency/quality control *inside* the loop
- Code imports `cascadeflow`, `@cascadeflow/core`, `@cascadeflow/langchain`, `@cascadeflow/vercel-ai`, or `@cascadeflow/n8n-nodes-cascadeflow`
- Mentions budgets, compliance (GDPR/HIPAA/PCI), KPI weights, tool-call routing, decision traces, drafter/verifier
- Working inside `lemony-ai/cascadeflow` (examples, integrations, gateway server)

## Pick the right entry point (30-second decision)

| Situation | Use | File/pattern |
|---|---|---|
| Existing OpenAI/Anthropic app, want instant observability | `cascadeflow.init(mode="observe")` | Auto-patches the SDKs. Zero code changes in the app. |
| Existing app, no code changes at all, want gateway | `python -m cascadeflow.server` | Drop-in OpenAI/Anthropic-compatible proxy; point client at `http://127.0.0.1:<port>/v1` |
| New agent, want the default "just works" cascade | `auto_agent()` or `get_cost_optimized_agent()` | Presets — fastest path; no model picking required |
| New agent, custom drafter+verifier | `CascadeAgent(models=[drafter, verifier])` | Both languages |
| Agent function with budget + policy metadata | `@cascadeflow.agent(budget=..., compliance=..., kpi_weights=...)` | Attaches metadata; combine with `cascadeflow.run()` for enforcement |
| Scoped run with budget and full trace | `with cascadeflow.run(budget=0.50, max_tool_calls=10) as session:` | Primary harness pattern |
| Inside LangChain / OpenAI Agents / CrewAI / PydanticAI / Google ADK / Vercel AI / n8n | Use the integration package | Don't reinvent — the integrations preserve tool calling, streaming, callbacks |

## Minimum viable cascade

**Python:**

```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),  # drafter
    ModelConfig(name="gpt-4o",      provider="openai", cost=0.00625),   # verifier
])

result = await agent.run("What's the capital of France?")
print(result.content, result.model_used, result.total_cost, result.cost_saved)
```

**TypeScript:**

```ts
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.000375 },
    { name: 'gpt-4o',      provider: 'openai', cost: 0.00625  },
  ],
});

const r = await agent.run('What is TypeScript?');
console.log(r.modelUsed, r.totalCost, r.savingsPercentage);
```

**Even faster — presets (Python):**

```python
from cascadeflow import auto_agent, get_cost_optimized_agent

agent = auto_agent()                       # picks a sensible pair
# or: get_cost_optimized_agent(), get_balanced_agent(),
#     get_quality_optimized_agent(), get_speed_optimized_agent(),
#     get_development_agent()
```

## Runtime intelligence — the harness

This is what makes cascadeflow different from a proxy or a model router. The harness runs **inside** the agent loop and decides per step.

### Three modes, safe rollout

- `off` — no instrumentation (default)
- `observe` — patches OpenAI + Anthropic SDKs, records cost/tokens/decisions, enforces nothing
- `enforce` — same, plus applies actions (see below)

### Per-step actions the harness can take

`allow` · `switch_model` · `deny_tool` · `stop`

Every LLM call, tool call, and sub-agent handoff is a decision point. The harness reads the current run state (cost so far, budget remaining, compliance flag, KPI weights) and chooses one of the four actions.

**Stop reasons (verbatim strings on the trace + on `HarnessStopError.reason`):**

`budget_exceeded` · `max_tool_calls_reached` · `compliance_no_approved_model` · `latency_limit_exceeded` · `energy_limit_exceeded`

### Handling stops gracefully (don't crash the demo)

In `enforce` mode the harness raises a typed exception when it stops a run. Catch them so the agent can summarize and exit cleanly:

```python
from cascadeflow.schema.exceptions import BudgetExceededError, HarnessStopError

try:
    result = await agent.run(query)
except BudgetExceededError as e:
    print(f"Stopped: budget exceeded. Remaining: ${e.remaining:.4f}")
except HarnessStopError as e:
    print(f"Stopped: {e.reason}")  # e.g. "max_tool_calls_reached"
finally:
    print(session.summary())   # cost/steps/tool_calls captured up to the stop
    session.save("run.jsonl")  # full trace still exportable
```

`max_latency_ms` is **cumulative across the run** (not per step) — `latency_used_ms` accumulates and triggers `latency_limit_exceeded` when it crosses the cap.

### Scoped runs with budget + trace (the demo-worthy pattern)

```python
import cascadeflow

cascadeflow.init(mode="enforce")   # or "observe" while you tune

with cascadeflow.run(
    budget=0.50,                    # hard USD cap
    max_tool_calls=10,
    max_latency_ms=15000,           # cumulative across the run
    max_energy=None,
    kpi_weights={"quality": 0.6, "cost": 0.3, "latency": 0.1},
    compliance="gdpr",              # blocks non-compliant models
) as session:
    result = await agent.run("Analyze this dataset")
    print(session.summary())        # see shape below
    for entry in session.trace():   # per-step decision audit
        print(entry)
    session.save("run.jsonl")       # exportable trace — great for demos / submissions
```

### Shapes you'll actually print

`session.summary()` → dict:

```python
{
  "run_id": "ab12cd34ef56", "mode": "enforce", "step_count": 7, "tool_calls": 3,
  "cost": 0.0421, "savings": 0.0118, "latency_used_ms": 4820.4, "energy_used": 0.0,
  "budget_max": 0.50, "budget_remaining": 0.4579,
  "last_action": "allow", "model_used": "gpt-4o-mini", "duration_ms": 5103.2,
}
```

`session.trace()` → list of dicts, one per decision:

```python
{
  "action": "switch_model",          # allow | switch_model | deny_tool | stop
  "reason": "budget_pressure",       # human-readable; on stop it's the reason code
  "model": "gpt-4o-mini",
  "run_id": "ab12cd34ef56",
  "mode": "enforce",
  "step": 4,
  "timestamp_ms": 1730000123456.0,
  "tool_calls_total": 2,
  "cost_total": 0.0312,
  "latency_used_ms": 2400.1,
  "energy_used": 0.0,
  "budget_state": {"max": 0.50, "remaining": 0.4688},
  "applied": true,                   # false for observe-mode "would have"
  "decision_mode": "pre_call",       # optional
}
```

`session.save("run.jsonl")` writes one session-header line + one trace line per decision. `HarnessRunContext.load("run.jsonl")` reads it back as `{"session": ..., "traces": [...]}`.

### Policy metadata on agent functions

```python
@cascadeflow.agent(
    budget=0.20,
    kpi_weights={"quality": 0.6, "cost": 0.3, "latency": 0.1},
    compliance="gdpr",
)
async def my_agent(query: str): ...
```

`@cascadeflow.agent` **attaches metadata** — it doesn't change the function's runtime by itself. Combine with `cascadeflow.init(mode="enforce")` and/or `cascadeflow.run(...)` to enforce. Works on sync or async functions.

### Zero-code config (env + file)

All harness settings also read from env vars and a config file — so students can demo `observe → enforce` rollout without touching code.

```bash
export CASCADEFLOW_HARNESS_MODE=enforce
export CASCADEFLOW_HARNESS_BUDGET=0.50
export CASCADEFLOW_HARNESS_MAX_TOOL_CALLS=10
export CASCADEFLOW_HARNESS_KPI_WEIGHTS='{"quality":0.6,"cost":0.3,"latency":0.1}'
# or point at a file:
export CASCADEFLOW_CONFIG=./cascadeflow.yaml
```

Precedence: explicit kwargs > env > config file > defaults. `HarnessInitReport.config_sources` tells you which source won.

### Simulate before running (for tuning and pitch slides)

```python
from cascadeflow.harness import simulate
report = simulate(...)   # model a run against historical traces without calling providers
```

## Agent loops — tools, multi-turn, multi-agent

cascadeflow's harness is built for multi-step agents, not just single calls.

- **Tool calling** — universal tool format across providers; drafter can be pinned for simple tool calls while verifier handles complex reasoning.
- **Multi-turn loops** — automatic tool call → result → re-prompt with full history preservation (`tool_calls`, `tool_call_id` preserved across turns).
- **Per-tool-call gating** — block or re-route tools based on risk/complexity (TS: `tool-risk.ts`, `ToolRouter`).
- **Agent-as-a-tool / multi-agent** — delegate sub-tasks to other agents; each sub-call runs through the same harness (sub-call decisions show up on the parent's trace).
- **Hooks & callbacks** — register a `CallbackManager` to stream cost/decision events to a dashboard.
- **Self-improving** — because the harness sees every step, every tool result, and every quality score over time, it accumulates the data needed to tune routing strategies and escalation thresholds. Long-lived agents get smarter the more they run.

### Wiring tools to the agent (Python)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.tools import ToolConfig, ToolExecutor

def get_weather(city: str) -> str:
    return f"{city}: 18°C, cloudy"   # mock

tool_configs = [
    ToolConfig(
        name="get_weather",
        description="Get current weather for a city.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        function=get_weather,
    ),
]

executor = ToolExecutor(tool_configs)
agent = CascadeAgent(
    models=[
        ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),
        ModelConfig(name="gpt-4o",      provider="openai", cost=0.00625),
    ],
    tool_executor=executor,           # executor goes on the agent
)

# Schemas (no function ref) go on the call:
schemas = [{"name": t.name, "description": t.description, "parameters": t.parameters}
           for t in tool_configs]
result = await agent.run("What's the weather in Paris?", tools=schemas)
```

### Streaming decision events to a dashboard

```python
import cascadeflow
from cascadeflow.telemetry.callbacks import CallbackManager, CallbackEvent

manager = CallbackManager()

def on_decision(data):
    # data.event, data.query, data.data — push to your dashboard / Slack / OTel
    print(data.event.value, data.data)

manager.register(CallbackEvent.CASCADE_DECISION, on_decision)
manager.register(CallbackEvent.MODEL_CALL_COMPLETE, on_decision)

cascadeflow.init(mode="enforce", callback_manager=manager)
```

Available events: `QUERY_START`, `COMPLEXITY_DETECTED`, `MODEL_CALL_START`, `MODEL_CALL_COMPLETE`, `MODEL_CALL_ERROR`, `CASCADE_DECISION`, `CACHE_HIT`/`MISS`, `QUERY_COMPLETE`, `QUERY_ERROR`. For LangChain, prefer `get_cascade_callback()` (covered below).

**Starter examples in the repo** (all exist — verified):

| Pattern | Python | TypeScript |
|---|---|---|
| Tool execution | `examples/tool_execution.py` | `packages/core/examples/nodejs/tool-execution.ts` |
| Multi-turn tool loop | `examples/multi_step_cascade.py` | `packages/core/examples/nodejs/agentic-multi-agent.ts` |
| Streaming tools | `examples/streaming_tools.py` | `packages/core/examples/nodejs/streaming-tools.ts` |
| Multi-agent / agent-as-a-tool | `examples/agentic_multi_agent.py` | `packages/core/examples/nodejs/agentic-multi-agent.ts` |
| Harness + budget enforcement | `examples/enforcement/basic_enforcement.py` | — |
| User budget tracking | `examples/user_budget_tracking.py` | — |
| Guardrails | `examples/guardrails_usage.py` | — |
| Rate limiting | `examples/rate_limiting_usage.py` | — |

## Picking drafter + verifier (the decision that decides savings)

The drafter should be ~8–20× cheaper than the verifier and actually able to answer the common case. If the drafter is too weak, escalation rate climbs and savings collapse.

| Use case | Drafter | Verifier |
|---|---|---|
| General chat (OpenAI) | `gpt-4o-mini` | `gpt-4o` or `gpt-5` |
| Cross-provider | `claude-haiku` / `gpt-4o-mini` | `claude-sonnet-4-5` / `gpt-5` |
| Code / reasoning | `gpt-4o-mini` | Reasoning model (o-series, `claude-sonnet-4-5`, `deepseek-r1`) |
| Local / edge | Ollama small (`llama3.1:8b`, `qwen2.5:7b`) | Local large or cloud fallback |

**TS helpers to pick from your configured LangChain models** (all real — exported from `@cascadeflow/langchain`):

```ts
import {
  findBestCascadePair, discoverCascadePairs, analyzeModel,
  validateCascadePair, analyzeCascadePair, suggestCascadePairs,
} from '@cascadeflow/langchain';
```

## Pre-routing by complexity (TS)

For agents where most queries are simple and a few are hard, pre-route so HARD queries skip the drafter entirely and go straight to the verifier.

```ts
import { PreRouter, ComplexityDetector } from '@cascadeflow/langchain';
// PreRouter config uses ComplexityDetector to classify SIMPLE / MEDIUM / HARD
```

Python equivalent: `ComplexityDetector`, `QueryComplexity` from `cascadeflow.quality.complexity`.

## Quality validation

Default: length + confidence (logprobs) + format checks. Opt in to ML-based semantic similarity for better escalation decisions:

- Python: `pip install cascadeflow[semantic]` → `from cascadeflow.quality.semantic import SemanticQualityChecker`
- TS: `npm install @cascadeflow/ml @huggingface/transformers`, then `quality: { useSemanticValidation: true, semanticThreshold: 0.5 }` on `CascadeAgent`

Tune `qualityThreshold` (TS) / `quality_threshold` (Py) to hit a target drafter-handled rate. 0.6–0.8 is a reasonable hackathon default. Higher threshold → more escalations → less savings.

## Multi-tenant demos — user profiles & tiers

```python
from cascadeflow import UserProfile, UserProfileManager, TierLevel, TIER_PRESETS
# Per-user budget enforcement, tier-aware routing (FREE/STARTER/PRO/BUSINESS/ENTERPRISE)
```

See `examples/user_profile_usage.py` and `examples/user_budget_tracking.py`. Great for SaaS-style hackathon submissions.

## Framework integrations (pick one, don't reinvent)

All of the following exist in the repo — verified on current main:

| Framework | Package / module | Entry point |
|---|---|---|
| LangChain (TS) | `@cascadeflow/langchain` | `withCascade({ drafter, verifier, qualityThreshold })` |
| LangChain (Py) | `cascadeflow.integrations.langchain` | `CascadeFlow(drafter=..., verifier=..., quality_threshold=...)` |
| LangChain callbacks (Py) | `cascadeflow.integrations.langchain.langchain_callbacks` | `get_cascade_callback()` |
| OpenAI Agents SDK | `cascadeflow.integrations.openai_agents` | See `examples/integrations/openai_agents_harness.py` |
| CrewAI | `cascadeflow.integrations.crewai` | See `examples/integrations/crewai_harness.py` |
| PydanticAI | `cascadeflow.integrations.pydantic_ai` | See `examples/integrations/pydantic_ai_harness.py` |
| Google ADK | `cascadeflow.integrations.google_adk` | See `examples/integrations/google_adk_harness.py` |
| n8n | `@cascadeflow/n8n-nodes-cascadeflow` | CascadeFlow Model + CascadeFlow Agent nodes |
| Vercel AI SDK | `@cascadeflow/vercel-ai` | Middleware for `ai` package; 17+ extra providers |
| OTel / Grafana | `cascadeflow.integrations.otel` | See `examples/integrations/opentelemetry_grafana.py` |
| LiteLLM | `cascadeflow.integrations.litellm` | See `examples/integrations/litellm_providers.py` |

When adding cascadeflow to a project already using one of these, prefer the integration package over raw `CascadeAgent` — keeps tool calling, streaming, and callbacks working.

## Common pitfalls

- **`@cascadeflow.agent` alone does nothing at runtime.** It attaches metadata. Pair with `cascadeflow.init(mode="enforce")` and/or `cascadeflow.run(...)` to actually enforce budgets/compliance.
- **`observe` mode does not stop on overrun.** Switch to `enforce` (or wrap in `cascadeflow.run(budget=...)`) to actually cut off.
- **Drafter too weak → escalation rate ~100%.** Log `result.model_used` on a sample; if the drafter is never "accepted", lower `quality_threshold` or upgrade the drafter.
- **Pairing two models of similar price.** No meaningful savings. Pick drafter and verifier from different tiers.
- **Per-provider auth.** cascadeflow does not proxy auth. Each provider still needs its own `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.
- **GPT-5 streaming requires org verification.** Non-streaming works for all users. If streaming breaks during a demo, flip to non-streaming or pick a different verifier.
- **Forgetting `[all]` extras.** `pip install cascadeflow[all]` pulls every provider + semantic validation. Otherwise install per-provider extras (`[openai]`, `[anthropic]`, `[groq]`, `[together]`, `[vllm]`, `[huggingface]`, `[local]`, `[semantic]`, `[langchain]`, `[crewai]`).
- **Expecting local clones to match docs.** The GitHub README and PyPI package are authoritative. Check `cascadeflow.__version__` and compare against [latest release](https://github.com/lemony-ai/cascadeflow/releases).

## Prove the savings in your demo

```python
print(f"Model used: {result.model_used}")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Saved:    ${result.cost_saved:.6f}  ({result.cost_saved_percentage():.1f}%)")
print(f"Draft/verifier breakdown: ${result.draft_cost:.6f} / ${result.verifier_cost:.6f}")
```

For aggregate across a run: `session.summary()` (harness) or the LangChain callback:

```python
from cascadeflow.integrations.langchain.langchain_callbacks import get_cascade_callback
with get_cascade_callback() as cb:
    await cascade.ainvoke("...")
    print(cb.total_cost, cb.drafter_cost, cb.verifier_cost, cb.total_tokens)
```

TS: `result.savingsPercentage` directly — use it in the UI.

## Where to look next

- Docs: https://docs.cascadeflow.ai
- Python API: https://docs.cascadeflow.ai/api-reference/python/overview
- TypeScript API: https://docs.cascadeflow.ai/api-reference/typescript/overview
- Agent harness: https://docs.cascadeflow.ai/get-started/agent-harness
- Rollout guide (observe → enforce): https://docs.cascadeflow.ai/get-started/rollout-guide
- Providers + presets: https://docs.cascadeflow.ai/developers/providers-and-presets
- Python examples: `./examples/` — start with `basic_usage.py`, `multi_step_cascade.py`, `tool_execution.py`, `enforcement/basic_enforcement.py`
- TS examples: `./packages/core/examples/nodejs/` — start with `basic-usage.ts`, `tool-calling.ts`, `agentic-multi-agent.ts`, `cost-tracking.ts`

## Red flags — stop and re-check

- Writing your own retry/escalation loop around two model calls → use `CascadeAgent` or a preset.
- Hand-rolling budget tracking on top of OpenAI/Anthropic calls → use `cascadeflow.init(mode="enforce")` + `cascadeflow.run(budget=...)`.
- Computing cost savings manually by subtracting hardcoded prices → use `result.total_cost` / `result.cost_saved` / `result.savings_percentage`, or the LangChain callback.
- Drafter and verifier from the same tier (e.g. `gpt-4o` + `gpt-4o`) → no meaningful savings.
- Treating `@cascadeflow.agent` as enforcement — it's metadata only.
- Demoing `observe` mode and claiming "budget enforced" — observe doesn't stop calls. Use `enforce` or `run(budget=...)`.
