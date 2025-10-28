"""
CascadeFlow v0.2.0 - Quickstart Example

This example demonstrates the simplest possible usage of CascadeFlow with Presets 2.0.
Perfect for getting started in less than 2 minutes!

Requirements:
- Set environment variables: OPENAI_API_KEY, GROQ_API_KEY (or others)
- Install: pip install cascadeflow

Usage:
    python examples/quickstart_v2.py
"""

import asyncio
from cascadeflow import get_balanced_agent


async def main():
    """
    Quickstart: One line to create a production-ready agent!
    """
    print("=== CascadeFlow v0.2.0 Quickstart ===\n")

    # One line to create an agent with production-ready defaults!
    agent = get_balanced_agent()
    print("✓ Agent created with Presets 2.0 (balanced profile)")
    print(f"  - Automatic provider detection")
    print(f"  - Optimized for cost/speed/quality balance")
    print(f"  - 80-90% cost savings vs GPT-4 alone\n")

    # Run a simple query
    print("Running query: 'What is 2+2?'\n")
    result = await agent.run("What is 2+2?")

    # Display results
    print("=== Results ===")
    print(f"Answer: {result.content}")
    print(f"Model used: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Quality score: {result.quality_score:.2f}")

    # Run another query to show cost savings
    print("\n" + "=" * 50)
    print("Running complex query...\n")

    result2 = await agent.run("Explain quantum computing in simple terms")

    print("=== Results ===")
    print(f"Answer: {result2.content[:200]}...")  # First 200 chars
    print(f"Model used: {result2.model_used}")
    print(f"Cost: ${result2.total_cost:.6f}")
    print(f"Quality score: {result2.quality_score:.2f}")

    # Summary
    print("\n" + "=" * 50)
    print("=== Summary ===")
    print(f"✓ Two queries completed successfully")
    print(f"✓ Total cost: ${result.total_cost + result2.total_cost:.6f}")
    print(f"✓ Average quality: {(result.quality_score + result2.quality_score) / 2:.2f}")
    print(f"\nThat's it! You're ready to use CascadeFlow in production.")
    print(f"\nNext steps:")
    print(f"  1. Try other presets: get_cost_optimized_agent(), get_speed_optimized_agent()")
    print(f"  2. Read the migration guide: docs/MIGRATION_GUIDE_V0.2.0.md")
    print(f"  3. See more examples: examples/")


if __name__ == "__main__":
    asyncio.run(main())
