"""
CascadeFlow - Preset Usage Example (NEW in v0.1.1)

The easiest way to get started with CascadeFlow - using presets!
This example demonstrates:
- Using pre-configured presets (no manual setup)
- Comparing different presets for your use case
- Understanding latency breakdown (provider vs cascade)
- Custom preset builder for advanced users

Requirements:
    - cascadeflow[all]
    - API keys for the presets you want to use

Setup:
    pip install cascadeflow[all]

    # For PRESET_BEST_OVERALL:
    export ANTHROPIC_API_KEY="your-key"
    export OPENAI_API_KEY="your-key"

    # For PRESET_ULTRA_FAST:
    export GROQ_API_KEY="your-key"

    python examples/preset_usage.py

What You'll Learn:
    1. How to use presets (2 lines of code!)
    2. Which preset to choose for your use case
    3. How latency breaks down (95% provider, 5% cascade)
    4. How to create custom presets

Expected Output:
    - Side-by-side comparison of presets
    - Clear latency breakdown showing provider dominance
    - Cost comparison
    - Performance insights

Documentation:
    - Preset Guide: docs/guides/presets.md
    - Performance Guide: docs/guides/performance.md
"""

import asyncio
import os

from cascadeflow import (
    PRESET_ANTHROPIC_ONLY,
    PRESET_BEST_OVERALL,
    PRESET_OPENAI_ONLY,
    PRESET_ULTRA_CHEAP,
    PRESET_ULTRA_FAST,
    CascadeAgent,
    create_preset,
)


async def main():
    """
    Demonstrate preset usage with CascadeFlow.
    """

    print("=" * 80)
    print("🌊 CASCADEFLOW - PRESET USAGE EXAMPLE (v0.1.1)")
    print("=" * 80)
    print()
    print("This example shows how to use pre-configured presets for instant setup!")
    print()
    print("💡 Key Benefit: Go from 30+ lines of config to 2 lines of code")
    print()

    # ========================================================================
    # PART 1: The Easiest Way - Use a Preset
    # ========================================================================

    print("=" * 80)
    print("PART 1: Using a Preset (The Easiest Way)")
    print("=" * 80)
    print()

    print("📋 Before (v0.1.0) - Manual Configuration:")
    print("""
    from cascadeflow import CascadeAgent, ModelConfig

    agent = CascadeAgent(models=[
        ModelConfig(
            name="claude-3-5-haiku-20241022",
            provider="anthropic",
            cost=0.0008,
            speed_ms=2000,
            quality_score=0.85,
            domains=["general"],
        ),
        ModelConfig(
            name="gpt-4o-mini",
            provider="openai",
            cost=0.00015,
            speed_ms=2500,
            quality_score=0.80,
            domains=["general"],
        ),
    ])
    """)

    print("📋 After (v0.1.1) - Using Preset:")
    print("""
    from cascadeflow import CascadeAgent, PRESET_BEST_OVERALL

    agent = CascadeAgent(models=PRESET_BEST_OVERALL)  # That's it!
    """)

    print("✅ Result: 90% less code, same functionality!\n")

    # ========================================================================
    # PART 2: Test Different Presets
    # ========================================================================

    print("=" * 80)
    print("PART 2: Comparing Presets")
    print("=" * 80)
    print()

    # Detect available API keys
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))

    print("🔑 Detected API Keys:")
    print(f"   {'✅' if has_anthropic else '❌'} Anthropic")
    print(f"   {'✅' if has_openai else '❌'} OpenAI")
    print(f"   {'✅' if has_groq else '❌'} Groq")
    print()

    # Determine which presets to test
    presets_to_test = []

    if has_anthropic and has_openai:
        presets_to_test.append(("PRESET_BEST_OVERALL", PRESET_BEST_OVERALL))
    if has_openai:
        presets_to_test.append(("PRESET_OPENAI_ONLY", PRESET_OPENAI_ONLY))
    if has_anthropic:
        presets_to_test.append(("PRESET_ANTHROPIC_ONLY", PRESET_ANTHROPIC_ONLY))
    if has_groq:
        presets_to_test.append(("PRESET_ULTRA_FAST", PRESET_ULTRA_FAST))
    if has_groq and has_openai:
        presets_to_test.append(("PRESET_ULTRA_CHEAP", PRESET_ULTRA_CHEAP))

    if not presets_to_test:
        print("❌ No API keys found! Please set at least one:")
        print("   export OPENAI_API_KEY='your-key'")
        print("   export ANTHROPIC_API_KEY='your-key'")
        print("   export GROQ_API_KEY='your-key'")
        return

    # Test query
    test_query = "Explain the difference between async and await in Python"

    print(f"📝 Test Query: {test_query}\n")

    results = []

    for preset_name, preset_config in presets_to_test:
        print(f"{'─' * 80}")
        print(f"Testing: {preset_name}")
        print(f"{'─' * 80}")

        try:
            # Create agent with preset
            agent = CascadeAgent(models=preset_config)

            # Run query
            result = await agent.run(test_query, max_tokens=150)

            # Extract metrics
            total_latency = getattr(result, "latency_ms", 0)
            draft_latency = getattr(result, "draft_latency_ms", 0)
            verifier_latency = getattr(result, "verifier_latency_ms", 0)
            provider_latency = draft_latency + verifier_latency
            cascade_latency = max(0, total_latency - provider_latency)

            # Calculate percentages
            if total_latency > 0:
                provider_pct = (provider_latency / total_latency * 100)
                cascade_pct = (cascade_latency / total_latency * 100)
            else:
                provider_pct = cascade_pct = 0

            print(f"✅ Result:")
            print(f"   Model: {result.model_used}")
            print(f"   Cost: ${result.total_cost:.6f}")
            print(f"   Latency Breakdown:")
            print(f"     Total: {total_latency:.0f}ms (100%)")
            print(f"     ├─ Provider API: {provider_latency:.0f}ms ({provider_pct:.1f}%)")
            print(f"     └─ CascadeFlow: {cascade_latency:.0f}ms ({cascade_pct:.1f}%)")
            print()

            results.append({
                "preset": preset_name,
                "model": result.model_used,
                "cost": result.total_cost,
                "total_latency": total_latency,
                "provider_latency": provider_latency,
                "cascade_latency": cascade_latency,
                "provider_pct": provider_pct,
            })

        except Exception as e:
            print(f"❌ Error: {e}\n")

    # ========================================================================
    # PART 3: Comparison Summary
    # ========================================================================

    if results:
        print("=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)
        print()

        # Find fastest
        fastest = min(results, key=lambda x: x["total_latency"])
        cheapest = min(results, key=lambda x: x["cost"])

        print("🏆 Winners:")
        print(f"   Fastest: {fastest['preset']} ({fastest['total_latency']:.0f}ms)")
        print(f"   Cheapest: {cheapest['preset']} (${cheapest['cost']:.6f})")
        print()

        print("📊 Key Insight:")
        avg_provider_pct = sum(r["provider_pct"] for r in results) / len(results)
        print(f"   Provider API calls account for {avg_provider_pct:.1f}% of latency")
        print(f"   CascadeFlow overhead is only {100-avg_provider_pct:.1f}%")
        print()
        print("   💡 To reduce latency: Choose faster providers (Groq is 5-10x faster)")
        print("      Don't worry about cascade overhead - it's minimal!")
        print()

    # ========================================================================
    # PART 4: Custom Preset Builder
    # ========================================================================

    print("=" * 80)
    print("PART 4: Custom Preset Builder (Advanced)")
    print("=" * 80)
    print()

    print("🔧 For advanced users who want control without manual config:")
    print()
    print("Example 1: Strict quality, fast performance")
    print("""
    from cascadeflow import create_preset

    models = create_preset(
        quality='strict',      # Higher quality threshold (0.8)
        performance='fast',    # Use Groq for speed
        include_premium=False  # No premium tier
    )
    """)

    print("Example 2: Cost-optimized with premium fallback")
    print("""
    models = create_preset(
        quality='cost-optimized',  # Accept more drafts (0.6)
        performance='balanced',     # Mix of providers
        include_premium=True        # Add gpt-4o tier
    )
    """)

    print()
    print("📚 Quality Modes:")
    print("   • cost-optimized: Threshold 0.6 (accept more drafts)")
    print("   • balanced: Threshold 0.7 (default)")
    print("   • strict: Threshold 0.8 (higher quality)")
    print()
    print("📚 Performance Modes:")
    print("   • fast: Uses Groq (ultra-fast)")
    print("   • balanced: Mix of providers")
    print("   • reliable: OpenAI/Anthropic")
    print()

    # ========================================================================
    # PART 5: Which Preset to Choose?
    # ========================================================================

    print("=" * 80)
    print("DECISION GUIDE: Which Preset Should You Use?")
    print("=" * 80)
    print()

    print("Choose PRESET_BEST_OVERALL if:")
    print("   ✅ You're starting out")
    print("   ✅ You want excellent quality")
    print("   ✅ 2-3s latency is acceptable")
    print("   Cost: ~$0.0008/query | Speed: Fast")
    print()

    print("Choose PRESET_ULTRA_FAST if:")
    print("   ✅ Latency is critical (<2s)")
    print("   ✅ You need real-time responses")
    print("   ✅ Good quality is sufficient")
    print("   Cost: ~$0.00005/query | Speed: Ultra-fast (5-10x faster!)")
    print()

    print("Choose PRESET_ULTRA_CHEAP if:")
    print("   ✅ You process millions of queries")
    print("   ✅ Cost is the main concern")
    print("   ✅ Speed still matters")
    print("   Cost: ~$0.00008/query | Speed: Very fast")
    print()

    print("Choose PRESET_OPENAI_ONLY if:")
    print("   ✅ You prefer single provider")
    print("   ✅ Billing simplicity matters")
    print("   Cost: ~$0.0005/query | Speed: Fast")
    print()

    print("=" * 80)
    print("🎯 NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Try different presets with your queries")
    print("2. Monitor latency breakdown (provider vs cascade)")
    print("3. Choose based on your priorities (speed, cost, quality)")
    print("4. For production: See docs/guides/production.md")
    print()
    print("📚 Resources:")
    print("   • Preset Guide: docs/guides/presets.md")
    print("   • Performance Guide: docs/guides/performance.md")
    print("   • All Examples: examples/")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
