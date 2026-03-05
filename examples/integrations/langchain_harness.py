"""
LangChain + cascadeflow harness integration example.

Run:
    pip install "cascadeflow[langchain]"
    export OPENAI_API_KEY="your-key"
    python examples/integrations/langchain_harness.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise SystemExit(
            "langchain-openai is not installed. "
            'Install with: pip install "cascadeflow[langchain]" langchain-openai'
        ) from exc

    from cascadeflow import init, run
    from cascadeflow.integrations.langchain import get_harness_callback

    # 1) Initialize harness globally.
    init(mode="observe", budget=1.0, max_tool_calls=6)

    model = ChatOpenAI(model="gpt-4o-mini")

    # 2) Scoped run with harness-aware callback.
    with run(budget=0.5, max_tool_calls=4) as session:
        with get_harness_callback() as cb:
            response = await model.ainvoke(
                "Explain why inside-the-loop model routing helps agent budgets.",
                config={"callbacks": [cb]},
            )

        print("=== Result ===")
        print(response.content)
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
    asyncio.run(main())
