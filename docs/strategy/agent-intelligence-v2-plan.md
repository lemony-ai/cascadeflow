# Agent Intelligence V2 Plan

Last updated: February 25, 2026
Status: Planning (no implementation in this document)
Supersedes: agent-intelligence-v1-plan.md

## 1. Objective

Make cascadeflow the default **in-process agent intelligence harness** for teams that need runtime control over cost, latency, quality, risk, budget, energy, and business KPIs.

Not a proxy. Not a hosted dependency. A local-first infrastructure layer that can influence agent decisions during execution.

### 1.1 Winning Criteria

This plan is successful only if all three pillars are achieved:

1. **Low-friction install**
   - Time-to-first-value under 15 minutes
   - Existing apps can activate in 1-3 lines
   - Explicit opt-in, no breaking changes for current users
2. **In-loop business KPI control**
   - Policies can influence step-level decisions and tool usage at runtime
   - Hard constraints and soft KPI preferences both supported
   - Decisions are explainable (`why` + `what action`)
3. **Reproducible benchmark superiority on realistic workflows**
   - Better or equal quality vs baseline while improving cost/latency
   - Results reproducible with pinned configs, prompts, models, and scripts
   - Agentic benchmarks include tool loops and multi-step workflows (not only static QA)

## 2. Product Thesis (Grounded)

Most routers and gateways optimize at request boundaries. The bigger opportunity is inside agent execution:

- Per-step model decisions based on agent state
- Per-tool-call gating based on remaining budget
- Runtime-aware stop/continue/escalate actions
- Business KPI injection during agent loops
- Learning from outcomes to improve future routing

This is the moat: **in-process harness for agent decisions**, not external provider routing.

### What Competitors Already Do (and Why That Is Not Enough)

- External routers/gateways already do strong request-level routing, fallback, and policy checks.
- Agent frameworks already expose hook systems and guardrails.

The remaining gap is **cross-framework, local-first, step-level optimization with shared policy semantics**:
- one policy model across different agent stacks,
- one observability model across direct SDK + frameworks,
- one enforcement model across tool loops and sub-agent calls.

### Why External Proxies Stay Structurally Limited

A proxy sees: `POST /v1/chat/completions { model, messages, tools }`.

cascadeflow's harness sees: agent state, step count, budget consumed, tool call history, error context, quality scores on intermediate results, domain, complexity, conversation depth, and any user-defined business context.

This information asymmetry is structural and permanent. Replicating in-process agent state awareness from an external proxy requires fundamental architectural changes — not a feature addition.

## 3. Target Users and Segments

- Startups shipping AI agents in existing products
- Platform teams standardizing agent behavior across products and tenants
- Individual developers are supported, but V2 optimization is for teams with production constraints

Primary constraints (hard):
- Max cost, max latency, max tool calls, risk/compliance gates, max energy

Secondary constraints (soft):
- Weighted KPI preferences that influence model/tool decisions when hard limits are not violated

## 4. V2/V2.1 Release Contract (Single Plan)

This document contains both releases in one plan with explicit boundaries:

| Area | V2 (Python-first) | V2.1 |
|---|---|---|
| Core harness API (`init`, `run`, `@agent`) | Python | TypeScript parity |
| Auto-instrumentation | OpenAI Python client | Anthropic Python + OpenAI/Anthropic TS clients |
| Integrations | OpenAI Agents SDK, CrewAI, LangChain (Python) + regression checks for existing integrations | TS integration parity + deeper framework convergence |
| Policy semantics | Defined and validated in Python | Same semantics validated in TS parity fixtures |
| Launch target | Production-ready Python harness + reproducible benchmarks | Cross-language parity release |

## 5. V2 Product Definition

V2 ships an **agent harness** as an optional, integration-first intelligence layer:

- Not enabled by default
- No cloud dependency required
- Works in existing apps/agents with minimal code changes (target: 1-3 lines)
- Default behavior remains unchanged unless explicitly enabled
- All framework-specific integrations are separate packages (not bundled with core)

### Harness Modes

- `off`: No harness evaluation (default for all existing users)
- `observe`: Evaluate + emit decisions, no behavior change (safe production rollout)
- `enforce`: Apply harness actions at runtime

### Recommended Rollout for Users

1. Start with `observe` in production
2. Validate traces + false positives + overhead
3. Enable `enforce` for selected tenants/channels

## 5.1 Low-Friction DX Contract (Must-Haves)

- Explicit activation only: no hidden patching.
- Existing code path preserved if harness is `off`.
- If auto-instrumentation is not safe in a runtime, users can use explicit adapter hooks (fallback mode).
- Quickstarts prioritize existing applications first, greenfield second.

## 5.2 DX Philosophy

### Principle: Invisible infrastructure, not wrappers

The gold standard DX is Sentry, DataDog, OpenTelemetry — you activate it, your existing code doesn't change.

cascadeflow targets this with **auto-instrumentation where safe**, plus **framework-native hooks** in optional integration packages.

> **Note**: The APIs shown below (`cascadeflow.init()`, `cascadeflow.run()`, `@cascadeflow.agent()`) are the **target V2 API design**. They do not exist today. Current API is `CascadeAgent(models).run(query)`. Building these APIs is the V2 deliverable.

### Tier 1: Zero-change activation (core, target API)

```python
import cascadeflow

cascadeflow.init(mode="observe")
# Every openai call in your app is now observed.
# No code changes. No wrappers.
# Example startup diagnostics:
# [cascadeflow] instrumented: openai
# [cascadeflow] detected but not instrumented in V2: anthropic (planned V2.1)

cascadeflow.init(mode="enforce")
# Now actively cascading, routing, and enforcing budgets.
```

How it works: `init()` patches LLM client libraries at the call level. This is the same proven pattern used by Sentry, DataDog APM, and OpenTelemetry auto-instrumentation.

V2 scope: `openai` Python client patching only. `anthropic` client patching follows in V2.1. Auto-instrumentation covers code that calls the `openai` SDK directly. Frameworks that abstract over the SDK (LangChain's `ChatOpenAI`, CrewAI via LiteLLM) require their respective integration packages for full coverage.

### Tier 2: Agent-scoped harness (core, target API)

```python
async with cascadeflow.run(budget=0.50, max_tool_calls=10) as run:
    # Your existing agent code
    result = await my_agent.invoke({"task": "Fix the login bug"})

    print(run.cost)        # $0.12
    print(run.savings)     # 68%
    print(run.tool_calls)  # 4 of 10 budget used
```

A context manager scopes budget tracking and harness decisions to an agent run. No restructuring of agent code required.

### Tier 3: Decorated agent with KPIs (core, target API)

```python
import openai

@cascadeflow.agent(
    budget=0.50,
    kpi_targets={"quality_min": 0.90, "latency_ms_max": 3000},
    kpi_weights={"cost": 0.4, "quality": 0.3, "latency": 0.2, "energy": 0.1},
    compliance="gdpr",
)
async def customer_support_agent(task: str):
    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": task}],
    )
    return response.choices[0].message.content
```

A decorator adds metadata. The function body doesn't change.

### Tier 4: Framework-specific deep integration (integration packages)

```python
# Requires separate install — not bundled with core.
# These extras do not exist in pyproject.toml today and must be added in Phase D.

# pip install cascadeflow[langchain]
from cascadeflow.integrations.langchain import CascadeFlowCallbackHandler

# pip install cascadeflow[openai-agents]
from cascadeflow.integrations.openai_agents import CascadeFlowModelProvider

# pip install cascadeflow[crewai]
from cascadeflow.integrations.crewai import CascadeFlowHooks
```

Framework-specific packages provide deeper integration (state extraction, middleware hooks, framework-native telemetry). These are optional — Tier 1-3 work without them for code that calls the `openai` SDK directly.

### TypeScript Equivalent

```typescript
// Target API — does not exist in @cascadeflow/core today.
// TS parity is a V2.1 deliverable (see Section 16, Phase F).

import { cascadeflow } from '@cascadeflow/core';

// Tier 1: Auto-instrument
cascadeflow.init({ mode: 'enforce' });

// Tier 2: Scoped run
const result = await cascadeflow.run({ budget: 0.50 }, async (run) => {
  return await myAgent.invoke({ task: 'Fix the login bug' });
});

// Tier 4: Framework packages
// npm install @cascadeflow/langchain
// npm install @cascadeflow/openai-agents
// npm install @cascadeflow/vercel-ai  (already exists)
// npm install @cascadeflow/n8n         (already exists)
```

## 5.3 DX Execution Contracts (Required)

These contracts remove ambiguity for production teams:

1. **`init()` instrumentation diagnostics**
   - `init()` emits a startup summary of what was instrumented and what was detected but not instrumented in the current version.
   - V2 example: OpenAI instrumented, Anthropic detected-but-not-instrumented warning.
2. **`init()` + `run()` scope composition**
   - `init()` defines global defaults for calls outside any scoped run.
   - `run()` creates an isolated child scope.
   - Inside a `run()` scope, run-level settings override global defaults for that scope only.
   - Nested `run()` scopes are isolated; inner scope does not mutate outer scope.
3. **Existing `CascadeAgent` migration behavior**
   - `cascadeflow.init()` does not rewrite `CascadeAgent`'s core cascade behavior.
   - `CascadeAgent` can execute inside `cascadeflow.run()` to contribute to run-level budget/trace accounting.
4. **Configuration precedence**
   - Effective config resolution order: explicit code kwargs > environment variables > config file (`cascadeflow.yaml` / JSON) > library defaults.
   - `init()` without kwargs may resolve from env/file for platform deployments.

## 6. Scope (V2)

### In Scope

- Harness engine in core (init, run context, decorator, action evaluation)
- Auto-instrumentation of `openai` Python client library (V2 scope; `anthropic` client and TS parity in V2.1)
- Harness modes: `off | observe | enforce`
- Action vocabulary: `allow | switch_model | deny_tool | stop`
- Config precedence support for harness init (code kwargs > env vars > config file > defaults)
- Hard controls: max cost, max latency, max tool calls, risk gates, max energy
- Soft controls: weighted KPI preferences
- Step-level and tool-level harness hooks
- Energy dimension (optional, in core)
- Parity fixtures/spec for TS implementation in V2.1 (Python implementation ships in V2)
- Integration packages (separate install, not bundled with core):
  - `cascadeflow[openai-agents]` — OpenAI Agents SDK (NEW — extra must be added to pyproject.toml)
  - `cascadeflow[crewai]` — CrewAI via LLM hooks (NEW — extra must be added to pyproject.toml)
  - `cascadeflow[langchain]` — LangChain/LangGraph (EXISTS as code, extra must be added to pyproject.toml)
  - Existing integrations verified: Vercel AI SDK, n8n
- Named benchmark suite with acceptance gates

### Out of Scope (V2)

- Hosted control plane / Studio (future product)
- Mandatory migration for existing users
- Autonomous learning loop with remote training (future phase)
- Speculative agent execution (future phase)
- Carbon API integration (future; energy estimate is V2, live carbon data is not)
- MCP tool call interception (future phase)
- Google ADK integration (on demand)

## 7. Non-Negotiable Constraints

- Backward compatible: existing users see zero behavior change
- Opt-in only: `off` by default
- No default latency regression for non-harness users
- Harness decision overhead target: **<5ms p95**
- Cascade execution overhead: documented and expected (extra LLM call for verification)
- Preserve existing DX simplicity for non-harness users
- Framework integrations are never auto-installed with core
- Auto-instrumentation is explicit (`cascadeflow.init()`) — never hidden

## 8. Architecture

### 8.1 Package Boundaries

```
cascadeflow (core)
├── cascadeflow.harness          # Harness engine (NEW)
│   ├── init()                   # Auto-instrumentation entry point
│   ├── run()                    # Context manager for scoped runs
│   ├── agent()                  # Decorator for KPI-annotated agents
│   ├── actions                  # allow, switch_model, deny_tool, stop
│   ├── context                  # HarnessContext (runtime state)
│   └── instrument               # LLM client patching (openai, anthropic)
├── cascadeflow.rules            # Rule engine (EXISTS, extended)
├── cascadeflow.quality          # Quality validation (EXISTS)
├── cascadeflow.routing          # Routing (EXISTS)
├── cascadeflow.core.cascade     # Speculative cascade (EXISTS)
├── cascadeflow.telemetry        # Cost tracking + metrics (EXISTS)
└── cascadeflow.providers        # LLM providers (EXISTS)

cascadeflow[openai-agents]       # Integration package (NEW)
├── CascadeFlowModelProvider     # OpenAI Agents SDK ModelProvider
├── tool_guard                   # Tool call gating via Agents SDK hooks
└── trace_adapter                # Map Agents SDK traces to harness context

cascadeflow[crewai]              # Integration package (NEW)
├── CascadeFlowHooks             # CrewAI LLM call hooks
├── crew_context                 # Extract crew/agent/task state
└── step_callback                # Budget tracking per crew step

cascadeflow[langchain]           # Integration package (EXISTS, extended)
├── CascadeFlow(BaseChatModel)   # Existing LangChain wrapper
├── harness_callback             # NEW: LangGraph middleware for harness
└── state_extractor              # NEW: Extract LangGraph state for context
```

### 8.2 Core Harness Layer

Extend current rule context with runtime/loop state:

```python
@dataclass
class HarnessContext:
    # Identification
    agent_id: Optional[str] = None
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Budget tracking (hard controls)
    budget_max: Optional[float] = None
    budget_used: float = 0.0
    tool_calls_max: Optional[int] = None
    tool_calls_used: int = 0
    latency_max_ms: Optional[float] = None
    latency_used_ms: float = 0.0
    energy_max: Optional[float] = None
    energy_used: float = 0.0

    # Agent state
    step_count: int = 0
    tool_history: list[str] = field(default_factory=list)
    error_history: list[str] = field(default_factory=list)
    prior_actions: list[str] = field(default_factory=list)
    cascade_active: bool = False
    draft_model: Optional[str] = None
    verifier_model: Optional[str] = None
    draft_accepted: Optional[bool] = None

    # Soft controls (KPI weights, sum to 1.0)
    kpi_weights: Optional[dict[str, float]] = None

    # Compliance
    compliance_tags: list[str] = field(default_factory=list)

    # Harness mode
    mode: Literal["off", "observe", "enforce"] = "off"
```

### 8.3 Harness Action Surface

Actions the harness can take:

| Action | Description | When |
|---|---|---|
| `allow` | Proceed normally (default) | Hard limits not violated |
| `switch_model` | Use a different model for this call | Cost/quality/latency optimization |
| `deny_tool` | Block a tool call | Budget exhausted, risk gate, compliance |
| `stop` | Terminate the agent run | Hard budget exceeded, safety gate |

These actions are evaluated at three hook points:

- **Pre-LLM-call**: Before each model invocation (model selection, budget check)
- **Pre-tool-call**: Before each tool execution (tool gating, budget check)
- **Post-LLM-call**: After each model response (quality validation, state update)

In `observe` mode: actions are computed and logged but not applied.
In `enforce` mode: actions are computed, logged, and applied.

### 8.3.1 `switch_model` Resolution Path

`switch_model` is not a simple fallback list. It uses existing cascadeflow intelligence:

1. Rule constraints (tenant/channel/KPI/tier/workflow context)
2. Complexity + domain signals
3. Model capability and safety constraints (tool support, risk/compliance requirements)
4. Cost/latency/quality scoring over remaining candidate models

The selected model and reason are always included in the decision trace.

### 8.3.2 `deny_tool` Contract (Default)

Default behavior in V2:

1. **Prevention path (preferred):** if a tool is disallowed before model execution, the tool is removed/blocked from the callable set for that step.
2. **Interception path:** if a disallowed tool call is still emitted, return a synthetic structured tool result:
   - `{"error":"tool_denied","reason":"budget_exceeded","action":"deny_tool"}`
3. Continue the loop with the denial result in context so the agent can recover or stop.

Integrations may map this to framework-native interruption semantics, but the default contract remains structured and non-crashing.

### 8.4 Auto-Instrumentation Layer

Core patches LLM client libraries to intercept calls:

```python
# V2 scope — core auto-instrumentation:
# - openai (Python) — already an optional dep in pyproject.toml

# V2.1 scope:
# - anthropic (Python) — already an optional dep
# - openai (TypeScript) — in @cascadeflow/core

# Supported via integration packages (separate install):
# - litellm (existing integration module; optional dependency)
# - langchain ChatModels (via cascadeflow[langchain])
# - crewai LLM (via cascadeflow[crewai])
```

The patch intercepts `create()` / `acreate()` calls and:
1. Reads the current `HarnessContext` (from context manager or `contextvars`, not thread-local)
2. Evaluates harness rules (complexity, domain, budget state)
3. In `observe`: logs the decision, passes through unchanged
4. In `enforce`: applies action (switch model, cascade, deny)
5. Updates context (cost, latency, step count)

Implementation contract:
- Patch registration is idempotent (multiple `init()` calls are safe).
- Scoped runs use isolated contextvar state (including nested runs).
- A clean unpatch/reset path exists for tests and controlled shutdown.

### 8.5 Integration Layer

Ship as optional integration packages, same pattern as existing integrations:

- Explicit install (`pip install cascadeflow[crewai]`)
- Explicit enable/config
- No hidden activation from core install
- Try/except imports with `AVAILABLE` flags
- Graceful degradation when not installed

Each integration provides:
1. **State extraction**: Pull agent/framework state into `HarnessContext`
2. **Native hooks**: Use the framework's own extension points (not custom wrappers)
3. **Telemetry bridge**: Map framework traces to harness telemetry

| Integration | Framework Extension Point | What It Adds |
|---|---|---|
| `openai-agents` | `ModelProvider` at `Runner.run` level | Model routing, tool gating |
| `crewai` | `llm_hooks` (native CrewAI feature) | LLM call interception, crew state |
| `langchain` | `BaseChatModel` (existing) + LangGraph middleware | State extraction, callbacks |
| `vercel-ai` | Existing `@cascadeflow/vercel-ai` | Extend with harness config |
| `n8n` | Existing `@cascadeflow/n8n-nodes-cascadeflow` | Extend with harness node params |

## 9. Hard vs Soft Controls

### 9.0 KPI Input Schema

To avoid ambiguity, harness KPI config is split into two explicit inputs:

- `kpi_targets`: absolute goals/limits (for example `quality_min`, `latency_ms_max`)
- `kpi_weights`: optimization preferences used for scoring when hard limits are not violated

### Hard Controls (enforced when enabled)

| Control | Config | Action on Violation |
|---|---|---|
| Max cost per run | `budget=0.50` | `switch_model` (downgrade) or `stop` |
| Max tool calls | `max_tool_calls=10` | `deny_tool` |
| Max latency per run | `max_latency_ms=5000` | `switch_model` (faster) or `stop` |
| Risk/compliance gate | `compliance="gdpr"` | Route to compliant model or `deny_tool` |
| Max energy estimate | `max_energy=0.01` | `switch_model` (lighter) or `stop` |

### Soft Controls (influence, don't enforce)

Weighted KPI preferences that influence model/tool decisions when hard limits are not violated:

```python
cascadeflow.init(
    mode="enforce",
    kpi_weights={
        "cost": 0.4,       # 40% weight on cost optimization
        "quality": 0.3,    # 30% weight on quality
        "latency": 0.2,    # 20% weight on latency
        "energy": 0.1,     # 10% weight on energy efficiency
    }
)
```

Soft controls affect model scoring in the cascade routing decision. They do not trigger `deny_tool` or `stop`.

### 9.1 Prompt Caching Strategy

Prompt caching is complementary to cascading and budget enforcement.

V2:
- Capture cache-related usage signals where available (e.g., cached tokens) in telemetry.
- Expose cache metrics in traces and benchmark artifacts.
- Do not make cache-hit optimization a hard routing objective yet.

V2.1:
- Optional cache-aware scoring bias for compatible providers/models.
- Validate that cache-aware routing improves net economics without quality regressions.

### 9.2 Energy Estimation Specification (V2)

V2 uses a deterministic proxy estimate (not real-time grid carbon):

- `energy_units = model_coefficient * (input_tokens + output_tokens * output_weight)`
- `model_coefficient` comes from a versioned local mapping (fallback to default when unknown).
- `output_weight` defaults to >1 to reflect higher generation compute cost.

This keeps energy scoring deterministic, reproducible, and local-first. Live carbon-intensity routing remains post-V2.

## 10. TS/Python Parity Requirements

Parity means same core semantics, not necessarily identical APIs.

V2 ships Python first. TS parity is a V2.1 deliverable (Phase F). Parity fixtures are written in V2 Phase A as the TS implementation spec.

Target parity (V2.1):
- Same harness modes: `off | observe | enforce`
- Same action vocabulary: `allow | switch_model | deny_tool | stop`
- Same `HarnessContext` fields for budget/latency/energy/tool-depth
- Same fallback behavior when harness is disabled
- Same hook points: pre-LLM-call, pre-tool-call, post-LLM-call
- Comparable telemetry fields for analysis
- Shared parity test fixtures (written in V2, validated in V2.1)

## 11. Framework Integrations (V2)

### 11.1 OpenAI Agents SDK (`cascadeflow[openai-agents]`)

Required as official integration coverage in V2.

Integration approach:
- Use `ModelProvider` at `Runner.run` level (framework's native extension)
- NOT a custom wrapper around the SDK
- Harness evaluates at each agent step via the model provider
- Tool gating via tool-call inspection in model responses

Minimum capabilities:
- Harness runs in `observe` and `enforce` modes
- Tool-call gating (deny on harness action)
- Model recommendation/switch based on harness decision
- Budget tracking across multi-step agent runs
- No hard dependency forced onto all cascadeflow users

### 11.2 CrewAI (`cascadeflow[crewai]`)

Integration approach:
- Use CrewAI's native `llm_hooks` (before/after LLM calls)
- Extract crew/agent/task state into `HarnessContext`
- Budget tracking via `step_callback`

### 11.3 LangChain/LangGraph (`cascadeflow[langchain]`)

Integration approach:
- Extend existing `CascadeFlow(BaseChatModel)` wrapper
- Add LangGraph-specific middleware for state extraction
- Add harness-aware callback handler
- Preserve existing DX for current LangChain users

### 11.4 Existing Integrations

Verify and extend (no breaking changes):
- `@cascadeflow/vercel-ai`: Add harness config pass-through
- `@cascadeflow/n8n-nodes-cascadeflow`: Add harness mode parameter to nodes
- `cascadeflow.integrations.litellm`: Verify harness compatibility
- `cascadeflow.integrations.openclaw`: Verify harness compatibility

## 12. Transparency and Debugging

Auto-instrumentation must not be magic. Every harness decision is visible:

- `cascadeflow.init(mode="observe")`: Logs every decision (what it *would* do)
- `cascadeflow.init(mode="enforce", verbose=True)`: Rich console output showing cascade path
- Harness metadata is accessible via two paths depending on usage mode:
  - **Library mode** (in-process): Metadata on `HarnessContext` / `run` object — `run.last_action`, `run.model_used`, `run.draft_accepted`, `run.budget_remaining`, `run.run_id`
  - **Proxy mode** (HTTP gateway): `x-cascadeflow-*` response headers (existing proxy behavior, unchanged)
- `run.trace()` returns full decision log for a scoped run
- Harness decisions are emitted via existing `CallbackManager` events
- All decisions include: action taken, reason, model used, budget state, run_id for correlation

Default logging destination:
- Logger name: `cascadeflow.harness`
- `DEBUG`: per-step decisions and action reasons
- `INFO`: per-run summaries in `run()` scope
- `verbose=True`: adds rich console rendering on top of logger output (does not replace structured logging)

### 12.1 Run Object Surface (V2 Target API)

```python
run.cost              # float: total cost in scoped run
run.savings           # float: savings percentage vs selected baseline
run.tool_calls        # int: tool calls used
run.budget_remaining  # float|None: remaining budget if configured
run.model_used        # str|None: most recent selected model
run.last_action       # str: allow|switch_model|deny_tool|stop
run.draft_accepted    # bool|None: draft acceptance for last cascade decision
run.run_id            # str: correlation id
run.trace()           # list[dict]: full decision timeline
```

## 13. Benchmark and Validation Plan

Use live API runs and keep comparability with prior benchmark set. Winning claims require reproducible, public methodology.

### 13.1 Benchmark Families

- Baseline language/reasoning: MT-Bench, TruthfulQA
- Code correctness: HumanEval, SWE-bench Lite slices
- Classification/structured output: Banking77
- Tool use and agent loops: BFCL-style tool/function scenarios + internal loop tests
- Product realism: customer-support and multi-agent delegation scenarios already aligned with cascadeflow usage

### 13.2 Realistic Workflow Suite (Required)

Each benchmark run must include at least these workload types:

- Existing app integration flow (OpenAI SDK direct calls)
- Existing agent framework flow (OpenAI Agents SDK, LangChain/LangGraph, CrewAI)
- Tool-heavy flow (5+ loop steps, mixed tool success/failure)
- Budget-constrained flow (mid-run budget pressure)
- Risk/compliance-constrained flow (policy escalation and tool deny paths)

### 13.3 Reproducibility Protocol (Non-Negotiable)

- Pin exact git SHA, benchmark script version, model names, and provider endpoints.
- Store raw per-case outputs (JSON/JSONL), not only aggregate summaries.
- Record both quality metrics and economics metrics per case:
  - accepted/rejected,
  - draft acceptance,
  - total cost,
  - latency,
  - selected model path,
  - policy action path.
- Publish confidence intervals and sample sizes for reported improvements.
- Re-run on at least two separate days before public claims.

### 13.4 Superiority Criteria (Grounded)

To claim “winning” in go-to-market material:

- Quality: non-inferior to baseline on core tasks with agreed margin.
- Cost: statistically significant reduction on realistic agent workflows.
- Latency: no material regression for non-harness users; harness overhead p95 <5ms.
- Policy safety: false-positive enforcement rate under agreed threshold.
- DX: time-to-first-value within target and successful quickstart completion by external testers.

### 13.5 Launch Gates

- Observe mode must be behavior-identical to baseline (output parity checks).
- Enforce mode must show measurable value on at least three realistic workflow families.
- Benchmark scripts and result artifacts must be executable by third parties with documented setup.

## 14. Competitive Positioning

### 14.1 Ecosystem Baseline Capabilities

- Provider/model fallback and load balancing
- Request-level cost optimization (model selection)
- Cross-provider unified API access
- Low integration friction (URL change)
- Framework middleware/hooks, guardrails, and tracing

### 14.2 What Remains Unresolved Across These Tools

- No shared cross-framework policy semantics for business KPIs.
- Limited consistent in-loop controls across model/tool/agent-step decisions.
- Weak portability of optimization behavior across direct SDK use and framework use.
- Economic claims are often hard to reproduce end-to-end on realistic workflows.

### 14.3 Remaining Gap We Target

- Cross-framework policy semantics (one control model across stacks).
- In-loop optimization that combines cost, latency, quality, risk, and business KPIs.
- Local-first deployment without mandatory cloud control plane.
- Reproducible economic + quality gains under realistic agent workflows.

### 14.4 Positioning Against Current Market

| Category | Examples | Their Strength | cascadeflow Differentiator |
|---|---|---|---|
| Budget-only enforcement | AgentBudget, custom budget middleware | Fast setup for spend caps and loop stops | Multi-dimensional optimization: cost + quality + latency + KPI + energy + cascade validation |
| Proxy cost-control + observability | Helicone, similar gateway observability stacks | Fast request-level analytics/caching/rules without code-level harness changes | In-process agent-state decisions and step/tool-level policy enforcement inside loops |
| External routers/gateways | OpenRouter, Portkey, NotDiamond | Provider/routing control at API boundary | In-loop action control with agent state and policy context |
| Framework-native orchestration | OpenAI Agents SDK, LangGraph, CrewAI | Rich framework-specific hooks and orchestration | Cross-framework policy layer + unified KPI semantics |
| Single-provider optimization | Provider-native routing features | Tight provider integration and defaults | Multi-provider, user-economics-first optimization |

## 15. Risks and Mitigations

- **Risk**: Over-complex harness UX
  Mitigation: Default `off`, `observe` before `enforce`, 1-3 lines to activate. Progressive complexity.

- **Risk**: Auto-instrumentation surprises (patching library internals)
  Mitigation: Explicit `init()` required. Never hidden. `observe` mode first. Verbose logging available. Metadata on every response.

- **Risk**: "Always verifier" behavior in sensitive benchmarks
  Mitigation: Explicit harness reasons + scenario tests + calibrated hard/soft boundaries.

- **Risk**: TS/Python drift
  Mitigation: Shared parity fixtures and decision test cases.

- **Risk**: Integration sprawl
  Mitigation: One harness core, thin adapters per integration. Auto-instrumentation plus explicit adapter mode for hard runtimes.

- **Risk**: Framework API instability (breaking changes in LangGraph, CrewAI, etc.)
  Mitigation: Integrations are thin adapters (<500 lines). Core harness works via LLM client patching regardless of framework changes.

- **Risk**: LangChain/OpenAI build competing harness features
  Mitigation: Ship fast, position as complementary (not competing), framework-agnostic is the moat. LangChain's Deep Agents is LangChain-only. cascadeflow works with everything.

- **Risk**: LLM provider builds internal routing (GPT-5 internal router)
  Mitigation: Provider routing is single-provider and optimizes for provider economics. cascadeflow is multi-provider and optimizes for user economics/KPIs. Re-evaluate this risk quarterly with a documented competitive capability review.

- **Risk**: Harness decision overhead exceeds target
  Mitigation: Rule evaluation is CPU-only (no network calls). Benchmark continuously. Degrade gracefully (skip harness if overhead budget exceeded).

- **Risk**: Low-friction promise fails in real teams
  Mitigation: Track time-to-first-value in external pilot tests; gate launch on quickstart completion metrics.

- **Risk**: Benchmark claims are not trusted externally
  Mitigation: Publish reproducibility protocol, scripts, and raw artifacts for independent reruns.

## 16. Release Plan (Phased)

### Phase A: Harness Core Definition (2-3 weeks)

- Finalize `HarnessContext` schema
- Finalize action vocabulary and hook points
- Define `off | observe | enforce` mode behavior
- Write parity fixtures (Python first, TS fixtures as spec — TS implementation in V2.1)
- Design auto-instrumentation for `openai` Python client
- Add new extras to `pyproject.toml`: `langchain`, `openai-agents`, `crewai`

Exit criteria:
- Schema frozen
- Python parity fixture tests green
- Auto-instrumentation prototype patching `openai` Python client
- pyproject.toml extras defined (even if integration code is not yet complete)

### Phase B: Observe Mode (3-4 weeks)

- Implement `cascadeflow.init(mode="observe")` (NEW top-level API)
- Auto-instrument `openai` Python client (sync + async + streaming + tool calling)
- Emit startup instrumentation diagnostics (instrumented vs detected-but-not-instrumented SDKs)
- Implement `cascadeflow.run()` context manager
- Emit decision traces via `CallbackManager`
- Integrate with existing `RuleEngine` (extended with `HarnessContext`)
- Harness metadata on `HarnessContext` / `run` object

Note: Auto-instrumentation of `openai` client is the highest-risk engineering task. Patching async streaming, tool calling, retries, and `with_raw_response` requires exhaustive edge-case testing.

Exit criteria:
- `observe` mode produces zero behavior change (validated by benchmark)
- Decision traces are accurate and complete
- Overhead within <5ms p95 target
- All existing tests still pass (backward compatibility)
- Edge cases validated: streaming, async, tool calling, parallel tool calls, retries

### Phase C: Enforce Mode (3-4 weeks)

- Activate `switch_model`, `deny_tool`, `stop` actions
- Implement hard controls (budget, tool-call cap, latency, energy)
- Implement soft controls (KPI-weighted model scoring)
- Add safety fallbacks (graceful degradation on harness error)
- Implement `@cascadeflow.agent()` decorator

Exit criteria:
- Enforced behavior matches harness intent
- No critical regressions in benchmark suite
- Hard controls reliably enforced (100% of violations caught)
- Harness errors never crash the agent (fail-open)

### Phase D: Integration Packages (3-5 weeks, parallelizable with Phase C)

- `cascadeflow[openai-agents]`: ModelProvider + tool gating
- `cascadeflow[crewai]`: LLM hooks + crew state extraction
- `cascadeflow[langchain]`: Extend existing with harness callbacks
- Verify existing integrations: Vercel AI SDK, n8n, LiteLLM, OpenClaw
- Docs + quickstarts + examples for each integration

Exit criteria:
- Install and quickstart verified end-to-end for each integration
- CI and integration tests green
- Each integration <500 lines of framework-specific code

### Phase E: Benchmarks + Public Launch (2-3 weeks)

- Run full benchmark suite (baseline + agentic + harness scenarios)
- Publish reproducible benchmark results
- Write launch content (blog post, integration cookbooks)
- Go/No-Go checklist validated

Exit criteria:
- All acceptance gates met
- Benchmark results published and reproducible
- DX quickstart works for existing app/agent users with 1-3 lines of code

### Total V2 Timeline (Python): 14-18 weeks

This is the realistic timeline for Python-first delivery with one primary contributor. Phases C and D can overlap (integration packages start once enforce mode core is stable).

### V2 Success Scorecard (Must Pass Before Launch)

- **Low-friction install**
  - 80%+ of pilot users complete quickstart without maintainer help.
  - Median time-to-first-value under 15 minutes.
- **In-loop KPI control**
  - Policy actions (`switch_model`, `deny_tool`, `stop`) triggered and logged correctly in scenario tests.
  - Observe→enforce rollout shows no unexpected behavior in pilot tenants.
- **Benchmark superiority**
  - Quality non-inferior vs baseline on agreed benchmark set.
  - Statistically significant cost reduction on realistic agent workflows.
  - Harness overhead p95 under 5ms for decision path.

### Phase F: TypeScript Parity (V2.1, post-V2 launch)

- Port `cascadeflow.init()` / `run()` to `@cascadeflow/core`
- Auto-instrument `openai` TypeScript client (OpenAI Node SDK)
- Port `HarnessContext`, action evaluation, harness modes
- TS parity fixture tests green
- Extend `@cascadeflow/vercel-ai` and `@cascadeflow/n8n` with harness support

Estimated: 6-8 weeks after V2 Python launch.

### Phase G: Anthropic Client Instrumentation (V2.1)

- Auto-instrument `anthropic` Python client
- Auto-instrument `@anthropic-ai/sdk` TypeScript client
- Validate with Claude-based agent workflows

Estimated: 3-4 weeks (can parallel with Phase F).

### 16.1 Parallel Branch Workboard (Tick-Off)

Use this section as the single coordination board for parallel execution.

Branching model:
- Keep `main` always releasable.
- Use one integration branch for this program: `feature/agent-intelligence-v2-integration`.
- Contributors build on short-lived feature branches and merge to the integration branch first.
- Merge to `main` only after integration branch CI + benchmark gates are green.

Claim checklist (one owner per branch at a time):
- [x] `feat/v2-core-harness-api` — Owner: `@codex` — PR: `TBD` — Status: `completed`
- [x] `feat/v2-openai-auto-instrumentation` — Owner: `@claude` — PR: `TBD` — Status: `in-progress`
- [x] `feat/v2-enforce-actions` — Owner: `@codex` — PR: `TBD` — Status: `completed (ready for PR)`
- [ ] `feat/v2-openai-agents-integration` — Owner: `@codex` — PR: `TBD` — Status: `in-progress`
- [ ] `feat/v2-crewai-integration` — Owner: `@` — PR: `#` — Status: `claimed/in-progress/review/merged`
- [ ] `feat/v2-langchain-harness-extension` — Owner: `@codex` — PR: `TBD` — Status: `in-progress`
- [ ] `feat/v2-dx-docs-quickstarts` — Owner: `@` — PR: `#` — Status: `claimed/in-progress/review/merged`
- [ ] `feat/v2-bench-repro-pipeline` — Owner: `@` — PR: `#` — Status: `claimed/in-progress/review/merged`
- [ ] `feat/v2-security-privacy-telemetry` — Owner: `@codex` — PR: `TBD` — Status: `in-progress`

Merge gates per feature branch:
- [ ] Unit/integration tests green for touched scope
- [ ] Docs/examples updated for any API or behavior change
- [ ] Backward compatibility verified (`off` mode unchanged)
- [ ] Bench impact assessed (if runtime behavior changed)

Integration-branch promotion gates:
- [ ] Core + integration CI green
- [ ] Full benchmark suite rerun with reproducibility artifacts
- [ ] Quickstart verification for existing app and framework paths
- [ ] Go/No-Go checklist in Section 18 satisfied before merging to `main`

## 17. Future Phases (Post-V2, Not in Scope)

For roadmap visibility. These inform V2 telemetry design but are not V2 deliverables.

### Future: Speculative Agent Execution
- Extend speculative cascade from model-level to agent-step-level
- Speculative next-step execution with cheap models, rollback on validation failure
- Selective verification (not every step needs verification)
- Validated by: Sherlock (Microsoft, 2025), Speculative Actions (2025)

### Future: Adaptive Learning Engine
- Contextual bandit routing (replace/augment static rules)
- Per-agent, per-task performance tracking
- Online learning from outcomes, no offline training needed
- Cold-start with aggregated anonymous routing telemetry (opt-in)
- Validated by: EMNLP 2025 bandit routing papers, BATS (Google, 2025)

### Future: cascadeflow Studio (Cloud Product)
- Dashboard: real-time visualization of all dimensions
- Fleet suggestions: auto-recommend optimal model combinations
- Learning flywheel: shared (anonymized) routing data improves routing for all users
- A/B testing: compare routing strategies in production
- Custom KPI builder: visual interface for defining business dimensions
- V2 telemetry fields are designed to support Studio without breaking changes

### Future: MCP Integration
- Intercept MCP tool calls (not just function-calling)
- Apply harness logic to MCP server interactions
- Track MCP server latency/reliability as routing dimensions

### Future: Additional Dimensions
- Carbon-aware routing with live grid carbon intensity data
- Data residency / compliance-aware model selection
- Custom business KPI plugins (user-defined scoring functions)

## 18. Go/No-Go Checklist

Go when all are true (V2 Python launch):

- [ ] Harness layer is opt-in and backward compatible
- [ ] `cascadeflow.init()` auto-instruments `openai` Python client
- [ ] `observe` mode produces zero behavior change (benchmark-validated)
- [ ] `enforce` mode actions work correctly (switch_model, deny_tool, stop)
- [ ] Harness decision overhead <5ms p95
- [ ] Python parity fixture tests pass
- [ ] Core + integration CI green
- [ ] Benchmark comparison acceptable vs latest baseline
- [ ] OpenAI Agents SDK integration documented and validated
- [ ] CrewAI integration documented and validated
- [ ] LangChain integration extended and validated
- [ ] Existing integrations (Vercel AI, n8n) verified compatible (no regressions)
- [ ] DX quickstart works for existing app/agent users with 1-3 lines of code change
- [ ] External pilot median time-to-first-value <15 minutes
- [ ] Public benchmark results ready for launch
- [ ] Benchmark scripts + raw artifacts are reproducible by third parties
- [ ] pyproject.toml extras (`openai-agents`, `crewai`, `langchain`) defined and installable

V2.1 Go/No-Go (TS parity + anthropic):
- [ ] TS parity fixtures pass
- [ ] `@cascadeflow/core` exports `cascadeflow.init()` and `cascadeflow.run()`
- [ ] `anthropic` Python client auto-instrumentation validated
- [ ] `@anthropic-ai/sdk` TS client auto-instrumentation validated

## 19. Academic Validation

Key research validating this approach (all 2025):

- **BATS: Budget-Aware Tool-Use** (Google DeepMind) — Budget tracker module achieves comparable accuracy with 40% fewer tool calls, 31% cost reduction
- **Sherlock** (Microsoft) — Speculative execution + selective verification for agent workflows: 18% accuracy gain, 48% latency reduction
- **Speculative Actions** — Generalizes speculative decoding to agent actions (tool calls, API calls): up to 55% next-action prediction accuracy
- **Faster Cascades via Speculative Decoding** (Google, ICLR 2025) — Validates cascadeflow's core cascade architecture as a first-class research direction
- **GAR: Carbon-Aware Routing** — Treats carbon as first-class routing objective alongside accuracy and latency SLOs
- **Adaptive LLM Routing Under Budget Constraints** (EMNLP 2025) — Bandit-based routing outperforms static rules with no offline training
- **LLM Routing with Dueling Feedback** — Contextual dueling bandits for model routing with cost-performance balancing

## 20. Documentation Strategy: Human + Agent Readable

### Platform

All public documentation hosted on [Mintlify](https://www.mintlify.com/). Mintlify provides structured, searchable, API-aware docs with built-in support for code examples, OpenAPI specs, and MDX.

### Why This Matters Strategically

In 2026+, agents increasingly select their own tooling. When a coding agent (Cursor, Claude Code, Devin, OpenHands) is asked to "build an agent that optimizes costs," it will search for and evaluate libraries. If cascadeflow's documentation is the clearest, most structured, and most machine-parseable option, agents will recommend and integrate cascadeflow by default.

**The documentation is a product surface for two audiences: human developers and AI agents.**

Documentation must directly support the three winning pillars:
- fast activation (low-friction install),
- clear policy control patterns (in-loop KPI influence),
- transparent evidence (reproducible benchmark claims).

### Design Principles

**For humans:**
- 5-minute quickstart with copy-paste code (Tier 1: `init()` → instant savings)
- Progressive disclosure: simple first, advanced when ready
- Integration cookbooks per framework (LangGraph, OpenAI Agents SDK, CrewAI)
- Visual architecture diagrams
- Benchmark results with reproducible methodology
- Changelog and migration guides

**For agents (LLM-readable):**
- Structured, consistent markdown with clear headings and hierarchy
- Every API surface documented with typed signatures, parameter descriptions, return types, and concrete examples
- `llms.txt` and/or `llms-full.txt` at docs root — a single-file summary optimized for LLM context windows (see llmstxt.org convention)
- OpenAPI spec for the proxy gateway endpoints
- Decision trees in explicit if/then format: "If you need cost optimization for an agent → use `cascadeflow.init()`. If you need budget enforcement → use `cascadeflow.run(budget=X)`."
- Comparison pages with structured tables: cascadeflow vs OpenRouter, vs NotDiamond, vs Portkey — in a format agents can parse and reason about
- Code examples that are complete and runnable (no `...` ellipsis, no "fill in your code here")
- Explicit "when to use" and "when NOT to use" sections — agents make better recommendations when they understand boundaries
- Capability matrix: what works with which framework, which harness mode, which language

### Documentation Structure

```
docs/
├── quickstart.mdx              # 5-minute setup, Tier 1 (init)
├── concepts/
│   ├── how-cascading-works.mdx # Core cascade explained
│   ├── harness-modes.mdx       # off / observe / enforce
│   ├── hard-soft-controls.mdx  # Budget, KPIs, compliance
│   └── actions.mdx             # allow, switch_model, deny_tool, stop
├── guides/
│   ├── budget-enforcement.mdx  # Tier 2: run() context manager
│   ├── kpi-injection.mdx       # Tier 3: @agent() decorator
│   ├── observe-first.mdx       # Production rollout guide
│   └── benchmarks.mdx          # How to reproduce our benchmarks
├── integrations/
│   ├── openai-agents-sdk.mdx   # Cookbook + full example
│   ├── crewai.mdx              # Cookbook + full example
│   ├── langchain.mdx           # Cookbook + full example
│   ├── vercel-ai-sdk.mdx       # Existing, extended
│   ├── n8n.mdx                 # Existing, extended
│   └── litellm.mdx             # Existing
├── api-reference/
│   ├── python/                 # Auto-generated from docstrings
│   └── typescript/             # Auto-generated from TSDoc
├── comparisons/
│   ├── vs-openrouter.mdx       # Structured comparison
│   ├── vs-notdiamond.mdx
│   ├── vs-portkey.mdx
│   └── vs-litellm.mdx
├── llms.txt                    # Single-file LLM-optimized summary
└── llms-full.txt               # Complete API reference for agent context
```

### `llms.txt` Specification

A concise, structured file at the docs root that gives any LLM/agent everything it needs to evaluate and use cascadeflow:

```
# cascadeflow

> Agent intelligence harness for cost, quality, latency, and business KPI optimization.
> In-process library (not a proxy). Works inside agent loops with full state awareness.

## Install
pip install cascadeflow

## Quickstart (3 lines)
import cascadeflow
cascadeflow.init(mode="enforce")
# All openai SDK calls are now cascaded. 40-80% cost savings.

## When to use cascadeflow
- You run AI agents (LangGraph, CrewAI, OpenAI Agents SDK, or custom)
- You want to reduce LLM costs without changing agent code
- You need budget enforcement across multi-step agent runs
- You need to inject business KPIs into agent decisions

## When NOT to use cascadeflow
- Single one-off LLM calls (overhead not justified)
- You only use one model and don't want routing

## Key APIs
- cascadeflow.init(mode) — activate harness globally
- cascadeflow.run(budget, max_tool_calls) — scoped agent run with budget
- @cascadeflow.agent(budget, kpis) — annotate agent functions

## Integrations
- pip install cascadeflow[langchain]
- pip install cascadeflow[openai-agents]
- pip install cascadeflow[crewai]

## Docs: https://docs.cascadeflow.ai
```

### Timeline

Documentation is not a post-launch task. It ships with each phase:

- Phase A: `llms.txt`, concepts pages, API reference stubs
- Phase B: Quickstart (observe mode), `llms-full.txt`
- Phase C: Budget enforcement guide, KPI injection guide
- Phase D: Integration cookbooks (one per framework)
- Phase E: Comparison pages, benchmark results, launch blog post

## 21. Document Owners

- Product strategy: cascadeflow maintainers
- Technical design owner: core/runtime maintainers
- Integration owners: per package maintainer (same pattern as existing integrations)
- Documentation: maintained alongside code — every PR that changes API must update docs
