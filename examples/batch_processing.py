"""
Example: Batch Processing with cascadeflow v0.2.1

This example demonstrates batch processing capabilities.
"""

import asyncio
from cascadeflow import CascadeAgent, BatchConfig, BatchStrategy


async def main():
    # Create agent
    agent = CascadeAgent.from_env()

    # Simple batch processing
    queries = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?",
    ]

    print("Processing 3 queries in batch...")
    result = await agent.run_batch(queries)

    print(f"\n✓ Success: {result.success_count}/{len(queries)}")
    print(f"✓ Total cost: ${result.total_cost:.4f}")
    print(f"✓ Average cost: ${result.average_cost:.4f}")
    print(f"✓ Total time: {result.total_time:.2f}s")
    print(f"✓ Strategy: {result.strategy_used}")

    for i, cascade_result in enumerate(result.results):
        if cascade_result:
            print(f"\nQuery {i+1}: {cascade_result.content[:100]}...")


if __name__ == "__main__":
    asyncio.run(main())
