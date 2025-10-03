"""
Domain-specific model routing example.

Shows how to use specialized models for different domains.
"""

import asyncio
from dotenv import load_dotenv

from cascadeflow import CascadeAgent, ModelConfig

load_dotenv()


async def main():
    """Demonstrate domain-specific routing."""

    print("🌊 CascadeFlow - Domain-Specific Models\n")

    # Define domain-specific cascade
    models = [
        # Code domain
        ModelConfig(
            name="codellama/CodeLlama-34b-Instruct-hf",
            provider="huggingface",
            cost=0.0,
            domains=["code"],
            keywords=["code", "programming", "function"]
        ),

        # General with code capability
        ModelConfig(
            name="meta-llama/Llama-3-70b-chat-hf",
            provider="together",
            cost=0.0009,
            domains=["general", "code"]
        ),

        # Fallback to GPT-4
        ModelConfig(
            name="gpt-4",
            provider="openai",
            cost=0.03,
            domains=["general", "code", "reasoning"]
        ),
    ]

    agent = CascadeAgent(models, verbose=True)

    # Test queries
    queries = [
        ("Write a Python function to calculate Fibonacci numbers", "code"),
        ("Explain how binary search works", "general"),
        ("Debug this code: def sum(a b): return a + b", "code"),
    ]

    for query, expected_domain in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"Expected domain: {expected_domain}")
        print(f"{'='*60}\n")

        try:
            result = await agent.run(
                query,
                domains=[expected_domain]  # Hint the domain
            )

            print(f"✅ Success!")
            print(f"Model: {result.model_used}")
            print(f"Provider: {result.provider}")
            print(f"Cost: ${result.total_cost:.6f}")
            print(f"\nResponse:\n{result.content[:300]}...")

        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())