"""Cost tracking and budget management example for cascadeflow.

Demonstrates Python-specific features that TypeScript doesn't have:
- Budget tracking with warnings
- Cost history analysis
- CSV export
- Context managers
- Automatic cost reporting

Run:
    OPENAI_API_KEY=sk-... python examples/langchain_cost_tracking.py
"""

import asyncio
import os

from langchain_openai import ChatOpenAI

from cascadeflow.integrations.langchain import BudgetTracker, CascadeFlow, CostHistory, track_costs


async def example_1_basic_cost_history():
    """Example 1: Basic cost history tracking."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Cost History Tracking")
    print("=" * 80)

    # Create cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",
    )

    # Track cost history
    history = CostHistory()

    queries = [
        "What is 2+2?",
        "Explain quantum computing in one sentence.",
        "What is the capital of France?",
        "List 3 programming languages.",
    ]

    print("\nProcessing queries...")
    for query in queries:
        await cascade.ainvoke(query)
        result = cascade.get_last_cascade_result()
        history.add_result(result, query)
        print(f"  ✓ {query[:50]}")

    # Print summary
    print("\nCost History Summary:")
    summary = history.get_summary()
    print(f"  Total Queries:     {summary['total_queries']}")
    print(f"  Total Cost:        ${summary['total_cost']:.6f}")
    print(f"  Average Cost:      ${summary['avg_cost']:.6f}")
    print(f"  Average Savings:   {summary['avg_savings']:.1f}%")
    print(f"  Acceptance Rate:   {summary['acceptance_rate']:.1f}%")

    # Export to CSV
    history.export_csv("/tmp/cascade_costs.csv")


async def example_2_budget_tracking():
    """Example 2: Budget tracking with warnings."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Budget Tracking with Warnings")
    print("=" * 80)

    # Create cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",
    )

    # Set a tight budget to demonstrate warnings
    budget = BudgetTracker(budget=0.001)  # $0.001 budget

    print(f"\nBudget: ${budget.budget:.6f}")
    print("Processing queries with budget tracking...\n")

    queries = [
        "What is 2+2?",
        "Explain machine learning.",
        "What is Python?",
    ]

    for query in queries:
        await cascade.ainvoke(query)
        result = cascade.get_last_cascade_result()

        # Add cost to budget tracker
        budget.add_cost(
            result["total_cost"],
            result["model_used"],
            {"query": query, "accepted": result["accepted"]},
        )

        print(f"Query: {query}")
        print(f"  Cost: ${result['total_cost']:.6f}")
        print(f"  Total Spent: ${budget.spent:.6f}")

        # Check for warnings
        warning = budget.get_warning()
        if warning:
            print(f"  {warning}")

        if budget.is_over_budget():
            print("\n⛔ Budget exceeded! Stopping.")
            break

        print()

    # Print final budget summary
    summary = budget.get_summary()
    print("\nBudget Summary:")
    print(f"  Budget:        ${summary['budget']:.6f}")
    print(f"  Spent:         ${summary['spent']:.6f}")
    print(f"  Remaining:     ${summary['remaining']:.6f}")
    print(f"  Percent Used:  {summary['percent_used']:.1f}%")
    print(f"  Over Budget:   {summary['over_budget']}")
    print(f"  Total Calls:   {summary['total_calls']}")


async def example_3_context_manager():
    """Example 3: Using context manager for automatic reporting."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Context Manager (Automatic Cost Reporting)")
    print("=" * 80)

    # Create cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",
    )

    print("\nUsing track_costs() context manager...")
    print("Budget: $0.01\n")

    # Use context manager - automatically prints report at end
    with track_costs(budget=0.01) as tracker:
        queries = [
            "What is 2+2?",
            "Explain the difference between lists and tuples in Python.",
            "What is the capital of Germany?",
        ]

        for query in queries:
            await cascade.ainvoke(query)
            result = cascade.get_last_cascade_result()
            tracker.add_result(result, query)
            print(f"✓ Processed: {query[:50]}")

    # Report is automatically printed by context manager!
    print("\n✅ Context manager automatically printed cost report above")


async def example_4_pandas_export():
    """Example 4: Export to pandas DataFrame (if pandas installed)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Pandas DataFrame Export")
    print("=" * 80)

    try:
        import pandas as pd
    except ImportError:
        print("\n⚠️  Pandas not installed. Skipping this example.")
        print("   Install with: pip install pandas")
        return

    # Create cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",
    )

    history = CostHistory()

    queries = [
        "What is 2+2?",
        "What is the capital of France?",
        "List 3 colors.",
    ]

    print("\nProcessing queries...")
    for query in queries:
        await cascade.ainvoke(query)
        result = cascade.get_last_cascade_result()
        history.add_result(result, query)

    # Export to DataFrame
    df = history.to_dataframe()

    print("\n✓ Exported to pandas DataFrame")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns)}")
    print("\nDataFrame Preview:")
    print(df[["query", "model_used", "total_cost", "accepted"]].to_string(index=False))

    # Can now use pandas for analysis
    print("\nPandas Analysis:")
    print(f"  Mean cost: ${df['total_cost'].mean():.6f}")
    print(f"  Max cost:  ${df['total_cost'].max():.6f}")
    print(f"  Min cost:  ${df['total_cost'].min():.6f}")


async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    print("\n" + "=" * 80)
    print("CASCADEFLOW PYTHON-SPECIFIC COST TRACKING FEATURES")
    print("=" * 80)
    print("\nFeatures that TypeScript doesn't have:")
    print("  ✓ Budget tracking with warnings")
    print("  ✓ Cost history analysis")
    print("  ✓ CSV export")
    print("  ✓ Pandas DataFrame export")
    print("  ✓ Context managers for automatic reporting")

    await example_1_basic_cost_history()
    await example_2_budget_tracking()
    await example_3_context_manager()
    await example_4_pandas_export()

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETE!")
    print("=" * 80)
    print("\nFiles created:")
    print("  - /tmp/cascade_costs.csv")
    print("\nThese Python-specific features provide superior DX for:")
    print("  - Data scientists (Pandas integration)")
    print("  - Budget-conscious developers (budget tracking)")
    print("  - Cost analysis (CSV export, history tracking)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
