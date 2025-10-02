"""
Full cascade example with all providers.

Demonstrates cascading from free local models to expensive cloud models.
"""

import asyncio
from dotenv import load_dotenv

from cascadeflow import CascadeAgent, ModelConfig, UserTier

load_dotenv()


async def main():
    """Run full cascade example."""

    print("🌊 CascadeFlow - Full Cascade Demo\n")

    # Define complete cascade (cheap → expensive)
    # NOTE: Must use keyword arguments with Pydantic v2!
    models = [
        ModelConfig(name="gemma3:1b", provider="ollama", cost=0.0),
        ModelConfig(name="llama-3.1-70b-versatile", provider="groq", cost=0.0),
        ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002),
        ModelConfig(name="gpt-4", provider="openai", cost=0.03),
    ]

    # Define user tiers
    tiers = {
        "free": UserTier(
            name="free",
            max_budget=0.001,
            quality_threshold=0.6,
        ),
        "pro": UserTier(
            name="pro",
            max_budget=0.01,
            quality_threshold=0.8,
        ),
        "premium": UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.9,
        )
    }

    # Create agent
    agent = CascadeAgent(models, tiers=tiers, verbose=True)

    # Example queries
    queries = [
        ("What is 2+2?", "free"),
        ("Explain quantum computing", "pro"),
        ("Write a detailed explanation of distributed consensus algorithms", "premium"),
    ]

    for query, tier in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"Tier: {tier}")
        print(f"{'='*60}\n")

        try:
            result = await agent.run(query, user_tier=tier)

            print(f"\n✅ Success!")
            print(f"Model: {result.model_used}")
            print(f"Cost: ${result.total_cost:.6f}")
            print(f"Tokens: {result.total_tokens}")
            print(f"Confidence: {result.confidence:.2f}")
            print(f"Cascaded: {result.cascaded}")
            if result.cascaded:
                print(f"Cascade path: {' → '.join(result.cascade_path)}")
            print(f"\nResponse: {result.content[:200]}...")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Show stats
    print(f"\n{'='*60}")
    print("Agent Statistics")
    print(f"{'='*60}")
    stats = agent.get_stats()
    print(f"Total queries: {stats['total_queries']}")
    print(f"Total cost: ${stats['total_cost']:.6f}")
    print(f"Avg cost: ${stats['avg_cost']:.6f}")
    print(f"Cascade rate: {stats['cascade_rate']*100:.1f}%")
    print(f"\nModel usage:")
    for model, count in stats['model_usage'].items():
        print(f"  {model}: {count}")


if __name__ == "__main__":
    asyncio.run(main())