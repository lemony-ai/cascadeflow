"""
Cost Tracking Example - FIXED VERSION
======================================

Comprehensive cost tracking and budget management with cascadeflow.

This example demonstrates:
- Real-time cost tracking across queries
- Per-model and per-provider cost analysis
- Budget limits and alerts
- Cost history and trends
- Integration with CostCalculator and MetricsCollector

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."

Run:
    python examples/cost_tracking.py

What You'll See:
    - Cost tracking for multiple queries
    - Budget warnings when approaching limits
    - Detailed breakdowns by model and provider
    - Cost optimization insights

Documentation:
    📖 Cost Tracking Guide: docs/guides/cost_tracking.md
    📖 Telemetry Module: cascadeflow/telemetry/
    📚 Examples README: examples/README.md
"""

import asyncio
import os

from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.telemetry import CostTracker, MetricsCollector


async def main():
    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Check API Key
    # ═══════════════════════════════════════════════════════════════════════

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'")
        return

    print("💰 cascadeflow Cost Tracking\n")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Setup Cost Tracker with Budget
    # ═══════════════════════════════════════════════════════════════════════
    # CostTracker monitors costs across queries and enforces budgets
    # - budget_limit: Maximum allowed spend
    # - warn_threshold: Warn at 80% of budget (0.8)
    # - verbose: Enable detailed logging

    cost_tracker = CostTracker(
        budget_limit=1.00,  # $1.00 budget limit
        warn_threshold=0.8,  # Warn at 80% ($0.80)
        verbose=True,
    )

    print("✓ Cost tracker initialized")
    print(f"  Budget limit: ${cost_tracker.budget_limit:.2f}")
    print(f"  Warn threshold: {int(cost_tracker.warn_threshold * 100)}%\n")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Setup Agent with Cascade
    # ═══════════════════════════════════════════════════════════════════════
    # Create agent with 2-tier cascade:
    # - Tier 1 (gpt-4o-mini): Fast & cheap (~$0.15 per 1M tokens)
    # - Tier 2 (gpt-4o): Slower & expensive (~$6.25 per 1M tokens)

    agent = CascadeAgent(
        models=[
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),  # Cost per 1K tokens
            ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
        ]
    )

    print("✓ Agent ready with 2-tier cascade\n")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Setup Metrics Collector (Optional)
    # ═══════════════════════════════════════════════════════════════════════
    # MetricsCollector provides comprehensive statistics beyond just costs
    # Useful for analyzing cascade performance, model usage, etc.

    metrics = MetricsCollector()
    print("✓ Metrics collector initialized\n")

    # ═══════════════════════════════════════════════════════════════════════
    # EXAMPLE 1: Track Multiple Queries
    # ═══════════════════════════════════════════════════════════════════════
    # Run several queries and track costs automatically

    queries = [
        "What is Python?",
        "Explain quantum computing",
        "What are the health benefits of green tea?",
        "Describe the history of the Eiffel Tower",
        "Explain machine learning in detail",
    ]

    print("=" * 60)
    print("Running queries with cost tracking...\n")

    for i, query in enumerate(queries, 1):
        print(f"Query {i}/{len(queries)}: {query[:50]}...")

        # Execute query
        result = await agent.run(query, max_tokens=150)

        # ✅ FIX: Extract from metadata dict - handle missing attributes gracefully
        # The agent returns a custom result object that may not have all expected attributes
        total_cost = getattr(result, "total_cost", 0) or 0
        total_tokens = (
            result.metadata.get("total_tokens", 0) or getattr(result, "total_tokens", 0) or 0
        )
        cascaded = result.metadata.get("cascaded", False) or getattr(result, "cascaded", False)
        draft_accepted = result.metadata.get("draft_accepted", False) or getattr(
            result, "draft_accepted", False
        )

        draft_cost = (
            result.metadata.get("draft_cost", 0) or result.metadata.get("drafter_cost", 0) or 0
        )
        verifier_cost = result.metadata.get("verifier_cost", 0) or 0
        draft_tokens = (
            result.metadata.get("draft_tokens", 0) or result.metadata.get("tokens_drafted", 0) or 0
        )
        verifier_tokens = (
            result.metadata.get("verifier_tokens", 0)
            or result.metadata.get("tokens_verified", 0)
            or 0
        )

        # If no tokens at all, estimate from word count (rough approximation)
        if total_tokens == 0:
            content = getattr(result, "content", "")
            total_tokens = int(len(content.split()) * 1.3)  # Rough estimate: words * 1.3

        # If metadata doesn't have breakdown, fall back to total cost
        if draft_cost == 0 and verifier_cost == 0 and total_cost > 0:
            # No breakdown available, just track total
            # ✅ FIX: Extract actual model name from metadata if available
            actual_model = (
                result.metadata.get("draft_model")
                or result.metadata.get("verifier_model")
                or getattr(result, "model_used", "unknown")
            )
            cost_tracker.add_cost(
                model=actual_model,
                provider=agent.models[0].provider,
                tokens=total_tokens,
                cost=total_cost,
                query_id=f"query-{i}",
                metadata={
                    "query": query[:50],
                    "cascaded": cascaded,
                    "no_breakdown": True,
                    "draft_accepted": draft_accepted,
                },
            )
        else:
            # We have breakdown - track separately
            # Track draft model costs if used
            if draft_cost > 0:
                cost_tracker.add_cost(
                    model=result.metadata.get("draft_model") or agent.models[0].name,
                    provider=agent.models[0].provider,
                    tokens=draft_tokens if draft_tokens > 0 else int(total_tokens * 0.5),
                    cost=draft_cost,
                    query_id=f"query-{i}",
                    metadata={
                        "query": query[:50],
                        "cascaded": cascaded,
                        "role": "draft",
                        "draft_accepted": draft_accepted,
                    },
                )

            # Track verifier model costs if used
            if verifier_cost > 0:
                cost_tracker.add_cost(
                    model=result.metadata.get("verifier_model") or agent.models[-1].name,
                    provider=(
                        agent.models[-1].provider
                        if len(agent.models) > 1
                        else agent.models[0].provider
                    ),
                    tokens=verifier_tokens if verifier_tokens > 0 else int(total_tokens * 0.5),
                    cost=verifier_cost,
                    query_id=f"query-{i}",
                    metadata={
                        "query": query[:50],
                        "cascaded": cascaded,
                        "role": "verifier",
                        "draft_accepted": draft_accepted,
                    },
                )

        # Track in metrics collector (for additional analytics)
        cascaded = result.metadata.get("cascaded", False) or getattr(result, "cascaded", False)
        metrics.record(
            result,
            routing_strategy="cascade" if cascaded else "direct",
            complexity="complex" if cascaded else "simple",
        )

        # Show result
        total_cost = getattr(result, "total_cost", 0)
        model_used = getattr(result, "model_used", "unknown")
        cascaded = result.metadata.get("cascaded", False) or getattr(result, "cascaded", False)

        print(f"  💰 Cost: ${total_cost:.6f}")

        # ✅ FIX: Show actual model used, not combined name
        if cascaded:
            draft_accepted = result.metadata.get("draft_accepted", False) or getattr(
                result, "draft_accepted", False
            )
            if draft_accepted:
                # Draft was accepted - only draft model was actually used
                actual_model = result.metadata.get("draft_model") or agent.models[0].name
                print(f"  🎯 Model: {actual_model} (draft accepted)")
                print("  ✅ Saved cost by using cheap model!")
            else:
                # Draft was rejected - both models were used
                actual_model = result.metadata.get("verifier_model") or agent.models[-1].name
                print(f"  🎯 Model: {actual_model} (after cascade)")
                print("  🔄 Draft rejected, used verifier for quality")
        else:
            # Direct routing - only one model used
            print(f"  🎯 Model: {model_used}")
        print()

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5: Display Cost Tracker Summary
    # ═══════════════════════════════════════════════════════════════════════
    # Show comprehensive cost breakdown

    print("=" * 60)
    cost_tracker.print_summary()

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6: Display Metrics Summary
    # ═══════════════════════════════════════════════════════════════════════
    # Show additional analytics from MetricsCollector

    metrics_summary = metrics.get_summary()

    print("=" * 60)
    print("METRICS SUMMARY")
    print("=" * 60)
    print(f"Total Queries:     {metrics_summary['total_queries']}")
    print(
        f"Cascaded Queries:  {metrics_summary['cascade_used']}"
    )  # ✅ FIX: Use 'cascade_used' not 'cascaded_queries'
    print(
        f"Cascade Rate:      {metrics_summary['cascade_rate']:.1f}%"
    )  # ✅ FIX: Already a percentage, no need for :.1%
    print(f"Avg Latency:       {metrics_summary['avg_latency_ms']:.0f}ms")
    print(f"Total Cost:        ${metrics_summary['total_cost']:.6f}")  # ✅ ADD: Show total cost
    print("=" * 60 + "\n")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 7: Advanced Cost Analysis
    # ═══════════════════════════════════════════════════════════════════════
    # Demonstrate detailed cost analysis capabilities

    print("=" * 60)
    print("ADVANCED COST ANALYSIS")
    print("=" * 60)

    # Get recent entries
    recent = cost_tracker.get_recent_entries(n=3)
    print(f"\nMost Recent {len(recent)} Entries:")
    for entry in recent:
        print(
            f"  {entry.timestamp.strftime('%H:%M:%S')} | "
            f"{entry.model:15s} | "
            f"${entry.cost:.6f} | "
            f"{entry.tokens:,} tokens"
        )

    # Get entries by model
    # ✅ FIX: Check for both individual names and combined name
    mini_entries = [e for e in cost_tracker.entries if "gpt-4o-mini" in e.model]
    gpt4_entries = [e for e in cost_tracker.entries if e.model == "gpt-4o"]

    print("\nModel Usage:")
    print(f"  gpt-4o-mini: {len(mini_entries)} entries")
    print(f"  gpt-4o:      {len(gpt4_entries)} entries")

    # Calculate savings
    summary = cost_tracker.get_summary()
    if "budget_remaining" in summary:
        print("\nBudget Status:")
        print(f"  Remaining: ${summary['budget_remaining']:.6f}")
        print(f"  Used: {summary['budget_used_pct']:.1f}%")

    print("=" * 60 + "\n")

    # ═══════════════════════════════════════════════════════════════════════
    # KEY TAKEAWAYS
    # ═══════════════════════════════════════════════════════════════════════

    print("📚 Key takeaways:")
    print("\n  Cost Tracking Components:")
    print("  ├─ CostTracker: Monitors costs across queries")
    print("  ├─ CostCalculator: Calculates costs from results")
    print("  ├─ MetricsCollector: Aggregates all statistics")
    print("  └─ Budget alerts: Warns and prevents overspending")

    print("\n  Integration:")
    print("  ├─ CostCalculator computes costs per query")
    print("  ├─ CostTracker accumulates costs over time")
    print("  └─ MetricsCollector provides comprehensive analytics")

    print("\n  Cost Optimization:")
    print("  ├─ Track per-model costs to identify expensive patterns")
    print("  ├─ Monitor cascade rate to optimize quality/cost balance")
    print("  └─ Set budgets to prevent unexpected spending")

    print("\n  CascadeResult Structure:")
    print("  ├─ result.metadata dict contains ALL diagnostic info")
    print("  ├─ result.metadata['draft_cost'], result.metadata['verifier_cost']")
    print("  ├─ result.metadata['draft_tokens'], result.metadata['verifier_tokens']")
    print("  └─ result.metadata['draft_model'], result.metadata['verifier_model']")

    print("\n📚 Learn more: docs/guides/cost_tracking.md\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        print("💡 Tip: Make sure OPENAI_API_KEY is set correctly")
