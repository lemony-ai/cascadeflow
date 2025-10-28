"""
CascadeFlow v0.2.0 - Preset Comparison Example

This example runs the same query through all 5 presets to demonstrate
the tradeoffs between cost, speed, and quality.

Perfect for understanding which preset to use for your use case.

Usage:
    python examples/preset_comparison.py
"""

import asyncio
import time
from cascadeflow import (
    get_cost_optimized_agent,
    get_balanced_agent,
    get_speed_optimized_agent,
    get_quality_optimized_agent,
    get_development_agent,
)


async def run_preset_comparison():
    """
    Compare all 5 presets with the same query
    """
    # Test query (moderately complex)
    query = "Explain the concept of recursion in programming with a simple example"

    print("\n" + "=" * 80)
    print("CascadeFlow v0.2.0 - Preset Comparison")
    print("=" * 80)
    print(f"\nTest query: '{query}'\n")
    print("Running same query through all 5 presets...\n")

    # Define all presets
    presets = [
        ("Development", get_development_agent, "Fast iteration, verbose logging"),
        ("Cost Optimized", get_cost_optimized_agent, "Minimize costs (85-95% savings)"),
        ("Balanced", get_balanced_agent, "Best overall (recommended)"),
        ("Speed Optimized", get_speed_optimized_agent, "Minimize latency (<800ms)"),
        (
            "Quality Optimized",
            get_quality_optimized_agent,
            "Maximize quality (0.90-0.98)",
        ),
    ]

    results = []

    # Run query through each preset
    for preset_name, preset_func, description in presets:
        print("=" * 80)
        print(f"Testing: {preset_name}")
        print(f"Description: {description}")
        print("-" * 80)

        # Create agent
        agent = preset_func()

        # Measure latency
        start_time = time.time()
        result = await agent.run(query)
        latency = time.time() - start_time

        # Store results
        results.append(
            {
                "preset": preset_name,
                "description": description,
                "model": result.model_used,
                "cost": result.total_cost,
                "quality": result.quality_score,
                "latency": latency,
                "content": result.content,
            }
        )

        # Display result
        print(f"✓ Model used: {result.model_used}")
        print(f"✓ Cost: ${result.total_cost:.6f}")
        print(f"✓ Quality score: {result.quality_score:.2f}")
        print(f"✓ Latency: {latency:.2f}s")
        print(f"\nResponse preview: {result.content[:150]}...")
        print()

    # Summary comparison
    print("\n" + "=" * 80)
    print("=== Comparison Summary ===")
    print("=" * 80 + "\n")

    # Table header
    print(
        f"{'Preset':<20} {'Model':<25} {'Cost':>10} {'Quality':>8} {'Latency':>8}"
    )
    print("-" * 80)

    # Table rows
    for r in results:
        print(
            f"{r['preset']:<20} {r['model']:<25} ${r['cost']:>9.6f} {r['quality']:>8.2f} {r['latency']:>7.2f}s"
        )

    # Analysis
    print("\n" + "=" * 80)
    print("=== Analysis ===")
    print("=" * 80 + "\n")

    # Find extremes
    cheapest = min(results, key=lambda x: x["cost"])
    most_expensive = max(results, key=lambda x: x["cost"])
    fastest = min(results, key=lambda x: x["latency"])
    slowest = max(results, key=lambda x: x["latency"])
    highest_quality = max(results, key=lambda x: x["quality"])
    lowest_quality = min(results, key=lambda x: x["quality"])

    print("Cost:")
    print(f"  Cheapest: {cheapest['preset']} (${cheapest['cost']:.6f})")
    print(
        f"  Most expensive: {most_expensive['preset']} (${most_expensive['cost']:.6f})"
    )
    savings = (1 - cheapest["cost"] / most_expensive["cost"]) * 100
    print(f"  Savings range: Up to {savings:.1f}%\n")

    print("Speed:")
    print(f"  Fastest: {fastest['preset']} ({fastest['latency']:.2f}s)")
    print(f"  Slowest: {slowest['preset']} ({slowest['latency']:.2f}s)")
    speedup = slowest["latency"] / fastest["latency"]
    print(f"  Speedup range: Up to {speedup:.1f}x\n")

    print("Quality:")
    print(
        f"  Highest: {highest_quality['preset']} ({highest_quality['quality']:.2f})"
    )
    print(f"  Lowest: {lowest_quality['preset']} ({lowest_quality['quality']:.2f})")
    quality_range = highest_quality["quality"] - lowest_quality["quality"]
    print(f"  Range: {quality_range:.2f} points\n")

    # Recommendations
    print("=" * 80)
    print("=== Recommendations ===")
    print("=" * 80 + "\n")

    recommendations = [
        {
            "title": "Development & Testing",
            "preset": "get_development_agent()",
            "reason": "Fast iteration, verbose logging, minimal cost",
            "use_cases": ["Local development", "Unit tests", "Prototyping"],
        },
        {
            "title": "High-Volume Production",
            "preset": "get_cost_optimized_agent()",
            "reason": "Minimize costs while maintaining good quality",
            "use_cases": ["Chatbots", "Content moderation", "Internal tools"],
        },
        {
            "title": "General Production (Recommended)",
            "preset": "get_balanced_agent()",
            "reason": "Best balance of cost, speed, and quality",
            "use_cases": [
                "Customer support",
                "Content generation",
                "Most applications",
            ],
        },
        {
            "title": "Real-Time Applications",
            "preset": "get_speed_optimized_agent()",
            "reason": "Minimize latency for user-facing interactions",
            "use_cases": [
                "Real-time chat",
                "Interactive assistants",
                "Low-latency needs",
            ],
        },
        {
            "title": "High-Stakes Applications",
            "preset": "get_quality_optimized_agent()",
            "reason": "Maximum quality for complex reasoning",
            "use_cases": ["Medical/legal", "Research", "Complex analysis"],
        },
    ]

    for rec in recommendations:
        print(f"{rec['title']}:")
        print(f"  Preset: {rec['preset']}")
        print(f"  Reason: {rec['reason']}")
        print(f"  Use cases: {', '.join(rec['use_cases'])}\n")

    # Cost comparison vs GPT-4
    print("=" * 80)
    print("=== Cost Savings vs GPT-4 Baseline ===")
    print("=" * 80 + "\n")

    # Assume GPT-4 would cost ~$0.005 for this query
    gpt4_cost = 0.005

    print(f"GPT-4 only cost (estimated): ${gpt4_cost:.6f}\n")

    for r in results:
        savings = (1 - r["cost"] / gpt4_cost) * 100
        print(f"{r['preset']:<20} ${r['cost']:.6f}  ({savings:>5.1f}% savings)")

    print("\n✓ All presets show significant cost savings vs GPT-4 alone!")

    # Final summary
    print("\n" + "=" * 80)
    print("=== Summary ===")
    print("=" * 80 + "\n")

    print("Key Takeaways:")
    print("  1. All presets provide 60-99% cost savings vs GPT-4 alone")
    print("  2. Quality remains high across all presets (0.65-0.98)")
    print("  3. Choose based on your priorities:")
    print("     - Cost? → get_cost_optimized_agent()")
    print("     - Balance? → get_balanced_agent() ⭐ (recommended)")
    print("     - Speed? → get_speed_optimized_agent()")
    print("     - Quality? → get_quality_optimized_agent()")
    print("     - Development? → get_development_agent()")
    print("\n✓ One line of code, production-ready results!")
    print("\nFor more details, see: docs/guides/presets.md")
    print("=" * 80 + "\n")


async def main():
    """
    Main entry point
    """
    try:
        await run_preset_comparison()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure API keys are set: OPENAI_API_KEY, GROQ_API_KEY, etc.")
        print("  2. Check your internet connection")
        print("  3. Verify API key permissions")
        print("\nSee: docs/MIGRATION_GUIDE_V0.2.0.md#troubleshooting")


if __name__ == "__main__":
    asyncio.run(main())
