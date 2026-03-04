"""
Google ADK + cascadeflow harness integration example.

Run:
    pip install "cascadeflow[google-adk]"
    export GOOGLE_API_KEY="your-key"
    python examples/integrations/google_adk_harness.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    try:
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
    except ImportError as exc:
        raise SystemExit(
            "Google ADK is not installed. " 'Install with: pip install "cascadeflow[google-adk]"'
        ) from exc

    from cascadeflow import init, run
    from cascadeflow.integrations.google_adk import enable, GoogleADKHarnessConfig

    # 1. Initialize harness globally
    init(mode="observe", budget=1.0)

    # 2. Create the cascadeflow ADK plugin
    plugin = enable(
        config=GoogleADKHarnessConfig(
            fail_open=True,
            enable_budget_gate=True,
        )
    )

    # 3. Define an ADK agent
    agent = Agent(
        name="demo_agent",
        model="gemini-2.5-flash",
        instruction="You are a helpful assistant. Answer concisely.",
    )

    # 4. Create a Runner with the cascadeflow plugin
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="cascadeflow_demo",
        session_service=session_service,
        plugins=[plugin],  # cascadeflow hooks into all LLM calls here
    )

    # 5. Run within a harness scope
    with run(budget=0.5) as session:
        user_session = await session_service.create_session(
            app_name="cascadeflow_demo",
            user_id="demo-user",
        )

        from google.genai.types import Content, Part

        async for event in runner.run_async(
            user_id="demo-user",
            session_id=user_session.id,
            new_message=Content(parts=[Part(text="What is model routing?")]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(part.text, end="")
        print()

        print("\n=== Harness Metrics ===")
        print(f"Cost: ${session.cost:.6f}")
        print(f"Remaining budget: {session.budget_remaining}")
        print(f"Steps: {session.step_count}")
        print(f"Tool calls: {session.tool_calls}")
        print(f"Energy: {session.energy_used:.1f}")
        print(f"Latency: {session.latency_used_ms:.0f}ms")
        print("\n=== Decision Trace ===")
        for event in session.trace():
            print(event)


if __name__ == "__main__":
    asyncio.run(main())
