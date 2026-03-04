"""
CrewAI + cascadeflow harness integration example.

Run:
    pip install "cascadeflow[crewai,openai]"
    export OPENAI_API_KEY="your-key"
    python examples/integrations/crewai_harness.py
"""

from __future__ import annotations


def main() -> None:
    try:
        from crewai import Agent, Crew, Process, Task
    except ImportError as exc:
        raise SystemExit(
            "CrewAI is not installed. " 'Install with: pip install "cascadeflow[crewai,openai]"'
        ) from exc

    from cascadeflow import init, run
    from cascadeflow.integrations.crewai import CrewAIHarnessConfig, enable

    # 1) Initialize harness globally.
    init(mode="observe", budget=1.0, max_tool_calls=6)

    # 2) Explicitly enable CrewAI integration hooks (opt-in).
    enabled = enable(
        config=CrewAIHarnessConfig(
            fail_open=True,
            enable_budget_gate=True,
        )
    )
    if not enabled:
        raise SystemExit(
            "CrewAI hooks are unavailable in this environment. " "Ensure crewai>=1.5 is installed."
        )

    agent = Agent(
        role="Routing Analyst",
        goal="Explain model routing impact on cost and latency in plain language.",
        backstory="You are concise and practical.",
        allow_delegation=False,
        llm="openai/gpt-4o-mini",
        verbose=False,
    )

    task = Task(
        description="Explain why inside-the-loop routing helps agent workloads.",
        expected_output="One short paragraph and three bullet points.",
        agent=agent,
    )

    with run(budget=0.5, max_tool_calls=4) as session:
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()

        print("=== Result ===")
        print(result)
        print("\n=== Harness Metrics ===")
        print(f"Cost: ${session.cost:.6f}")
        print(f"Remaining budget: {session.budget_remaining}")
        print(f"Steps: {session.step_count}")
        print(f"Tool calls: {session.tool_calls}")
        print(f"Latency: {session.latency_used_ms:.0f}ms")
        print(f"Energy: {session.energy_used:.1f}")
        print("\n=== Decision Trace ===")
        for event in session.trace():
            print(event)


if __name__ == "__main__":
    main()
