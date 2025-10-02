"""
Basic cascade example to test everything works.
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import CascadeAgent, ModelConfig, CascadeConfig

load_dotenv()


async def main():
    """Run basic cascade."""

    print("🌊 CascadeFlow - Basic Cascade Test\n")

    # Simple cascade with just OpenAI models
    models = [
        ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002),
        ModelConfig(name="gpt-4", provider="openai", cost=0.03),
    ]

    # Use lower quality threshold for simple queries
    # (Short correct answers like "4" get ~0.7 confidence)
    config = CascadeConfig(quality_threshold=0.6)

    agent = CascadeAgent(models, config=config, verbose=True)

    # Test query
    query = "What is 2+2?"

    print(f"Query: {query}\n")

    try:
        result = await agent.run(query)

        print(f"\n✅ Success!")
        print(f"Model: {result.model_used}")
        print(f"Cost: ${result.total_cost:.6f}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Cascaded: {result.cascaded}")
        print(f"\nResponse: {result.content}")

        # Show stats
        print(f"\nStats:")
        stats = agent.get_stats()
        print(f"  Total queries: {stats['total_queries']}")
        print(f"  Total cost: ${stats['total_cost']:.6f}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())