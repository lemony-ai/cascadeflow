"""
PydanticAI + cascadeflow cascade Model integration example.

Demonstrates full speculative cascading: a cheap drafter model runs first,
its response is quality-gated, and only escalates to an expensive verifier
when the quality score is too low.

Run:
    pip install "cascadeflow[pydantic-ai]"
    export OPENAI_API_KEY="your-key"
    python examples/integrations/pydantic_ai_harness.py
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    try:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIModel
    except ImportError as exc:
        raise SystemExit(
            "PydanticAI is not installed. " 'Install with: pip install "cascadeflow[pydantic-ai]"'
        ) from exc

    from cascadeflow import init, run
    from cascadeflow.integrations.pydantic_ai import create_cascade_model

    # 1. Initialize harness globally
    init(mode="observe", budget=1.0)

    # 2. Create a cascade model (drafter + verifier)
    drafter = OpenAIModel("gpt-4o-mini")
    verifier = OpenAIModel("gpt-4o")

    cascade = create_cascade_model(
        drafter,
        verifier,
        quality_threshold=0.7,
        enable_pre_router=True,  # Hard queries skip drafter
        enable_budget_gate=True,  # Enforce harness budget
        domain_policies={
            "medical": {"direct_to_verifier": True},
            "legal": {"quality_threshold": 0.95},
        },
    )

    # 3. Create a PydanticAI agent with the cascade model
    agent = Agent(model=cascade)

    # 4. Run within a harness scope
    with run(budget=0.50) as session:
        result = await agent.run("Explain quantum computing in simple terms.")
        print(result.output)

        # Inspect cascade decision
        cascade_result = cascade.get_last_cascade_result()
        if cascade_result:
            print(f"\n=== Cascade Decision ===")
            print(f"Model used: {cascade_result['model_used']}")
            print(f"Drafter accepted: {cascade_result['accepted']}")
            print(f"Drafter quality: {cascade_result['drafter_quality']:.2f}")
            print(f"Drafter cost: ${cascade_result['drafter_cost']:.6f}")
            print(f"Verifier cost: ${cascade_result['verifier_cost']:.6f}")
            print(f"Total cost: ${cascade_result['total_cost']:.6f}")
            print(f"Savings: {cascade_result['savings_percentage']:.1f}%")

        print(f"\n=== Harness Metrics ===")
        print(f"Cost: ${session.cost:.6f}")
        print(f"Remaining budget: {session.budget_remaining}")
        print(f"Steps: {session.step_count}")
        print(f"Energy: {session.energy_used:.1f}")
        print(f"Latency: {session.latency_used_ms:.0f}ms")
        print(f"\n=== Decision Trace ===")
        for event in session.trace():
            print(event)


if __name__ == "__main__":
    asyncio.run(main())
