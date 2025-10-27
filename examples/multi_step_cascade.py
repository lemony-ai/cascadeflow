"""
Phase 4: Multi-Step Cascade Pipelines Demo

This example demonstrates domain-specific cascade pipelines that execute
multiple steps with validation at each stage.

Features Demonstrated:
1. CODE domain pipeline (Deepseek → GPT-4 fallback)
2. MEDICAL domain pipeline (GPT-4o-mini → GPT-4 fallback)
3. GENERAL domain pipeline (Groq Llama → GPT-4o fallback)
4. DATA domain pipeline (GPT-4o-mini → GPT-4o fallback)
5. Step-by-step validation
6. Automatic fallback to more capable models
7. Cost tracking per step

Benefits:
- 95% cost reduction for code queries (Deepseek vs GPT-4)
- 98% cost reduction for general queries (Groq vs GPT-4)
- Automatic quality validation at each step
- Intelligent fallback only when needed
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def demo_code_cascade():
    """Demo 1: CODE domain cascade pipeline."""
    print("=" * 80)
    print("DEMO 1: CODE DOMAIN CASCADE PIPELINE")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import get_code_strategy
    from cascadeflow.routing.domain import Domain

    # Get CODE strategy
    strategy = get_code_strategy()

    print("Strategy Details:")
    print(f"Domain: {strategy.domain.value}")
    print(f"Description: {strategy.description}")
    print(f"Steps: {len(strategy.steps)}")
    print()

    for i, step in enumerate(strategy.steps, 1):
        print(f"  Step {i}: {step.name}")
        print(f"    Model: {step.model} ({step.provider})")
        print(f"    Validation: {step.validation}")
        print(f"    Quality Threshold: {step.quality_threshold}")
        print(f"    Fallback Only: {step.fallback_only}")
        print()

    # Initialize executor
    executor = MultiStepCascadeExecutor(strategies=[strategy])

    # Execute CODE query
    query = "Write a Python function to implement quicksort algorithm"
    print(f"Query: {query}")
    print()

    result = await executor.execute(query=query, domain=Domain.CODE)

    print("Execution Results:")
    print("-" * 40)
    print(f"Success: {result.success}")
    print(f"Total Cost: ${result.total_cost:.6f}")
    print(f"Total Latency: {result.total_latency_ms:.0f}ms")
    print(f"Total Tokens: {result.total_tokens}")
    print(f"Quality Score: {result.quality_score:.2%}")
    print(f"Fallback Used: {result.fallback_used}")
    print()

    print("Steps Executed:")
    for step_result in result.steps_executed:
        print(f"  {step_result.step_name}:")
        print(f"    Status: {step_result.status.value}")
        print(f"    Quality: {step_result.quality_score:.2%}")
        print(f"    Cost: ${step_result.cost:.6f}")
        print(f"    Latency: {step_result.latency_ms:.0f}ms")
        if step_result.validation_details:
            print(f"    Validation: {step_result.validation_details}")
        print()

    if result.final_response:
        print("Final Response:")
        print("-" * 40)
        print(result.final_response[:500] + "..." if len(result.final_response) > 500 else result.final_response)
        print()

    print("=" * 80)
    print()


async def demo_medical_cascade():
    """Demo 2: MEDICAL domain cascade pipeline."""
    print("=" * 80)
    print("DEMO 2: MEDICAL DOMAIN CASCADE PIPELINE")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import get_medical_strategy
    from cascadeflow.routing.domain import Domain

    # Get MEDICAL strategy
    strategy = get_medical_strategy()

    print("Strategy Details:")
    print(f"Domain: {strategy.domain.value}")
    print(f"Description: {strategy.description}")
    print()

    # Initialize executor
    executor = MultiStepCascadeExecutor(strategies=[strategy])

    # Execute MEDICAL query
    query = "What are the common symptoms of type 2 diabetes?"
    print(f"Query: {query}")
    print()

    result = await executor.execute(query=query, domain=Domain.MEDICAL)

    print("Execution Results:")
    print("-" * 40)
    print(f"Success: {result.success}")
    print(f"Total Cost: ${result.total_cost:.6f}")
    print(f"Quality Score: {result.quality_score:.2%}")
    print(f"Fallback Used: {result.fallback_used}")
    print()

    print("Cost Breakdown:")
    for step_name, cost in result.get_cost_breakdown().items():
        print(f"  {step_name}: ${cost:.6f}")
    print()

    if result.final_response:
        print("Final Response (truncated):")
        print("-" * 40)
        print(result.final_response[:300] + "...")
        print()

    print("=" * 80)
    print()


async def demo_general_cascade():
    """Demo 3: GENERAL domain cascade pipeline."""
    print("=" * 80)
    print("DEMO 3: GENERAL DOMAIN CASCADE PIPELINE")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import get_general_strategy
    from cascadeflow.routing.domain import Domain

    # Get GENERAL strategy
    strategy = get_general_strategy()

    print("Strategy Details:")
    print(f"Domain: {strategy.domain.value}")
    print(f"Description: {strategy.description}")
    print()

    # Initialize executor
    executor = MultiStepCascadeExecutor(strategies=[strategy])

    # Execute GENERAL query
    query = "What are the benefits of renewable energy?"
    print(f"Query: {query}")
    print()

    result = await executor.execute(query=query, domain=Domain.GENERAL)

    print("Execution Results:")
    print("-" * 40)
    print(f"Success: {result.success}")
    print(f"Total Cost: ${result.total_cost:.6f}")
    print(f"Steps Executed: {len(result.steps_executed)}")
    print(f"Successful Steps: {len(result.get_successful_steps())}")
    print()

    print("=" * 80)
    print()


async def demo_data_cascade():
    """Demo 4: DATA domain cascade pipeline."""
    print("=" * 80)
    print("DEMO 4: DATA DOMAIN CASCADE PIPELINE")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import get_data_strategy
    from cascadeflow.routing.domain import Domain

    # Get DATA strategy
    strategy = get_data_strategy()

    print("Strategy Details:")
    print(f"Domain: {strategy.domain.value}")
    print(f"Description: {strategy.description}")
    print()

    # Initialize executor
    executor = MultiStepCascadeExecutor(strategies=[strategy])

    # Execute DATA query
    query = "Write a SQL query to find the top 10 customers by total purchase amount"
    print(f"Query: {query}")
    print()

    result = await executor.execute(query=query, domain=Domain.DATA)

    print("Execution Results:")
    print("-" * 40)
    print(f"Success: {result.success}")
    print(f"Total Cost: ${result.total_cost:.6f}")
    print(f"Quality Score: {result.quality_score:.2%}")
    print()

    print("=" * 80)
    print()


async def demo_multi_domain_executor():
    """Demo 5: Multi-domain executor with automatic strategy selection."""
    print("=" * 80)
    print("DEMO 5: MULTI-DOMAIN EXECUTOR")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import (
        get_code_strategy,
        get_medical_strategy,
        get_general_strategy,
        get_data_strategy,
    )
    from cascadeflow.routing.domain import Domain

    # Initialize executor with multiple strategies
    executor = MultiStepCascadeExecutor(
        strategies=[
            get_code_strategy(),
            get_medical_strategy(),
            get_general_strategy(),
            get_data_strategy(),
        ]
    )

    print(f"Loaded strategies for {len(executor.strategies)} domains")
    print()

    # Execute queries for different domains
    test_queries = [
        (Domain.CODE, "Implement a binary search tree in Python"),
        (Domain.DATA, "Create a pandas DataFrame from a CSV file"),
        (Domain.MEDICAL, "What are the side effects of aspirin?"),
        (Domain.GENERAL, "Explain the water cycle"),
    ]

    total_cost = 0.0

    for domain, query in test_queries:
        print(f"Domain: {domain.value.upper()}")
        print(f"Query: {query}")

        result = await executor.execute(query=query, domain=domain)

        print(f"  Success: {result.success}")
        print(f"  Cost: ${result.total_cost:.6f}")
        print(f"  Steps: {len(result.steps_executed)}")
        print(f"  Fallback: {result.fallback_used}")

        total_cost += result.total_cost
        print()

    print(f"Total Cost (all queries): ${total_cost:.6f}")
    print()

    print("=" * 80)
    print()


async def demo_cost_comparison():
    """Demo 6: Cost comparison with and without cascading."""
    print("=" * 80)
    print("DEMO 6: COST COMPARISON")
    print("=" * 80)
    print()

    print("Scenario: 100 queries per day")
    print()

    # Cost estimates per query
    scenarios = {
        "CODE": {
            "without_cascade": 0.030,  # Direct GPT-4
            "with_cascade": 0.0014,  # Deepseek-Coder
            "cascade_success_rate": 0.95,  # 95% pass with Deepseek
        },
        "GENERAL": {
            "without_cascade": 0.030,  # Direct GPT-4
            "with_cascade": 0.0007,  # Groq Llama 70B
            "cascade_success_rate": 0.90,  # 90% pass with Groq
        },
        "MEDICAL": {
            "without_cascade": 0.030,  # Direct GPT-4
            "with_cascade": 0.00015,  # GPT-4o-mini
            "cascade_success_rate": 0.80,  # 80% pass with GPT-4o-mini
        },
    }

    queries_per_day = 100

    print(f"{'Domain':<12} {'Without':<15} {'With Cascade':<15} {'Savings':<15} {'Savings %'}")
    print("-" * 70)

    for domain, costs in scenarios.items():
        without = costs["without_cascade"] * queries_per_day
        # Average cost with cascade (draft pass rate * draft cost + fallback rate * fallback cost)
        with_cascade = (
            costs["cascade_success_rate"] * costs["with_cascade"]
            + (1 - costs["cascade_success_rate"]) * costs["without_cascade"]
        ) * queries_per_day

        savings = without - with_cascade
        savings_pct = (savings / without) * 100

        print(f"{domain:<12} ${without:<14.2f} ${with_cascade:<14.2f} ${savings:<14.2f} {savings_pct:.0f}%")

    print()
    print("=" * 80)
    print()


async def demo_fallback_behavior():
    """Demo 7: Fallback behavior when draft fails."""
    print("=" * 80)
    print("DEMO 7: FALLBACK BEHAVIOR")
    print("=" * 80)
    print()

    from cascadeflow.routing.cascade_executor import MultiStepCascadeExecutor
    from cascadeflow.routing.cascade_pipeline import CascadeStep, DomainCascadeStrategy
    from cascadeflow.routing.domain import Domain

    # Create a strategy with intentionally high quality threshold (to trigger fallback)
    high_threshold_strategy = DomainCascadeStrategy(
        domain=Domain.CODE,
        description="High threshold strategy to demonstrate fallback",
        steps=[
            CascadeStep(
                name="draft",
                model="gpt-4o-mini",
                provider="openai",
                validation="quality_check",
                quality_threshold=0.95,  # Very high threshold (likely to fail)
                fallback_only=False,
            ),
            CascadeStep(
                name="fallback",
                model="gpt-4",
                provider="openai",
                validation="full_quality",
                quality_threshold=0.85,
                fallback_only=True,  # Only execute if draft fails
            ),
        ],
    )

    executor = MultiStepCascadeExecutor(strategies=[high_threshold_strategy])

    query = "Write a simple hello world function"
    print(f"Query: {query}")
    print()

    result = await executor.execute(query=query, domain=Domain.CODE)

    print("Execution Flow:")
    print("-" * 40)
    for step in result.steps_executed:
        print(f"{step.step_name}:")
        print(f"  Status: {step.status.value}")
        print(f"  Quality: {step.quality_score:.2%} (threshold: {step.metadata.get('threshold', 0):.2%})")
        print(f"  Cost: ${step.cost:.6f}")
        print()

    print(f"Fallback Used: {result.fallback_used}")
    print(f"Total Cost: ${result.total_cost:.6f}")
    print()

    print("=" * 80)
    print()


async def main():
    """Run all Phase 4 demos."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "PHASE 4: MULTI-STEP CASCADING" + " " * 24 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # Demo 1: CODE cascade
    await demo_code_cascade()

    # Demo 2: MEDICAL cascade
    await demo_medical_cascade()

    # Demo 3: GENERAL cascade
    await demo_general_cascade()

    # Demo 4: DATA cascade
    await demo_data_cascade()

    # Demo 5: Multi-domain executor
    await demo_multi_domain_executor()

    # Demo 6: Cost comparison
    await demo_cost_comparison()

    # Demo 7: Fallback behavior
    await demo_fallback_behavior()

    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 32 + "DEMO COMPLETE!" + " " * 31 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    print("Summary:")
    print("• Multi-step cascade pipelines with domain-specific strategies")
    print("• Automatic validation at each step")
    print("• Intelligent fallback to more capable models only when needed")
    print("• 95% cost savings for code queries (Deepseek vs GPT-4)")
    print("• 98% cost savings for general queries (Groq vs GPT-4)")
    print("• Step-by-step cost tracking and quality metrics")
    print()
    print("Next steps:")
    print("1. Integrate with CascadeAgent for automatic domain detection + cascading")
    print("2. Add custom validation functions for specific use cases")
    print("3. Create custom domain strategies for your specific needs")
    print("4. Monitor cascade success rates in production")
    print()


if __name__ == "__main__":
    asyncio.run(main())
