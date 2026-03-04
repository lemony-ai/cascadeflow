# CrewAI Integration

Use cascadeflow as an explicit, opt-in harness integration for CrewAI via
`llm_hooks`.

## Design Principles

- Integration-only: nothing is enabled by default
- Works with existing CrewAI flows
- Harness behavior is controlled by `cascadeflow.init(...)` and `cascadeflow.run(...)`
- Fail-open integration path: harness integration errors should not break crew execution

## Install

```bash
pip install "cascadeflow[crewai,openai]"
```

`crewai` is optional and only installed when you request this extra.
Requires Python 3.10+.

Optional (more precise provider/model cost tracking in harness telemetry):

```bash
pip install litellm
```

## Quickstart

```python
from crewai import Agent, Crew, Process, Task

from cascadeflow import init, run
from cascadeflow.integrations.crewai import CrewAIHarnessConfig, enable

# Global harness defaults.
init(mode="enforce", budget=1.0)

# Explicitly register CrewAI hooks (integration-only behavior).
enable(
    config=CrewAIHarnessConfig(
        fail_open=True,
        enable_budget_gate=True,
    )
)

agent = Agent(
    role="Support Agent",
    goal="Answer support questions clearly and concisely.",
    backstory="You are helpful and direct.",
    allow_delegation=False,
    llm="openai/gpt-4o-mini",
)

task = Task(
    description="Explain why model cascading helps control agent costs.",
    expected_output="A concise explanation with one practical example.",
    agent=agent,
)

with run(budget=0.4) as session:
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    print(result)
    print(session.summary())
    print(session.trace())
```

## What This Integration Adds

- Budget gating in enforce mode (`before_llm_call` hook)
- Run metrics in `cascadeflow.run()` scope:
  - `cost`, `budget_remaining`, `step_count`, `latency_used_ms`, `energy_used`
- Full decision trace through `run.trace()`

## Current Scope

- This integration uses CrewAI hook points, so it tracks and gates calls without
  changing your crew/task definitions.
- Tool-level deny/switch actions are not currently applied in this integration path.

## Notes

- Existing non-CrewAI users are unaffected.
- If CrewAI is not installed, `enable()` returns `False` and no hooks are registered.
- Without `litellm`, cost tracking still works using cascadeflow's built-in pricing estimates.
