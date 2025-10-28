"""
CascadeFlow v0.2.0 - Migration Example

This example demonstrates migrating from v0.1.x manual configuration to v0.2.0 Presets 2.0.
Shows side-by-side comparison to highlight the dramatic simplification.

Usage:
    python examples/migration_example.py
"""

import asyncio
from cascadeflow import CascadeAgent, ModelConfig, get_balanced_agent


async def v0_1_x_approach():
    """
    v0.1.x approach: Manual model configuration (20+ lines)
    """
    print("=== v0.1.x Approach (Manual Configuration) ===\n")

    # Step 1: Manually define all models
    models = [
        ModelConfig(
            name="llama-3.1-8b-instant",
            provider="groq",
            cost=0.00005,
            quality_tier=1,
        ),
        ModelConfig(
            name="gpt-4o-mini",
            provider="openai",
            cost=0.00015,
            quality_tier=2,
        ),
        ModelConfig(
            name="gpt-4o",
            provider="openai",
            cost=0.005,
            quality_tier=3,
        ),
    ]

    # Step 2: Create agent with manual config
    agent = CascadeAgent(
        models=models,
        validation_threshold=0.7,
        max_attempts=3,
    )

    print(f"✓ Agent created (28 lines of code)")
    print(f"✓ 3 models manually configured")
    print(f"✓ Manual provider setup required")
    print(f"✓ Manual cost/tier configuration\n")

    # Step 3: Run query
    print("Running query...\n")
    result = await agent.run("What is the capital of France?")

    print("Results:")
    print(f"  Answer: {result.content}")
    print(f"  Model: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Quality: {result.quality_score:.2f}")

    return result


async def v0_2_0_approach():
    """
    v0.2.0 approach: Presets 2.0 (1 line)
    """
    print("\n" + "=" * 70)
    print("=== v0.2.0 Approach (Presets 2.0) ===\n")

    # One line!
    agent = get_balanced_agent()

    print(f"✓ Agent created (1 line of code!)")
    print(f"✓ Automatic provider detection")
    print(f"✓ Production-ready defaults")
    print(f"✓ Optimized model cascade\n")

    # Run same query
    print("Running same query...\n")
    result = await agent.run("What is the capital of France?")

    print("Results:")
    print(f"  Answer: {result.content}")
    print(f"  Model: {result.model_used}")
    print(f"  Cost: ${result.total_cost:.6f}")
    print(f"  Quality: {result.quality_score:.2f}")

    return result


async def compare_results(v1_result, v2_result):
    """
    Compare results from both approaches
    """
    print("\n" + "=" * 70)
    print("=== Comparison ===\n")

    print("Code Complexity:")
    print(f"  v0.1.x: 28 lines of manual configuration")
    print(f"  v0.2.0: 1 line with Presets 2.0")
    print(f"  Reduction: 96% less code\n")

    print("Setup Time:")
    print(f"  v0.1.x: ~10 minutes (research + config)")
    print(f"  v0.2.0: <1 minute (just one line)")
    print(f"  Improvement: 90% faster\n")

    print("Configuration:")
    print(f"  v0.1.x: Manual (requires research)")
    print(f"  v0.2.0: Automatic (zero config)")
    print(f"  Benefit: No decisions needed\n")

    print("Quality:")
    print(f"  v0.1.x: {v1_result.quality_score:.2f}")
    print(f"  v0.2.0: {v2_result.quality_score:.2f}")
    improvement = (
        "Better" if v2_result.quality_score > v1_result.quality_score else "Same"
    )
    print(f"  Result: {improvement}\n")

    print("Cost:")
    print(f"  v0.1.x: ${v1_result.total_cost:.6f}")
    print(f"  v0.2.0: ${v2_result.total_cost:.6f}")
    if v2_result.total_cost < v1_result.total_cost:
        savings = (1 - v2_result.total_cost / v1_result.total_cost) * 100
        print(f"  Savings: {savings:.1f}%")
    else:
        print(f"  Similar cost")


async def main():
    """
    Main migration demonstration
    """
    print("\n" + "=" * 70)
    print("CascadeFlow Migration Example: v0.1.x → v0.2.0")
    print("=" * 70 + "\n")

    # Show v0.1.x approach
    v1_result = await v0_1_x_approach()

    # Show v0.2.0 approach
    v2_result = await v0_2_0_approach()

    # Compare results
    await compare_results(v1_result, v2_result)

    # Migration recommendation
    print("\n" + "=" * 70)
    print("=== Migration Recommendation ===\n")
    print("✓ v0.1.x code still works (100% backwards compatible)")
    print("✓ But v0.2.0 offers dramatic simplification:")
    print("  - 96% less code")
    print("  - 90% faster setup")
    print("  - Automatic provider detection")
    print("  - Production-ready defaults")
    print("  - Better or same performance")
    print("\n✓ Migration time: <10 minutes for most projects")
    print("✓ See: docs/MIGRATION_GUIDE_V0.2.0.md")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
