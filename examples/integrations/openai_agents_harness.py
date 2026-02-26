"""
OpenAI Agents SDK + cascadeflow harness integration example.

Run:
    pip install "cascadeflow[openai,openai-agents]"
    python examples/integrations/openai_agents_harness.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    try:
        from agents import Agent, RunConfig, Runner
    except ImportError as exc:
        raise SystemExit(
            "OpenAI Agents SDK is not installed. "
            "Install with: pip install \"cascadeflow[openai,openai-agents]\""
        ) from exc

    from cascadeflow import init, run
    from cascadeflow.integrations.openai_agents import (
        CascadeFlowModelProvider,
        OpenAIAgentsIntegrationConfig,
    )

    init(mode="observe", budget=1.0, max_tool_calls=5)

    provider = CascadeFlowModelProvider(
        config=OpenAIAgentsIntegrationConfig(
            model_candidates=["gpt-4o", "gpt-4o-mini"],
            enable_tool_gating=True,
        )
    )

    agent = Agent(
        name="RouteAwareAgent",
        instructions="Respond clearly and include a short reasoning summary.",
        model="gpt-4o",
    )

    run_config = RunConfig(model_provider=provider)

    with run(budget=0.5, max_tool_calls=3) as session:
        result = await Runner.run(agent, "Summarize why model routing helps agent budgets.", run_config=run_config)

        print("=== Result ===")
        print(result.final_output)
        print("\n=== Harness Metrics ===")
        print(f"Cost: ${session.cost:.6f}")
        print(f"Remaining budget: {session.budget_remaining}")
        print(f"Steps: {session.step_count}")
        print(f"Tool calls: {session.tool_calls}")
        print("\n=== Decision Trace ===")
        for event in session.trace():
            print(event)


if __name__ == "__main__":
    asyncio.run(main())
