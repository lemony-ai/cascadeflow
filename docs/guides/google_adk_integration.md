# Google ADK Integration

Integrate cascadeflow harness with Google's Agent Development Kit (ADK) to get
budget enforcement, cost/latency/energy tracking, tool call counting, and full
trace recording across all agents in an ADK Runner.

---

## Design Principles

- **Plugin-based** — Uses ADK's `BasePlugin` system to intercept every LLM call
  across all agents in a Runner. One plugin covers the entire agent graph.
- **Opt-in** — Install `cascadeflow[google-adk]` and create a plugin explicitly.
  Never enabled by default. Core cascadeflow behavior is unchanged unless you
  explicitly wire this integration into `Runner(plugins=[...])`.
- **Fail-open** — Integration errors are logged but never break ADK execution
  (configurable).
- **No tool gating** — ADK's `tools_dict` is part of agent definition, not
  per-call. Budget gate via `before_model_callback` provides sufficient cost
  control. This is an intentional difference from the OpenAI Agents integration.

---

## Installation

```bash
pip install "cascadeflow[google-adk]"
```

Requires Python 3.10+ (ADK requirement).

Optional (more precise provider/model cost tracking in harness telemetry):

```bash
pip install litellm
```

---

## Quick Start

```python
import asyncio
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from cascadeflow import init, run
from cascadeflow.integrations.google_adk import enable

# 1. Initialize harness
init(mode="observe", budget=1.0)

# 2. Create the cascadeflow plugin
plugin = enable()

# 3. Pass it to the Runner
agent = Agent(name="my_agent", model="gemini-2.5-flash", instruction="Be helpful.")
runner = Runner(
    agent=agent,
    app_name="my_app",
    session_service=InMemorySessionService(),
    plugins=[plugin],
)

# 4. Run within a harness scope
async def main():
    with run(budget=0.5) as session:
        # ... run your agent ...
        print(f"Cost: ${session.cost:.6f}")
        print(f"Steps: {session.step_count}")
        print(f"Tool calls: {session.tool_calls}")

asyncio.run(main())
```

---

## Features

### Budget Enforcement

In `enforce` mode, the plugin short-circuits LLM calls when the budget is
exhausted by returning an `LlmResponse` with `error_code="BUDGET_EXCEEDED"`.

```python
init(mode="enforce", budget=0.10)  # Hard limit: $0.10
plugin = enable()
```

### Cost and Energy Tracking

Every LLM call is tracked with:
- **Cost** — Estimated from model pricing (USD per 1M tokens)
- **Energy** — Deterministic proxy coefficient for compute intensity
- **Latency** — Wall-clock time per call
- **Tool calls** — Count of `function_call` parts in responses

By default this uses cascadeflow's built-in pricing table. If you install
`litellm`, provider/model normalization can be more precise for some aliased
model identifiers.

### Trace Recording

All decisions are recorded in the `HarnessRunContext` trace:

```python
with run() as session:
    # ... run agents ...
    for event in session.trace():
        print(event)
        # {"action": "allow", "reason": "observe", "model": "gemini-2.5-flash", ...}
```

### Configuration

```python
from cascadeflow.integrations.google_adk import enable, GoogleADKHarnessConfig

plugin = enable(
    config=GoogleADKHarnessConfig(
        fail_open=True,           # Default: True. Never break ADK on integration errors.
        enable_budget_gate=True,  # Default: True. Block calls when budget exhausted.
    )
)
```

---

## Zero-Code Alternative

If you don't need per-agent plugin integration, you can route ADK through a
cascadeflow LiteLlm proxy by setting `base_url` on your Gemini model:

```python
# ADK uses LiteLlm under the hood — point it at your cascadeflow proxy
agent = Agent(
    name="my_agent",
    model="openai/gemini-2.5-flash",  # LiteLlm format
    instruction="...",
)
# Set OPENAI_API_BASE=http://localhost:8080/v1 to route through cascadeflow proxy
```

This gives you cost tracking at the proxy level without a plugin, but doesn't
provide budget enforcement or per-agent trace recording.

---

## Supported Gemini Models

| Model | Input $/1M | Output $/1M | Energy Coefficient |
|-------|-----------|-------------|-------------------|
| gemini-2.5-flash | $0.15 | $0.60 | 0.3 |
| gemini-2.5-pro | $1.25 | $10.00 | 1.2 |
| gemini-2.0-flash | $0.10 | $0.40 | 0.25 |
| gemini-1.5-flash | $0.075 | $0.30 | 0.2 |
| gemini-1.5-pro | $1.25 | $5.00 | 1.0 |

All OpenAI and Anthropic models from the shared pricing table are also
supported (e.g., when using LiteLlm provider prefixes).

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| `ImportError: google.adk` | `pip install "cascadeflow[google-adk]"` |
| Plugin not tracking calls | Ensure `plugin` is passed to `Runner(plugins=[plugin])` |
| Budget not enforced | Check `init(mode="enforce", ...)` — observe mode never blocks |
| Zero cost reported | Model name may not match pricing table; check for provider prefix stripping |
