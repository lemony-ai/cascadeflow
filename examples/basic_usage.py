"""
cascadeflow - Basic Usage Example

The simplest way to get started with cascadeflow. This example demonstrates:
- Setting up a two-tier cascade (cheap → expensive)
- Processing queries with automatic quality-based routing
- Cost tracking and savings calculation
- Different complexity levels (simple → complex queries)

Requirements:
    - cascadeflow[all]
    - OpenAI API key

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="your-key-here"
    python examples/basic_usage.py

What You'll Learn:
    1. How to configure a basic cascade
    2. How cascadeflow automatically routes queries
    3. How to track costs and savings
    4. How different query complexities are handled

Expected Output:
    - Simple queries: GPT-4o-mini draft accepted, GPT-4o skipped
    - Complex queries: Direct to GPT-4o OR draft rejected and escalated
    - Token-based cost comparison showing realistic 40-60% savings

Note on Costs:
    Costs are calculated using actual token-based pricing from OpenAI:
    - GPT-4o-mini: ~$0.000375 per 1K tokens (blended input/output)
    - GPT-4o: ~$0.0025 per 1K tokens (blended input/output)

    Savings depend on your query mix and response lengths.

Note on Latency:
    95% of latency comes from provider API calls, NOT from cascadeflow!
    - Provider API: 95% (waiting for OpenAI/Anthropic/etc to respond)
    - cascadeflow overhead: 5% (routing, quality checks, etc.)

    To reduce latency:
    1. Choose faster providers (Groq is 5-10x faster than OpenAI)
    2. Use streaming for perceived speed improvement
    3. Don't worry about cascade overhead (it's minimal)

Documentation:
    For complete setup instructions and detailed explanations, see:
    docs/guides/quickstart.md
"""

import asyncio

from cascadeflow import CascadeAgent, ModelConfig


async def main():
    """
    Basic cascadeflow usage - the simplest possible example.
    """

    print("=" * 80)
    print("🌊 CASCADEFLOW - BASIC USAGE EXAMPLE")
    print("=" * 80)
    print()
    print("This example shows how cascadeflow automatically routes queries")
    print("between a cheap model (GPT-4o-mini) and expensive model (GPT-4o).")
    print()
    print("💡 Key Concept: cascadeflow uses TOKEN-BASED pricing, not flat rates.")
    print("   This means costs depend on how long your queries and responses are.")
    print()

    # ========================================================================
    # STEP 1: Configure Your Cascade
    # ========================================================================

    print("📋 Step 1: Configuring cascade with two models...")
    print()

    agent = CascadeAgent(
        models=[
            # Cheap model - tries first
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.000375,  # $0.375 per 1M tokens (blended estimate)
                quality_threshold=0.7,  # Accept if confidence >= 70%
            ),
            # Expensive model - only if needed
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.00625,  # $6.25 per 1M tokens (blended estimate)
                quality_threshold=0.95,  # Very high quality
            ),
        ]
    )

    print("   ✅ Tier 1: gpt-4o-mini (~$0.375/1M tokens) - Tries first")
    print("   ✅ Tier 2: gpt-4o (~$6.25/1M tokens) - Escalates if needed")
    print()

    # ========================================================================
    # STEP 2: Test with Different Query Types
    # ========================================================================

    print("📝 Step 2: Testing with various query types...\n")

    # Test queries ranging from simple to complex
    test_queries = [
        # SIMPLE queries - should stay on GPT-4o-mini
        {
            "query": "What color is the sky?",
            "expected": "gpt-4o-mini",
            "reason": "Simple factual question - cheap model handles easily",
        },
        {
            "query": "What's the capital of France?",
            "expected": "gpt-4o-mini",
            "reason": "Simple factual - cheap model knows this",
        },
        {
            "query": "Translate 'hello' to Spanish",
            "expected": "gpt-4o-mini",
            "reason": "Simple translation - cheap model sufficient",
        },
        # MODERATE queries - might escalate
        {
            "query": "Explain the difference between lists and tuples in Python",
            "expected": "gpt-4o-mini",
            "reason": "Moderate complexity - cheap model likely handles it",
        },
        {
            "query": "Write a function to reverse a string in Python",
            "expected": "gpt-4o-mini",
            "reason": "Standard coding task - cheap model can do it",
        },
        # COMPLEX queries - likely escalate to GPT-4o
        {
            "query": "Explain quantum entanglement and its implications for quantum computing in detail",
            "expected": "gpt-4o",
            "reason": "Complex scientific topic - needs better model",
        },
        {
            "query": "Design a microservices architecture for a large-scale e-commerce platform with high availability",
            "expected": "gpt-4o",
            "reason": "Complex architecture design - benefits from GPT-4o",
        },
        {
            "query": "Analyze the philosophical implications of consciousness and free will in the context of determinism",
            "expected": "gpt-4o",
            "reason": "Deep philosophical analysis - needs sophisticated reasoning",
        },
    ]

    # Track statistics
    stats = {
        "gpt-4o-mini": {"count": 0, "cost": 0.0},
        "gpt-4o": {"count": 0, "cost": 0.0},
        "total_cost": 0.0,
        "draft_accepted": 0,
        "draft_rejected": 0,
        "direct_routing": 0,
    }

    # Track token usage for baseline calculation
    all_gpt4_tokens = 0

    # Process each query
    for i, test in enumerate(test_queries, 1):
        print(f"{'─' * 80}")
        print(f"Query {i}/{len(test_queries)}")
        print(f"{'─' * 80}")
        print(f"❓ Question: {test['query']}")
        print(f"🎯 Expected: {test['expected']}")
        print(f"💡 Why: {test['reason']}")
        print()

        # Run the query through cascade
        result = await agent.run(test["query"], max_tokens=150)

        # Determine which model was used
        model_used = "gpt-4o-mini" if "4o-mini" in result.model_used.lower() else "gpt-4o"

        # Update statistics
        stats[model_used]["count"] += 1
        stats[model_used]["cost"] += result.total_cost
        stats["total_cost"] += result.total_cost

        # Track cascade status
        if hasattr(result, "cascaded") and result.cascaded:
            if hasattr(result, "draft_accepted") and result.draft_accepted:
                stats["draft_accepted"] += 1
            else:
                stats["draft_rejected"] += 1
        else:
            stats["direct_routing"] += 1

        # Estimate tokens for baseline (approximate)
        query_tokens = len(test["query"].split()) * 1.3
        if hasattr(result, "content"):
            response_tokens = len(result.content.split()) * 1.3
        else:
            response_tokens = 100  # Default estimate
        all_gpt4_tokens += query_tokens + response_tokens

        # Show result
        tier = "Tier 1 (Cheap)" if model_used == "gpt-4o-mini" else "Tier 2 (Expensive)"
        icon = "💚" if model_used == "gpt-4o-mini" else "💛"

        print("✅ Result:")

        # Show actual model(s) used with clear status
        if hasattr(result, "draft_accepted") and result.draft_accepted:
            # Only draft was used
            print(f"   {icon} Model Used: gpt-4o-mini only ({tier})")
        elif (
            hasattr(result, "cascaded")
            and result.cascaded
            and not getattr(result, "draft_accepted", True)
        ):
            # Both models were used
            print("   💚💛 Models Used: gpt-4o-mini + gpt-4o (Both Tiers)")
        else:
            # Direct routing
            print(f"   {icon} Model Used: {result.model_used} ({tier})")

        # Safely get cost
        cost = getattr(result, "total_cost", 0.0)
        print(f"   💰 Cost: ${cost:.6f}")

        # Safely get latency with breakdown
        total_latency = getattr(result, "latency_ms", 0.0)
        draft_latency = getattr(result, "draft_latency_ms", 0.0)
        verifier_latency = getattr(result, "verifier_latency_ms", 0.0)

        # Calculate provider vs cascade latency
        provider_latency = draft_latency + verifier_latency
        cascade_latency = max(0, total_latency - provider_latency)

        if provider_latency > 0:
            provider_pct = (provider_latency / total_latency * 100) if total_latency > 0 else 0
            cascade_pct = (cascade_latency / total_latency * 100) if total_latency > 0 else 0
            print("   ⚡ Latency Breakdown:")
            print(f"      Total: {total_latency:.0f}ms")
            print(f"      ├─ Provider API: {provider_latency:.0f}ms ({provider_pct:.1f}%)")
            print(f"      └─ cascadeflow: {cascade_latency:.0f}ms ({cascade_pct:.1f}%)")
        else:
            print(f"   ⚡ Latency: {total_latency:.0f}ms")

        # Safely get complexity
        complexity = getattr(result, "complexity", "unknown")
        print(f"   📊 Complexity: {complexity}")

        # Show cascade status more clearly
        if hasattr(result, "cascaded") and result.cascaded:
            if hasattr(result, "draft_accepted") and result.draft_accepted:
                print("   ✅ Draft Accepted: GPT-4o-mini response passed quality check")
                print("   💡 Verifier Skipped: GPT-4o was not called (cost saved!)")
            else:
                print("   ❌ Draft Rejected: Quality check failed, escalated to GPT-4o")
                print("   💸 Both Models Used: Paid for GPT-4o-mini + GPT-4o")
        else:
            print("   🎯 Direct Route: Query sent directly to GPT-4o (no cascade)")

        # Show first part of response
        response_preview = result.content[:100].replace("\n", " ")
        print(f"   📝 Response: {response_preview}...")
        print()

    # ========================================================================
    # STEP 3: Show Cost Analysis
    # ========================================================================

    print("=" * 80)
    print("💰 COST ANALYSIS")
    print("=" * 80)
    print()

    # Calculate statistics
    total_queries = len(test_queries)
    gpt4mini_count = stats["gpt-4o-mini"]["count"]
    gpt4o_count = stats["gpt-4o"]["count"]

    gpt4mini_pct = (gpt4mini_count / total_queries) * 100
    gpt4o_pct = (gpt4o_count / total_queries) * 100

    print("📊 Query Distribution:")
    print(f"   GPT-4o-mini: {gpt4mini_count}/{total_queries} ({gpt4mini_pct:.0f}%)")
    print(f"   GPT-4o:      {gpt4o_count}/{total_queries} ({gpt4o_pct:.0f}%)")
    print()

    print("🔄 Cascade Behavior:")
    print(f"   Draft Accepted:  {stats['draft_accepted']} (verifier skipped)")
    print(f"   Draft Rejected:  {stats['draft_rejected']} (both models used)")
    print(f"   Direct Routing:  {stats['direct_routing']} (no cascade)")
    print()

    print("💵 Cost Breakdown:")
    print(f"   GPT-4o-mini: ${stats['gpt-4o-mini']['cost']:.6f}")
    print(f"   GPT-4o:      ${stats['gpt-4o']['cost']:.6f}")
    print(f"   Total Cost:  ${stats['total_cost']:.6f}")
    print()

    # Calculate savings vs all-GPT-4o (token-based estimate)
    # GPT-4o pricing: ~$0.00625 per 1K tokens (blended)
    all_gpt4o_cost = (all_gpt4_tokens / 1000) * 0.00625
    savings = all_gpt4o_cost - stats["total_cost"]
    savings_pct = (savings / all_gpt4o_cost * 100) if all_gpt4o_cost > 0 else 0.0

    print("💎 Savings Compared to All-GPT-4o (Token-Based):")
    print(f"   All-GPT-4o Estimate: ${all_gpt4o_cost:.6f}")
    print(f"   cascadeflow Cost:   ${stats['total_cost']:.6f}")
    print(f"   💰 SAVINGS:         ${savings:.6f} ({savings_pct:.1f}%)")
    print()
    print(f"   ℹ️  Note: Savings based on actual token usage (~{int(all_gpt4_tokens)} tokens)")
    print("       Your savings will vary based on query complexity and response length.")
    print()

    # Extrapolate to realistic scale
    print("📈 Extrapolated to 10,000 Queries/Month:")
    if all_gpt4_tokens > 0:
        scale_factor = 10_000 / total_queries
        monthly_cascade = stats["total_cost"] * scale_factor
        monthly_gpt4o = all_gpt4o_cost * scale_factor
        monthly_savings = monthly_gpt4o - monthly_cascade

        print(f"   All-GPT-4o:     ${monthly_gpt4o:,.2f}/month")
        print(f"   cascadeflow:    ${monthly_cascade:,.2f}/month")
        print(f"   💵 SAVE:        ${monthly_savings:,.2f}/month")
        print()

    # ========================================================================
    # STEP 4: Key Takeaways
    # ========================================================================

    print("=" * 80)
    print("🎯 KEY TAKEAWAYS")
    print("=" * 80)
    print()
    print("✅ What You Learned:")
    print("   1. cascadeflow automatically routes queries by complexity")
    print("   2. Simple queries use cheap models (GPT-4o-mini)")
    print("   3. Complex queries escalate to expensive models (GPT-4o)")
    print("   4. When draft is accepted, verifier is SKIPPED (saves cost!)")
    print("   5. Token-based pricing means actual costs depend on query/response length")
    print(f"   6. You achieved {savings_pct:.1f}% savings on this query mix")
    print()

    print("🚀 Next Steps:")
    print("   • Try with your own queries")
    print("   • Adjust quality_threshold to tune cascade behavior")
    print("   • Add more models (Ollama for local, Groq for free)")
    print("   • Monitor your own query patterns and optimize")
    print("   • Deploy to production")
    print()

    print("📚 Resources:")
    print("   • Full Guide: docs/guides/quickstart.md")
    print("   • API Reference: docs/api/")
    print("   • GitHub: https://github.com/lemony-ai/cascadeflow")
    print()

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
