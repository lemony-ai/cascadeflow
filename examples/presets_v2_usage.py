"""
Example: Using Presets 2.0 for One-Line Agent Initialization

Demonstrates the new preset functions that provide one-line setup
for common use cases with automatic provider detection.

All presets are OPTIONAL - you can still configure everything manually.
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def main():
    """Demonstrate Presets 2.0 usage."""
    print("=" * 80)
    print("Presets 2.0 - One-Line Agent Initialization")
    print("=" * 80)

    # Check which providers are available
    print("\nChecking available providers...")
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_together = bool(os.getenv("TOGETHER_API_KEY"))

    print(f"  OpenAI:    {'✓' if has_openai else '✗'}")
    print(f"  Anthropic: {'✓' if has_anthropic else '✗'}")
    print(f"  Groq:      {'✓' if has_groq else '✗'}")
    print(f"  Together:  {'✓' if has_together else '✗'}")

    if not any([has_openai, has_anthropic, has_groq, has_together]):
        print(
            "\n❌ No API keys found. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY"
        )
        return

    # Example 1: Cost-optimized preset (minimize cost)
    print("\n" + "=" * 80)
    print("Example 1: Cost-Optimized Agent")
    print("=" * 80)
    print("Use case: Minimize cost, accept slower responses")
    print("Expected savings: 85-95% vs GPT-4 only")

    from cascadeflow import get_cost_optimized_agent

    agent_cost = get_cost_optimized_agent(verbose=False)
    print(f"\n✓ Agent created with {len(agent_cost.models)} models:")
    for m in agent_cost.models:
        print(f"  - {m.name} (${m.cost:.6f}/1K tokens)")

    result = await agent_cost.run("What is 2+2?")
    print(f"\n✓ Query result:")
    print(f"  Model used: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Answer: {result.content}")

    # Example 2: Balanced preset (balance cost/speed/quality)
    print("\n" + "=" * 80)
    print("Example 2: Balanced Agent")
    print("=" * 80)
    print("Use case: Balance cost, speed, and quality")
    print("Expected savings: 70-85% vs GPT-4 only")

    from cascadeflow import get_balanced_agent

    agent_balanced = get_balanced_agent(verbose=False)
    print(f"\n✓ Agent created with {len(agent_balanced.models)} models:")
    for m in agent_balanced.models:
        print(f"  - {m.name} (${m.cost:.6f}/1K tokens)")

    result = await agent_balanced.run("Explain quantum computing in one sentence.")
    print(f"\n✓ Query result:")
    print(f"  Model used: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Answer: {result.content}")

    # Example 3: Speed-optimized preset (minimize latency)
    print("\n" + "=" * 80)
    print("Example 3: Speed-Optimized Agent")
    print("=" * 80)
    print("Use case: Minimize latency, higher cost acceptable")
    print("Expected latency: 300-800ms per query")

    from cascadeflow import get_speed_optimized_agent

    agent_speed = get_speed_optimized_agent(verbose=False)
    print(f"\n✓ Agent created with {len(agent_speed.models)} models:")
    for m in agent_speed.models:
        print(f"  - {m.name} (~{m.speed_ms}ms)")

    result = await agent_speed.run("What's the capital of France?")
    print(f"\n✓ Query result:")
    print(f"  Model used: {result.model_used}")
    print(f"  Latency: {result.latency_ms:.0f}ms")
    print(f"  Answer: {result.content}")

    # Example 4: auto_agent() helper
    print("\n" + "=" * 80)
    print("Example 4: auto_agent() Helper")
    print("=" * 80)
    print("Use case: Select preset by name (useful for config-driven apps)")

    from cascadeflow import auto_agent

    # Select preset by name
    agent_auto = auto_agent(preset="balanced", verbose=False)
    print(f"\n✓ Agent created using 'balanced' preset")
    print(f"  Models: {len(agent_auto.models)}")

    result = await agent_auto.run("What is Python?")
    print(f"\n✓ Query result:")
    print(f"  Model used: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Answer: {result.content[:100]}...")

    # Example 5: Development preset (verbose logging)
    print("\n" + "=" * 80)
    print("Example 5: Development Agent")
    print("=" * 80)
    print("Use case: Fast iteration, verbose logging, relaxed quality thresholds")

    from cascadeflow import get_development_agent

    agent_dev = get_development_agent(verbose=True)
    print(f"\n✓ Agent created with verbose=True")
    print(f"  Models: {len(agent_dev.models)}")

    print(f"\n✓ Running query with verbose output:")
    result = await agent_dev.run("Hello, world!")
    print(f"\n✓ Query result:")
    print(f"  Model used: {result.model_used}")
    print(f"  Answer: {result.content}")

    # Summary
    print("\n" + "=" * 80)
    print("Summary: Presets 2.0 Benefits")
    print("=" * 80)
    print("✓ One-line initialization - no manual configuration")
    print("✓ Automatic provider detection from environment variables")
    print("✓ Production-ready configurations for common use cases")
    print("✓ Completely optional - manual configuration still available")
    print("✓ Graceful fallback when providers not available")
    print("\nAvailable presets:")
    print("  - get_cost_optimized_agent(): Minimize cost (85-95% savings)")
    print("  - get_balanced_agent(): Balance cost/speed/quality (70-85% savings)")
    print("  - get_speed_optimized_agent(): Minimize latency (300-800ms)")
    print("  - get_quality_optimized_agent(): Maximize quality (0.90-0.98)")
    print("  - get_development_agent(): Fast iteration, verbose logging")
    print("  - auto_agent(preset): Helper to select preset by name")


if __name__ == "__main__":
    asyncio.run(main())
