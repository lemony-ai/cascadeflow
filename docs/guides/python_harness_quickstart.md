# Python Harness Quickstart

This guide covers the in-process harness API:

- `init(...)` for global defaults and SDK instrumentation
- `run(...)` for per-request scoped budgets/limits and traceability
- `@agent(...)` for attaching policy metadata to agent functions

## Install

```bash
pip install "cascadeflow[openai]"
```

Optional integrations stay opt-in:

```bash
pip install "cascadeflow[openai,openai-agents]"
pip install "cascadeflow[crewai]"
pip install "cascadeflow[google-adk]"
```

## 1) Initialize Harness

```python
from cascadeflow import init

report = init(
    mode="observe",      # off | observe | enforce
    budget=1.0,          # default per-run budget cap
    max_tool_calls=8,    # default per-run tool call cap
)

print(report.mode)
print(report.instrumented)
print(report.detected_but_not_instrumented)
```

`init(...)` is explicit and never auto-enables integrations.

## 2) Track One Scoped Run

```python
from openai import OpenAI

from cascadeflow import run

client = OpenAI()

with run(budget=0.25, max_tool_calls=4) as session:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize model cascading in one sentence."}],
    )

    print(response.choices[0].message.content)
    print(session.summary())
    print(session.trace())
```

## 3) Attach Agent Metadata

`@agent(...)` attaches policy metadata to your function without changing how the
function executes.

```python
from cascadeflow import agent

@agent(
    budget=0.2,
    kpi_targets={"quality": 0.9},
    kpi_weights={"cost": 0.5, "latency": 0.5},
    compliance="strict",
)
def support_agent(task: str) -> str:
    return f"Handled: {task}"

print(support_agent.__cascadeflow_agent_policy__)
```

## Minimal Checklist

1. Call `init(...)` once at process startup.
2. Wrap each unit of work in `with run(...):`.
3. Use `run.summary()` and `run.trace()` for auditability and tuning.
