# OpenAI Agents SDK Integration

Use cascadeflow as an explicit, opt-in `ModelProvider` integration for the OpenAI Agents SDK.

## Design Principles

- Integration-only: nothing is enabled by default
- Works with existing Agents SDK apps
- Harness behavior is controlled by `cascadeflow.init(...)` and `cascadeflow.run(...)`
- Fail-open integration path: harness integration errors should not break agent execution

## Install

```bash
pip install "cascadeflow[openai,openai-agents]"
```

## Quickstart

```python
import asyncio

from agents import Agent, RunConfig, Runner
from cascadeflow import init, run
from cascadeflow.integrations.openai_agents import (
    CascadeFlowModelProvider,
    OpenAIAgentsIntegrationConfig,
)


async def main() -> None:
    # Global harness defaults.
    init(mode="enforce", budget=1.0, max_tool_calls=6)

    provider = CascadeFlowModelProvider(
        config=OpenAIAgentsIntegrationConfig(
            model_candidates=["gpt-4o", "gpt-4o-mini"],
            enable_tool_gating=True,
        )
    )

    agent = Agent(
        name="SupportAgent",
        instructions="Answer support questions clearly and concisely.",
        model="gpt-4o",
    )

    run_config = RunConfig(model_provider=provider)

    # Scoped run accounting for a single user task.
    with run(budget=0.5, max_tool_calls=3) as session:
        result = await Runner.run(agent, "Reset my account password", run_config=run_config)
        print(result.final_output)
        print(session.trace())


if __name__ == "__main__":
    asyncio.run(main())
```

## What This Integration Adds

- Harness-aware model switching under budget pressure
- Tool gating when enforce-mode limits are reached
- Run metrics on `cascadeflow.run()` context:
  - `cost`, `budget_remaining`, `step_count`, `tool_calls`, `latency_used_ms`, `energy_used`
- Full action trace through `run.trace()`

## Notes

- This is a Python integration for OpenAI Agents SDK.
- The SDK remains optional and is only installed via the `openai-agents` extra.
- Existing non-Agents users are unaffected.
