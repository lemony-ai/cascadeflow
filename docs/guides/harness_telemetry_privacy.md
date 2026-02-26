# Harness Telemetry and Privacy

Use this guide when you want harness observability without leaking user content.

## What the Harness Records

Each `run.trace()` decision entry includes:

- `action`, `reason`, `model`
- `run_id`, `mode`, `step`, `timestamp_ms`
- `cost_total`, `latency_used_ms`, `energy_used`, `tool_calls_total`
- `budget_state` (`max`, `remaining`)
- `applied`, `decision_mode` (when available)

The trace is scoped to the current `run()` context.

## What the Harness Does Not Record

By default, harness decision traces do not include:

- raw prompts or user messages
- model response text
- tool argument payloads

This keeps decision telemetry focused on policy/routing state instead of request content.

## Callback Emission (Optional)

If you provide a callback manager, each harness decision emits `CallbackEvent.CASCADE_DECISION`.

```python
from cascadeflow import init, run
from cascadeflow.telemetry.callbacks import CallbackEvent, CallbackManager

manager = CallbackManager()

def on_decision(event):
    print(event.data["action"], event.data["model"])

manager.register(CallbackEvent.CASCADE_DECISION, on_decision)

init(mode="observe", callback_manager=manager)

with run(budget=1.0) as r:
    ...
```

The emitted callback uses `query="[harness]"` and `workflow="harness"` to avoid passing user prompt content.

## Per-Run Summary Logging

When a scoped run exits (and recorded at least one step), the harness logs a summary on logger `cascadeflow.harness`:

- run id, mode, steps, tool calls
- cost/latency/energy totals
- last action/model
- remaining budget

Use standard Python logging controls to direct this to your existing log sink.
